"""Select and manage NOVA's dedicated Chromium automation browser.

Supported browsers: Brave, Microsoft Edge, and Google Chrome.
On Windows, Auto follows the user's HTTPS default-app ProgID when it is one
of those browsers. Unsupported defaults fall back to Microsoft Edge.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

SUPPORTED_BROWSERS = ("brave", "edge", "chrome")
PROCESS_NAMES = {
    "brave": "brave.exe",
    "edge": "msedge.exe",
    "chrome": "chrome.exe",
}


@dataclass(frozen=True)
class BrowserConfig:
    name: str
    executable_path: str
    profile_path: str
    detected_from: str
    launch_channel: str | None = None

    @property
    def display_name(self) -> str:
        return {"brave": "Brave", "edge": "Microsoft Edge", "chrome": "Google Chrome"}[self.name]


def browser_from_prog_id(prog_id: str | None) -> str | None:
    """Map Windows URL-handler ProgIDs to the browsers NOVA supports."""
    value = (prog_id or "").strip().casefold()
    if not value:
        return None
    if "brave" in value:
        return "brave"
    if "chrome" in value or "googlechrome" in value:
        return "chrome"
    if "msedge" in value or "microsoftedge" in value or value.startswith("edge"):
        return "edge"
    return None


def choose_browser_name(default_prog_id: str | None, override: str | None = "auto") -> str:
    """Choose a supported browser; unsupported Windows defaults use Edge."""
    requested = (override or "auto").strip().casefold()
    if requested not in ("", "auto"):
        aliases = {"brave-browser": "brave", "microsoft-edge": "edge", "google-chrome": "chrome"}
        requested = aliases.get(requested, requested)
        if requested not in SUPPORTED_BROWSERS:
            raise ValueError(
                f"Unsupported NOVA_BROWSER={override!r}. Choose auto, brave, edge, or chrome."
            )
        return requested
    return browser_from_prog_id(default_prog_id) or "edge"


def _windows_default_prog_id() -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg  # Windows-only standard library module

        key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "ProgId")
            return str(value)
    except (OSError, ImportError):
        return None


def _default_handler_executable(prog_id: str | None) -> str | None:
    """Read the registered open command to support non-standard install paths."""
    if os.name != "nt" or not prog_id:
        return None
    try:
        import winreg

        key_path = rf"{prog_id}\shell\open\command"
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
            command, _ = winreg.QueryValueEx(key, None)
        command = str(command).strip()
        quoted = re.match(r'^\s*"([^\"]+\.exe)"', command, flags=re.IGNORECASE)
        if quoted:
            candidate = quoted.group(1)
        else:
            candidate = command.split()[0].strip('"') if command else ""
        return candidate if candidate and Path(candidate).is_file() else None
    except (OSError, ImportError, IndexError):
        return None


def _candidate_paths(browser: str, env: Mapping[str, str]) -> list[str]:
    local = env.get("LOCALAPPDATA", "")
    pf = env.get("PROGRAMFILES", r"C:\Program Files")
    pf86 = env.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")

    if browser == "brave":
        relative = Path("BraveSoftware") / "Brave-Browser" / "Application" / "brave.exe"
        bases = [Path(local), Path(pf), Path(pf86)]
    elif browser == "chrome":
        relative = Path("Google") / "Chrome" / "Application" / "chrome.exe"
        bases = [Path(local), Path(pf), Path(pf86)]
    else:
        relative = Path("Microsoft") / "Edge" / "Application" / "msedge.exe"
        bases = [Path(pf86), Path(pf), Path(local)]

    paths = [str(base / relative) for base in bases if str(base)]
    path_name = PROCESS_NAMES[browser]
    discovered = shutil.which(path_name)
    if discovered:
        paths.append(discovered)
    # Preserve order while removing duplicates.
    return list(dict.fromkeys(paths))


def _find_executable(browser: str, env: Mapping[str, str], preferred: str | None = None) -> str | None:
    candidates = ([preferred] if preferred else []) + _candidate_paths(browser, env)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    return None


def detect_browser(base_dir: str | os.PathLike[str] | None = None,
                   environ: Mapping[str, str] | None = None) -> BrowserConfig:
    """Resolve NOVA_BROWSER=auto|brave|edge|chrome to a real browser executable."""
    env = os.environ if environ is None else environ
    prog_id = _windows_default_prog_id()
    default_kind = browser_from_prog_id(prog_id)
    override = env.get("NOVA_BROWSER", "auto")
    selected = choose_browser_name(prog_id, override)

    custom_path = env.get("NOVA_BROWSER_PATH", "").strip()
    launch_channel: str | None = None
    if custom_path:
        custom = Path(custom_path).expanduser()
        if custom.is_file():
            inferred = browser_from_prog_id(custom.name)
            if inferred is None:
                basename = custom.name.casefold()
                inferred = next((name for name, exe in PROCESS_NAMES.items() if basename == exe), None)
            if inferred is None:
                raise FileNotFoundError(
                    "NOVA_BROWSER_PATH must point to brave.exe, msedge.exe, or chrome.exe."
                )
            if override not in ("", "auto") and selected != inferred:
                raise ValueError("NOVA_BROWSER and NOVA_BROWSER_PATH select different browsers.")
            selected = inferred
            executable = str(custom.resolve())
            detected_from = "NOVA_BROWSER_PATH"
        else:
            raise FileNotFoundError(f"NOVA_BROWSER_PATH does not exist: {custom_path}")
    else:
        preferred = _default_handler_executable(prog_id) if selected == default_kind else None
        executable = _find_executable(selected, env, preferred=preferred)
        detected_from = (
            f"Windows default browser ({prog_id})" if selected == default_kind and default_kind
            else "NOVA_BROWSER override" if override not in ("", "auto")
            else "Microsoft Edge fallback"
        )
        # Prefer Playwright's officially supported branded channels for standard
        # Chrome/Edge installs. Use executable_path only for non-standard paths.
        standard_paths = {str(Path(item).resolve()).casefold() for item in _candidate_paths(selected, env)}
        is_standard_location = not preferred or str(Path(preferred).resolve()).casefold() in standard_paths
        if selected == "edge" and is_standard_location:
            launch_channel = "msedge"
        elif selected == "chrome" and is_standard_location:
            launch_channel = "chrome"

    # If a recognized default browser is not found at its registered path, use
    # Edge as the documented fallback. Do not silently choose another browser.
    if not executable and selected != "edge" and override in ("", "auto"):
        selected = "edge"
        executable = _find_executable("edge", env)
        detected_from = "Edge fallback (selected browser executable not found)"
        launch_channel = "msedge"

    if not executable:
        raise FileNotFoundError(
            f"NOVA could not find {selected}. Install Microsoft Edge, Chrome, or Brave, "
            "or set NOVA_BROWSER_PATH to the browser executable."
        )

    root = Path(base_dir or Path(__file__).resolve().parent)
    if selected == "brave":
        # Retain the existing NOVA Brave profile so current users do not lose it.
        profile = root / "BraveAgentProfile"
    else:
        profile = root / "NOVA_BrowserProfiles" / selected

    return BrowserConfig(
        name=selected,
        executable_path=executable,
        profile_path=str(profile.resolve()),
        detected_from=detected_from,
        launch_channel=launch_channel,
    )


def terminate_browser_for_profile(browser_name: str, profile_path: str,
                                  timeout: float = 6.0) -> bool:
    """Stop only a supported browser process whose command line contains NOVA's profile.

    It never terminates ordinary user browser windows or other profiles.
    """
    if os.name != "nt":
        return False
    process_name = PROCESS_NAMES.get(browser_name)
    if not process_name:
        return False
    profile = str(Path(profile_path).resolve())
    escaped = profile.replace("'", "''")
    script = (
        f"$profile = [System.IO.Path]::GetFullPath('{escaped}'); "
        f"Get-CimInstance Win32_Process -Filter \"Name='{process_name}'\" | "
        "Where-Object { $_.CommandLine -and "
        "$_.CommandLine.IndexOf($profile, [StringComparison]::OrdinalIgnoreCase) -ge 0 } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
