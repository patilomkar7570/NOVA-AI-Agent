"""NOVA Coder Permission Stages & Workspace Access Control.

Defines 3 distinct security tiers for CoderAgent:
1. minimal: Read-only inspection & diff/AST viewing. Zero write, zero shell execution.
2. necessary (Default): Workspace development. Full read/write/test within workspace root. Blocks OS root & external drives.
3. all: Full developer autonomy. Multi-file edits, external repo access, Git worktree isolation, package manager execution.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PERMISSIONS_FILE = Path(__file__).resolve().parent.parent / "coder_permissions.json"

STAGE_MINIMAL = "minimal"
STAGE_NECESSARY = "necessary"
STAGE_ALL = "all"

PERMISSION_STAGES: dict[str, dict[str, Any]] = {
    STAGE_MINIMAL: {
        "id": STAGE_MINIMAL,
        "label": "Stage 1: Minimal (Read-Only)",
        "summary": "Safe AST syntax check & code diff inspection without disk modifications.",
        "hover_info": (
            "Read-Only Inspection Mode: Allows CoderAgent to read files and inspect syntax, "
            "but strictly blocks any file modifications, unified diff writing, package installations, "
            "or shell/test executions on disk."
        ),
        "allow_read": True,
        "allow_write": False,
        "allow_execute": False,
        "allow_external": False,
    },
    STAGE_NECESSARY: {
        "id": STAGE_NECESSARY,
        "label": "Stage 2: Necessary (Workspace Protected - Recommended)",
        "summary": "Full read, write, patch, and test execution restricted strictly to the project workspace.",
        "hover_info": (
            "Balanced Workspace Development (Recommended): Permits reading, writing, patching, "
            "and running test suites strictly within the current project workspace repository. "
            "Access outside the workspace root and modifications to OS/system drives are strictly prohibited."
        ),
        "allow_read": True,
        "allow_write": True,
        "allow_execute": True,
        "allow_external": False,
    },
    STAGE_ALL: {
        "id": STAGE_ALL,
        "label": "Stage 3: All (Full Autonomous Developer)",
        "summary": "Unrestricted developer autonomy with multi-file edits, Git worktree isolation, and external access.",
        "hover_info": (
            "Full Autonomous Developer Mode: Grants unrestricted multi-file editing, Git worktree isolation, "
            "package management (pip/npm), and system-level test execution across workspace and linked directories "
            "under automated safety policy guardrails."
        ),
        "allow_read": True,
        "allow_write": True,
        "allow_execute": True,
        "allow_external": True,
    },
}

DEFAULT_STAGE = STAGE_NECESSARY


def get_coder_permissions() -> dict[str, Any]:
    """Load current coder permission configuration."""
    stage = DEFAULT_STAGE
    if PERMISSIONS_FILE.is_file():
        try:
            data = json.loads(PERMISSIONS_FILE.read_text(encoding="utf-8"))
            candidate = str(data.get("stage") or "").lower().strip()
            if candidate in PERMISSION_STAGES:
                stage = candidate
        except Exception:
            pass

    info = dict(PERMISSION_STAGES[stage])
    return {
        "current_stage": stage,
        "stage_info": info,
        "available_stages": [dict(s) for s in PERMISSION_STAGES.values()],
    }


def set_coder_permission_stage(stage: str) -> dict[str, Any]:
    """Persist and update the active coder permission stage."""
    clean_stage = str(stage or "").lower().strip()
    # Map common aliases
    if clean_stage in {"read_only", "readonly", "safe", "min", "1"}:
        clean_stage = STAGE_MINIMAL
    elif clean_stage in {"default", "workspace", "normal", "balanced", "2"}:
        clean_stage = STAGE_NECESSARY
    elif clean_stage in {"full", "unrestricted", "max", "admin", "3"}:
        clean_stage = STAGE_ALL

    if clean_stage not in PERMISSION_STAGES:
        raise ValueError(f"Invalid permission stage '{stage}'. Choose from: {list(PERMISSION_STAGES.keys())}")

    payload = {
        "stage": clean_stage,
        "updated_at": os.environ.get("MOCK_TIME", None) or Path(__file__).stat().st_mtime,
    }
    try:
        PERMISSIONS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as exc:
        raise IOError(f"Could not write permissions file: {exc}")

    return get_coder_permissions()


def verify_file_write_permission(filepath: Path | str, workspace_root: Path | None = None) -> tuple[bool, str]:
    """Check if writing or patching the given file is allowed under the current stage."""
    perms = get_coder_permissions()
    stage = perms["current_stage"]
    stage_info = perms["stage_info"]

    if not stage_info.get("allow_write", False):
        return False, (
            f"Permission Denied: CoderAgent is configured in '{stage}' stage (Read-Only). "
            f"File writing is prohibited. Switch permission stage to 'necessary' or 'all' in Settings."
        )

    root = (workspace_root or Path.cwd()).resolve()
    target = Path(filepath).resolve()

    # Protected OS System Directories (Prohibited even under Stage 'All' for system safety)
    target_str = str(target).lower().replace("/", "\\")
    protected_system_roots = [
        "c:\\windows",
        "c:\\program files",
        "c:\\program files (x86)",
        "c:\\recovery",
        "/etc",
        "/bin",
        "/sbin",
        "/usr/bin",
        "/usr/sbin",
    ]
    for sys_root in protected_system_roots:
        clean_sys = sys_root.lower().replace("/", "\\")
        if target_str.startswith(clean_sys):
            return False, (
                f"Permission Denied: Target path '{filepath}' resides in a protected operating system directory. "
                "System directory modifications are strictly prohibited under NOVA safety policy."
            )

    if not stage_info.get("allow_external", False):
        try:
            target.relative_to(root)
        except ValueError:
            return False, (
                f"Permission Denied: Target path '{filepath}' is outside workspace root '{root}'. "
                f"CoderAgent in '{stage}' stage cannot modify external paths. Upgrade to 'all' in Settings."
            )

    return True, "Permission granted"


def verify_test_execution_permission() -> tuple[bool, str]:
    """Check if test/subprocess execution is allowed under current stage."""
    perms = get_coder_permissions()
    stage = perms["current_stage"]
    stage_info = perms["stage_info"]

    if not stage_info.get("allow_execute", False):
        return False, (
            f"Permission Denied: CoderAgent is configured in '{stage}' stage. "
            f"Command/test execution is disabled. Switch permission stage to 'necessary' or 'all' in Settings."
        )

    return True, "Execution granted"
