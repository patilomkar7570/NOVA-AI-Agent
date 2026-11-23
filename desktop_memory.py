"""Local SQLite memory for NOVA's verified Windows desktop applications, controls, and workflows.

Stores learned UI control locations, application profiles, and safe execution workflows
so NOVA learns how to interact with desktop apps (Discord, WhatsApp, Telegram, etc.)
and executes repeat actions faster.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().with_name("nova_desktop_memory.sqlite3")


from contextlib import contextmanager

@contextmanager
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _init_db() -> None:
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS apps (
            app_name TEXT PRIMARY KEY,
            exe_name TEXT NOT NULL DEFAULT '',
            window_title_pattern TEXT NOT NULL DEFAULT '',
            launch_command TEXT NOT NULL DEFAULT '',
            controls_json TEXT NOT NULL DEFAULT '{}',
            visit_count INTEGER NOT NULL DEFAULT 1,
            last_seen INTEGER NOT NULL
        )""")

        db.execute("""CREATE TABLE IF NOT EXISTS controls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            control_name TEXT NOT NULL,
            control_type TEXT NOT NULL DEFAULT '',
            automation_id TEXT NOT NULL DEFAULT '',
            action_type TEXT NOT NULL DEFAULT 'click',
            success_count INTEGER NOT NULL DEFAULT 1,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_used INTEGER NOT NULL,
            UNIQUE(app_name, control_name, control_type, automation_id, action_type)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_controls_lookup
            ON controls(app_name, control_name, action_type)""")

        db.execute("""CREATE TABLE IF NOT EXISTS desktop_workflows (
            command_key TEXT NOT NULL,
            app_name TEXT NOT NULL,
            command TEXT NOT NULL,
            actions_json TEXT NOT NULL,
            success_count INTEGER NOT NULL DEFAULT 1,
            failure_count INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY(command_key, app_name)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_workflows_app
            ON desktop_workflows(app_name, updated_at DESC)""")

        db.execute("""CREATE TABLE IF NOT EXISTS visual_anchors (
            app_name TEXT NOT NULL,
            element_key TEXT NOT NULL,
            norm_x REAL NOT NULL,
            norm_y REAL NOT NULL,
            context_signature TEXT NOT NULL DEFAULT '',
            success_count INTEGER NOT NULL DEFAULT 1,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_verified INTEGER NOT NULL,
            PRIMARY KEY(app_name, element_key)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_anchors_app
            ON visual_anchors(app_name, last_verified DESC)""")

        db.execute("""CREATE TABLE IF NOT EXISTS desktop_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at INTEGER NOT NULL
        )""")


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def normalize_command(value: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", " ", str(value or "")).strip()
    return re.sub(r"\s+", " ", cleaned).casefold()


_SAFE_DESKTOP_ACTIONS = {
    "LAUNCH_APP", "FOCUS_WINDOW", "CLICK_CONTROL", "TYPE_TEXT",
    "SEND_HOTKEY", "SCROLL", "CLOSE_WINDOW", "WAIT"
}


def save_app_profile(
    app_name: str,
    exe_name: str = "",
    window_title_pattern: str = "",
    launch_command: str = "",
    controls: dict[str, Any] | list[Any] | None = None,
) -> None:
    key = normalize_name(app_name)
    if not key:
        return
    _init_db()
    now = int(time.time())
    controls_payload = json.dumps(controls or {}, ensure_ascii=False, separators=(",", ":"))
    if len(controls_payload) > 60000:
        controls_payload = "{}"

    with _connect() as db:
        db.execute("""INSERT INTO apps
            (app_name, exe_name, window_title_pattern, launch_command, controls_json, visit_count, last_seen)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(app_name) DO UPDATE SET
                exe_name = CASE WHEN excluded.exe_name != '' THEN excluded.exe_name ELSE apps.exe_name END,
                window_title_pattern = CASE WHEN excluded.window_title_pattern != '' THEN excluded.window_title_pattern ELSE apps.window_title_pattern END,
                launch_command = CASE WHEN excluded.launch_command != '' THEN excluded.launch_command ELSE apps.launch_command END,
                controls_json = CASE WHEN excluded.controls_json != '{}' THEN excluded.controls_json ELSE apps.controls_json END,
                visit_count = apps.visit_count + 1,
                last_seen = excluded.last_seen""",
            (key, str(exe_name or "")[:260], str(window_title_pattern or "")[:260],
             str(launch_command or "")[:500], controls_payload, now))


def get_app_profile(app_name: str) -> dict[str, Any] | None:
    key = normalize_name(app_name)
    if not key:
        return None
    _init_db()
    with _connect() as db:
        row = db.execute("SELECT * FROM apps WHERE app_name = ?", (key,)).fetchone()
        if not row:
            # Try prefix / suffix substring match
            row = db.execute(
                "SELECT * FROM apps WHERE app_name LIKE ? ORDER BY visit_count DESC LIMIT 1",
                (f"%{key}%",)
            ).fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["controls"] = json.loads(res.pop("controls_json", "{}"))
        except (TypeError, ValueError):
            res["controls"] = {}
        return res


def save_control(
    app_name: str,
    control_name: str,
    control_type: str = "",
    automation_id: str = "",
    action_type: str = "click",
) -> None:
    app_key = normalize_name(app_name)
    ctrl_key = str(control_name or "").strip()
    if not app_key or not ctrl_key:
        return
    _init_db()
    now = int(time.time())
    with _connect() as db:
        db.execute("""INSERT INTO controls
            (app_name, control_name, control_type, automation_id, action_type, success_count, failure_count, last_used)
            VALUES (?, ?, ?, ?, ?, 1, 0, ?)
            ON CONFLICT(app_name, control_name, control_type, automation_id, action_type)
            DO UPDATE SET success_count = success_count + 1, last_used = excluded.last_used""",
            (app_key, ctrl_key[:200], str(control_type or "")[:80],
             str(automation_id or "")[:120], str(action_type or "click").lower()[:40], now))


def get_controls(app_name: str, action_type: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    app_key = normalize_name(app_name)
    if not app_key:
        return []
    _init_db()
    with _connect() as db:
        if action_type:
            rows = db.execute("""SELECT * FROM controls
                WHERE app_name = ? AND action_type = ?
                ORDER BY (success_count - failure_count) DESC, success_count DESC, last_used DESC
                LIMIT ?""", (app_key, str(action_type).lower(), int(limit))).fetchall()
        else:
            rows = db.execute("""SELECT * FROM controls
                WHERE app_name = ?
                ORDER BY (success_count - failure_count) DESC, success_count DESC, last_used DESC
                LIMIT ?""", (app_key, int(limit))).fetchall()
        return [dict(r) for r in rows]


def save_desktop_workflow(command: str, app_name: str, actions: list[dict[str, Any]]) -> bool:
    """Save a verified desktop workflow sequence for an application."""
    cmd_key = normalize_command(command)
    app_key = normalize_name(app_name)
    if not cmd_key or not app_key or not isinstance(actions, list) or not actions:
        return False

    compact = []
    for item in actions[:10]:
        if not isinstance(item, dict):
            continue
        act = str(item.get("action", "")).upper().strip()
        if act not in _SAFE_DESKTOP_ACTIONS:
            continue
        args = item.get("args", {})
        if not isinstance(args, dict):
            args = {}
        # Sanitize arguments
        safe_args = {}
        for k, v in args.items():
            if isinstance(v, (str, int, float, bool)):
                safe_args[k] = str(v)[:500] if isinstance(v, str) else v
        compact.append({"action": act, "args": safe_args})

    if not compact:
        return False

    payload = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    now = int(time.time())
    _init_db()
    with _connect() as db:
        db.execute("""INSERT INTO desktop_workflows
            (command_key, app_name, command, actions_json, success_count, failure_count, updated_at)
            VALUES (?, ?, ?, ?, 1, 0, ?)
            ON CONFLICT(command_key, app_name) DO UPDATE SET
                command = excluded.command,
                actions_json = excluded.actions_json,
                success_count = desktop_workflows.success_count + 1,
                updated_at = excluded.updated_at""",
            (cmd_key, app_key, str(command).strip()[:300], payload, now))
    return True


def get_desktop_workflow(command: str, app_name: str | None = None) -> list[dict[str, Any]] | None:
    cmd_key = normalize_command(command)
    if not cmd_key:
        return None
    _init_db()
    with _connect() as db:
        if app_name:
            app_key = normalize_name(app_name)
            row = db.execute("""SELECT actions_json FROM desktop_workflows
                WHERE command_key = ? AND app_name = ? AND success_count > failure_count
                ORDER BY (success_count - failure_count) DESC, success_count DESC, updated_at DESC LIMIT 1""",
                (cmd_key, app_key)).fetchone()
        else:
            row = db.execute("""SELECT actions_json FROM desktop_workflows
                WHERE command_key = ? AND success_count > failure_count
                ORDER BY (success_count - failure_count) DESC, success_count DESC, updated_at DESC LIMIT 1""",
                (cmd_key,)).fetchone()

        if not row:
            # Fuzzy match command
            if app_name:
                row = db.execute("""SELECT actions_json FROM desktop_workflows
                    WHERE command_key LIKE ? AND app_name = ? AND success_count > failure_count
                    ORDER BY (success_count - failure_count) DESC, success_count DESC, updated_at DESC LIMIT 1""",
                    (f"%{cmd_key}%", normalize_name(app_name))).fetchone()
            else:
                row = db.execute("""SELECT actions_json FROM desktop_workflows
                    WHERE command_key LIKE ? AND success_count > failure_count
                    ORDER BY (success_count - failure_count) DESC, success_count DESC, updated_at DESC LIMIT 1""",
                    (f"%{cmd_key}%",)).fetchone()

        if not row:
            return None
        try:
            actions = json.loads(row["actions_json"])
            if isinstance(actions, list):
                return actions
        except (TypeError, ValueError):
            return None
    return None


def record_workflow_result(command: str, app_name: str, success: bool) -> None:
    cmd_key = normalize_command(command)
    app_key = normalize_name(app_name)
    if not cmd_key or not app_key:
        return
    _init_db()
    now = int(time.time())
    with _connect() as db:
        if success:
            db.execute(
                "UPDATE desktop_workflows SET success_count = success_count + 1, updated_at = ? WHERE command_key = ? AND app_name = ?",
                (now, cmd_key, app_key)
            )
        else:
            db.execute(
                "UPDATE desktop_workflows SET failure_count = failure_count + 1, updated_at = ? WHERE command_key = ? AND app_name = ?",
                (now, cmd_key, app_key)
            )
            # Auto-purge broken workflows
            db.execute(
                "DELETE FROM desktop_workflows WHERE command_key = ? AND app_name = ? AND failure_count >= success_count",
                (cmd_key, app_key)
            )



def set_meta(key: str, value: str) -> None:
    _init_db()
    with _connect() as db:
        db.execute("""INSERT INTO desktop_meta (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (str(key), str(value), int(time.time())))


def get_meta(key: str) -> str | None:
    _init_db()
    with _connect() as db:
        row = db.execute("""SELECT value FROM desktop_meta WHERE key=?""", (str(key),)).fetchone()
        return str(row["value"]) if row else None


def save_last_created_note(file_path: str) -> None:
    set_meta("last_created_note", file_path)


def get_last_created_note() -> str | None:
    return get_meta("last_created_note")


def save_last_app(app_name: str) -> None:
    if app_name:
        set_meta("last_app", app_name.strip().lower())


def get_last_app() -> str | None:
    return get_meta("last_app")


def save_last_assistant_output(text: str, conversation_id: str | None = None) -> None:
    if text:
        cid = str(conversation_id or "").strip()
        key = f"last_assistant_output:{cid}" if cid else "last_assistant_output"
        set_meta(key, text.strip())


def get_last_assistant_output(conversation_id: str | None = None) -> str | None:
    cid = str(conversation_id or "").strip()
    if cid:
        return get_meta(f"last_assistant_output:{cid}")
    return get_meta("last_assistant_output") or None


def delete_conversation_memory(conversation_id: str) -> None:
    cid = str(conversation_id or "").strip()
    if not cid:
        return
    _init_db()
    with _connect() as db:
        db.execute(
            "DELETE FROM desktop_meta WHERE key = ? OR key LIKE ?",
            (f"last_assistant_output:{cid}", f"%:{cid}")
        )


def get_desktop_stats() -> dict[str, int]:
    _init_db()
    with _connect() as db:
        apps_count = db.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
        controls_count = db.execute("SELECT COUNT(*) FROM controls").fetchone()[0]
        workflows_count = db.execute("SELECT COUNT(*) FROM desktop_workflows").fetchone()[0]
        anchors_count = db.execute("SELECT COUNT(*) FROM visual_anchors").fetchone()[0]
    return {
        "apps": apps_count,
        "controls": controls_count,
        "workflows": workflows_count,
        "anchors": anchors_count,
    }


def save_visual_anchor(
    app_name: str,
    element_key: str,
    norm_x: float,
    norm_y: float,
    context_signature: str = "",
) -> None:
    """Save an element anchor using normalized geometric vectors rather than fixed pixels."""
    app_key = normalize_name(app_name)
    elem_key = normalize_name(element_key)
    if not app_key or not elem_key:
        return
    _init_db()
    now = int(time.time())
    with _connect() as db:
        db.execute("""
            INSERT INTO visual_anchors (app_name, element_key, norm_x, norm_y, context_signature, last_verified)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(app_name, element_key) DO UPDATE SET
                norm_x = excluded.norm_x,
                norm_y = excluded.norm_y,
                context_signature = excluded.context_signature,
                success_count = visual_anchors.success_count + 1,
                last_verified = excluded.last_verified
        """, (app_key, elem_key, float(norm_x), float(norm_y), str(context_signature or "")[:200], now))


def get_visual_anchor(app_name: str, element_key: str) -> dict[str, Any] | None:
    """Retrieve normalized coordinates and context signature for an element."""
    app_key = normalize_name(app_name)
    elem_key = normalize_name(element_key)
    if not app_key or not elem_key:
        return None
    _init_db()
    with _connect() as db:
        row = db.execute(
            "SELECT * FROM visual_anchors WHERE app_name = ? AND element_key = ?",
            (app_key, elem_key)
        ).fetchone()
        if not row:
            # Substring match on element_key
            row = db.execute(
                "SELECT * FROM visual_anchors WHERE app_name = ? AND element_key LIKE ? ORDER BY success_count DESC LIMIT 1",
                (app_key, f"%{elem_key}%")
            ).fetchone()
        if not row:
            return None
        return dict(row)


def verify_anchor_drift(
    app_name: str,
    element_key: str,
    current_norm_pos: tuple[float, float],
    tolerance: float = 0.20
) -> bool:
    """Returns True if the current element position matches the cached anchor within tolerance."""
    anchor = get_visual_anchor(app_name, element_key)
    if not anchor:
        return True  # No prior anchor to conflict with
    dx = abs(anchor["norm_x"] - current_norm_pos[0])
    dy = abs(anchor["norm_y"] - current_norm_pos[1])
    dist = (dx**2 + dy**2) ** 0.5
    return dist <= tolerance


_init_db()
