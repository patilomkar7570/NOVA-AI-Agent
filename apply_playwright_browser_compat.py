from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import shutil
import sys


AGENT_TOP_START = "def find_brave_path():"
AGENT_TOP_END = 'MODEL = "qwen3:8b"'
KILL_START = "def kill_brave():"
START_BROWSER_START = "def start_browser():"
CLOSE_BROWSER_START = "def close_browser():"


def replace_section(source: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Could not find {label} start marker: {start_marker!r}")
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Could not find {label} end marker: {end_marker!r}")
    return source[:start] + replacement.rstrip() + "\n\n" + source[end:]


def build_agent_update(source: str) -> str:
    if "BROWSER_CONFIG = detect_browser(" in source:
        return source

    import_line = "from nova_browser_runtime import detect_browser, terminate_browser_for_profile"
    if import_line not in source:
        anchor = "from playwright.sync_api import sync_playwright"
        if anchor not in source:
            raise RuntimeError("Could not find Playwright import in agent.py")
        source = source.replace(anchor, anchor + "\n" + import_line, 1)

    top_replacement = '''# ============================================================
# CONFIGURATION — CROSS-BROWSER PLAYWRIGHT
# ============================================================

BROWSER_CONFIG = detect_browser(base_dir=os.path.dirname(os.path.abspath(__file__)))
BROWSER_NAME = BROWSER_CONFIG.name
BROWSER_DISPLAY_NAME = BROWSER_CONFIG.display_name
BROWSER_PATH = BROWSER_CONFIG.executable_path
PROFILE_PATH = BROWSER_CONFIG.profile_path

# Backward-compatible alias for older NOVA modules that may still read this.
BRAVE_PATH = BROWSER_PATH

print(
    f"🌐 NOVA automation browser: {BROWSER_DISPLAY_NAME} "
    f"({BROWSER_CONFIG.detected_from})"
)

'''
    source = replace_section(source, AGENT_TOP_START, AGENT_TOP_END, top_replacement, "browser configuration")

    kill_replacement = '''def kill_browser():
    """Stop only NOVA's own automation browser process/profile."""
    if os.name != "nt":
        return
    terminate_browser_for_profile(BROWSER_NAME, PROFILE_PATH)
    time.sleep(0.30)


# Backward-compatible alias; cleanup is now browser-neutral.
def kill_brave():
    return kill_browser()

'''
    source = replace_section(source, KILL_START, START_BROWSER_START, kill_replacement, "browser cleanup")

    start_replacement = '''def start_browser():
    global _browser_context, _page, _playwright, _listener

    # Recover a stale page/context without touching the user's normal browser profile.
    if _page is not None and _browser_context is not None and _playwright is not None:
        try:
            pages = _browser_context.pages
            if not _page.is_closed() and any(page == _page for page in pages):
                _ = _page.url
                return True
        except Exception:
            pass
        close_browser()

    try:
        if not BROWSER_PATH or not os.path.isfile(BROWSER_PATH):
            print(
                f"❌ {BROWSER_DISPLAY_NAME} executable was not found: {BROWSER_PATH}. "
                "Install a supported browser or set NOVA_BROWSER_PATH."
            )
            _browser_context = None
            _page = None
            _playwright = None
            return False

        os.makedirs(PROFILE_PATH, exist_ok=True)
        kill_browser()
        _playwright = sync_playwright().start()

        # Playwright's Chromium driver can launch Chrome, Edge and Brave using
        # their installed executable, while each browser gets a separate NOVA profile.
        launch_options = {
            "user_data_dir": PROFILE_PATH,
            "headless": False,
            "viewport": {"width": 1400, "height": 900},
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-default-apps",
            ],
        }
        if BROWSER_CONFIG.launch_channel:
            # Official Playwright channels for branded Google Chrome and Edge.
            launch_options["channel"] = BROWSER_CONFIG.launch_channel
        else:
            # Brave and explicitly configured non-standard installs use their path.
            launch_options["executable_path"] = BROWSER_PATH

        _browser_context = _playwright.chromium.launch_persistent_context(**launch_options)

        if _browser_context.pages:
            _page = _browser_context.pages[0]
        else:
            _page = _browser_context.new_page()

        _page.set_default_timeout(CLICK_TIMEOUT)

        if _listener is None:
            _listener = threading.Thread(target=esc_listener, daemon=True)
            _listener.start()

        print(f"✅ {BROWSER_DISPLAY_NAME} started for NOVA automation.")
        return True

    except Exception as e:
        print(f"❌ Could not start {BROWSER_DISPLAY_NAME}:\\n{e}")
        try:
            if _browser_context is not None:
                _browser_context.close()
        except Exception:
            pass
        try:
            if _playwright is not None:
                _playwright.stop()
        except Exception:
            pass
        _browser_context = None
        _page = None
        _playwright = None
        return False

'''
    source = replace_section(source, START_BROWSER_START, CLOSE_BROWSER_START, start_replacement, "browser launcher")

    source = source.replace(
        '"⚠️ Brave page/context is no longer usable. Rebuilding the session…"',
        '"⚠️ NOVA automation browser page/context is no longer usable. Rebuilding the session…"',
    )
    source = source.replace(
        '"✅ Brave session recovered; continuing the task."',
        '"✅ NOVA browser session recovered; continuing the task."',
    )
    source = source.replace(
        '"Browser recovery failed: NOVA could not create a live Brave page. "',
        '"Browser recovery failed: NOVA could not create a live automation browser page. "',
    )
    source = source.replace(
        '"Check the Brave installation, backend console, and whether "',
        '"Check the selected browser installation, backend console, and whether "',
    )
    source = source.replace(
        '"BraveAgentProfile is locked by another process."',
        '"NOVA browser profile is locked by another process."',
    )
    return source


def build_api_update(source: str) -> str:
    return source.replace('"Could not start Brave."', '"Could not start NOVA automation browser."')


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch NOVA Playwright to support Brave, Edge and Chrome.")
    parser.add_argument("--root", default=".", help="NOVA project root containing agent.py and api.py")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    agent_path = root / "agent.py"
    api_path = root / "api.py"
    runtime_source = Path(__file__).with_name("nova_browser_runtime.py")

    if not agent_path.is_file():
        print(f"ERROR: agent.py not found under {root}")
        return 2
    if not runtime_source.is_file():
        print(f"ERROR: Missing {runtime_source}")
        return 2

    try:
        original_agent = agent_path.read_text(encoding="utf-8")
        updated_agent = build_agent_update(original_agent)
        original_api = api_path.read_text(encoding="utf-8") if api_path.exists() else None
        updated_api = build_api_update(original_api) if original_api is not None else None
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        print("No files were changed.")
        return 3

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backups = []
    try:
        if updated_agent != original_agent:
            backup = agent_path.with_name(f"agent.py.before_browser_patch.{stamp}.bak")
            shutil.copy2(agent_path, backup)
            backups.append(backup.name)
            agent_path.write_text(updated_agent, encoding="utf-8", newline="\n")

        if updated_api is not None and updated_api != original_api:
            backup = api_path.with_name(f"api.py.before_browser_patch.{stamp}.bak")
            shutil.copy2(api_path, backup)
            backups.append(backup.name)
            api_path.write_text(updated_api, encoding="utf-8", newline="\n")

        shutil.copy2(runtime_source, root / "nova_browser_runtime.py")
    except OSError as exc:
        print(f"ERROR while writing patch: {exc}")
        print("Restore from the .bak files if one or more writes completed.")
        return 4

    print("SUCCESS: NOVA Playwright browser compatibility updated.")
    print("Supported: Brave, Microsoft Edge, Google Chrome.")
    print("Auto mode follows the Windows HTTPS default browser if supported; otherwise Edge is selected.")
    print("Existing BraveAgentProfile is preserved; Edge and Chrome receive separate NOVA profiles.")
    if backups:
        print("Backups: " + ", ".join(backups))
    else:
        print("agent.py already contains the browser compatibility changes; no agent rewrite was needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
