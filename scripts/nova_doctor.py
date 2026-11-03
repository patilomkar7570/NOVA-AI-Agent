"""Read-only setup diagnostics for a local NOVA project.

Run from the project root with: python scripts/nova_doctor.py
The script never launches services, changes settings, or modifies project data.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import socket
import sqlite3
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "qwen3:8b"
OLLAMA_TAGS_URL = os.environ.get("NOVA_OLLAMA_TAGS_URL", "http://127.0.0.1:11434/api/tags")


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def model_available(tags_payload: dict, model_name: str = DEFAULT_MODEL) -> bool:
    """Return true when the Ollama tags response contains the requested model."""
    models = tags_payload.get("models", []) if isinstance(tags_payload, dict) else []
    if not isinstance(models, list):
        return False
    names = {
        str(item.get("name", "")).strip()
        for item in models
        if isinstance(item, dict)
    }
    return model_name in names or f"{model_name}:latest" in names


def port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_project_layout(root: Path) -> list[Check]:
    required = (
        "api.py",
        "agent.py",
        "nova_agents/__init__.py",
        "nova_agents/registry.py",
        "frontend/package.json",
        "frontend/src/App.jsx",
        "frontend/src/App.css",
        "frontend/src/voice/voiceController.js",
    )
    return [
        Check(
            name=f"Project file: {relative}",
            status="PASS" if (root / relative).is_file() else "FAIL",
            detail="Present" if (root / relative).is_file() else "Missing",
        )
        for relative in required
    ]


def _check_module(module_name: str) -> Check:
    available = importlib.util.find_spec(module_name) is not None
    return Check(
        name=f"Python dependency: {module_name}",
        status="PASS" if available else "FAIL",
        detail="Importable" if available else "Not installed in this Python environment",
    )


def _check_ollama(model_name: str) -> Check:
    try:
        request = urllib.request.Request(OLLAMA_TAGS_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=2.5) as response:
            payload = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return Check("Ollama service", "WARN", f"Not reachable at {OLLAMA_TAGS_URL}: {exc}")
    if model_available(payload, model_name):
        return Check("Ollama service and model", "PASS", f"Service reachable; {model_name} is available")
    return Check("Ollama model", "WARN", f"Ollama is reachable, but {model_name} was not listed. Run: ollama pull {model_name}")


def _check_database(root: Path) -> Check:
    candidates = (
        root / "nova_shared_memory.sqlite3",
        root / "nova_website_memory.sqlite3",
    )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        return Check("Local databases", "WARN", "No NOVA database exists yet; databases are created on first use")
    for path in existing:
        connection = None
        try:
            connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
            result = connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                return Check("Local database integrity", "FAIL", f"Integrity check did not pass for {path.name}")
        except sqlite3.Error as exc:
            return Check("Local database integrity", "FAIL", f"Could not inspect {path.name}: {exc}")
        finally:
            if connection is not None:
                connection.close()
    return Check("Local database integrity", "PASS", f"Read-only integrity check passed for {len(existing)} database(s)")


def collect_checks(root: Path | None = None) -> list[Check]:
    root = (root or Path.cwd()).resolve()
    checks: list[Check] = []
    py_ok = sys.version_info >= (3, 11)
    checks.append(Check(
        "Python version",
        "PASS" if py_ok else "FAIL",
        f"{platform.python_version()} (Python 3.11+ required)",
    ))
    checks.extend(check_project_layout(root))
    checks.extend((_check_module("ollama"), _check_module("playwright")))

    model_name = os.environ.get("NOVA_MODEL", DEFAULT_MODEL)
    checks.append(_check_ollama(model_name))

    brave_candidates = []
    configured_brave = os.environ.get("NOVA_BRAVE_EXECUTABLE")
    if configured_brave:
        brave_candidates.append(Path(configured_brave).expanduser())
    for env_key in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env_key)
        if base:
            brave_candidates.append(Path(base) / "BraveSoftware/Brave-Browser/Application/brave.exe")
    brave_path = next((path for path in brave_candidates if path.is_file()), None)
    checks.append(Check(
        "Brave Browser",
        "PASS" if brave_path else "WARN",
        str(brave_path) if brave_path else "Not found in standard Windows install locations; verify the Browser Agent can launch Brave",
    ))

    for label, port in (("NOVA API port 8000", 8000), ("Vite frontend port 5173", 5173)):
        is_open = port_open("127.0.0.1", port)
        checks.append(Check(label, "INFO" if is_open else "INFO", "Listening" if is_open else "Not listening (normal when NOVA is stopped)"))

    checks.append(_check_database(root))
    return checks


def main() -> int:
    checks = collect_checks()
    print("NOVA Setup Doctor — read-only diagnostics")
    print(f"Project: {Path.cwd().resolve()}")
    print("-" * 76)
    for check in checks:
        print(f"[{check.status:4}] {check.name}: {check.detail}")
    print("-" * 76)
    counts = {status: sum(item.status == status for item in checks) for status in ("PASS", "WARN", "FAIL", "INFO")}
    print("Summary: " + " · ".join(f"{key} {value}" for key, value in counts.items()))
    print("This diagnostic is read-only. WARN/INFO results do not modify or restart any service.")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
