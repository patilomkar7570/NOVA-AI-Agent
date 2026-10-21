"""Local SQLite memory for NOVA's verified website locators and safe workflows.

This module stores only selector metadata and a narrow allowlisted workflow cache.
It does not store page text, form contents, passwords, cookies, or browser profiles.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit

DB_PATH = Path(__file__).resolve().with_name("nova_website_memory.sqlite3")


def _connect():
    # The database is private per installation and is created on first use.
    # Creating the parent folder is harmless and does not touch an existing database.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def _init_db():
    with _connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS locators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            path TEXT NOT NULL,
            action TEXT NOT NULL,
            target_key TEXT NOT NULL,
            locator_type TEXT NOT NULL,
            locator_value TEXT NOT NULL,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL,
            last_used INTEGER NOT NULL,
            UNIQUE(domain, path, action, target_key, locator_type, locator_value)
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_locator_lookup
            ON locators(domain, path, action, target_key)""")
        db.execute("""CREATE TABLE IF NOT EXISTS recipes (
            command_key TEXT PRIMARY KEY,
            command TEXT NOT NULL,
            actions_json TEXT NOT NULL,
            success_count INTEGER NOT NULL DEFAULT 1,
            updated_at INTEGER NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            path TEXT NOT NULL,
            page_title TEXT NOT NULL DEFAULT '',
            page_url TEXT NOT NULL DEFAULT '',
            purpose TEXT NOT NULL DEFAULT '',
            fingerprint TEXT NOT NULL DEFAULT '',
            controls_json TEXT NOT NULL DEFAULT '{}',
            visit_count INTEGER NOT NULL DEFAULT 1,
            last_seen INTEGER NOT NULL,
            last_verified INTEGER,
            UNIQUE(domain, path, page_title)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_pages_lookup ON pages(domain, path, last_seen DESC)")
        db.execute("""CREATE TABLE IF NOT EXISTS workflows (
            command_key TEXT NOT NULL,
            start_host TEXT NOT NULL,
            start_path TEXT NOT NULL,
            command TEXT NOT NULL,
            actions_json TEXT NOT NULL,
            end_host TEXT NOT NULL DEFAULT '',
            end_path TEXT NOT NULL DEFAULT '/',
            success_count INTEGER NOT NULL DEFAULT 1,
            failure_count INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY(command_key, start_host, start_path)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_workflows_start ON workflows(start_host, start_path)")


def normalize_target(value):
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def normalize_command(value):
    return normalize_target(value)


def get_locators(domain, path, action, target, limit=5):
    _init_db()
    key = normalize_target(target)
    with _connect() as db:
        rows = db.execute("""SELECT * FROM locators
            WHERE domain=? AND path=? AND action=? AND target_key=?
            ORDER BY (success_count - failure_count) DESC, success_count DESC, last_used DESC
            LIMIT ?""", (str(domain), str(path or "/"), str(action).upper(), key, int(limit))).fetchall()
        return [dict(row) for row in rows]


def save_locator(domain, path, action, target, locator_type, locator_value):
    if not domain or not target or not locator_type or not locator_value:
        return
    _init_db()
    now = int(time.time())
    with _connect() as db:
        db.execute("""INSERT INTO locators
            (domain,path,action,target_key,locator_type,locator_value,success_count,failure_count,created_at,last_used)
            VALUES (?,?,?,?,?,?,1,0,?,?)
            ON CONFLICT(domain,path,action,target_key,locator_type,locator_value)
            DO UPDATE SET success_count=success_count+1,last_used=excluded.last_used""",
            (str(domain), str(path or "/"), str(action).upper(), normalize_target(target),
             str(locator_type), str(locator_value), now, now))


def record_locator_result(locator_id, success):
    _init_db()
    now = int(time.time())
    column = "success_count" if success else "failure_count"
    with _connect() as db:
        db.execute(f"UPDATE locators SET {column}={column}+1,last_used=? WHERE id=?", (now, int(locator_id)))


def get_recipe(command):
    _init_db()
    key = normalize_command(command)
    with _connect() as db:
        row = db.execute("SELECT actions_json FROM recipes WHERE command_key=?", (key,)).fetchone()
        if not row:
            return None
        try:
            actions = json.loads(row["actions_json"])
        except (TypeError, ValueError):
            return None
        return actions if isinstance(actions, list) else None


def save_recipe(command, actions):
    """Persist only the specific safe recipe NOVA currently supports."""
    key = normalize_command(command)
    if not key:
        return
    compact = [{"action": str(item.get("action", "")).upper(), "args": item.get("args", {})}
               for item in actions if isinstance(item, dict)]
    if [item["action"] for item in compact] != ["SEARCH_WEB", "OPEN_FIRST_ORGANIC_RESULT"]:
        return
    # Only store a bounded, JSON-serializable action plan. No free-form page content is persisted.
    payload = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    now = int(time.time())
    with _connect() as db:
        db.execute("""INSERT INTO recipes(command_key,command,actions_json,success_count,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(command_key) DO UPDATE SET actions_json=excluded.actions_json,
                success_count=recipes.success_count+1,updated_at=excluded.updated_at""",
            (key, str(command).strip()[:300], payload, 1, now))


def save_page_profile(domain, path, page_title, page_url, purpose, fingerprint, controls):
    """Save compact page/interface metadata; never store page body text or form values."""
    if not domain:
        return
    _init_db()
    now = int(time.time())
    title = str(page_title or "")[:240]
    safe_controls = controls if isinstance(controls, dict) else {}
    payload = json.dumps(safe_controls, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > 60000:
        safe_controls = {
            "links": safe_controls.get("links", [])[:30],
            "buttons": safe_controls.get("buttons", [])[:20],
            "inputs": safe_controls.get("inputs", [])[:15],
            "forms": safe_controls.get("forms", [])[:10],
        }
        payload = json.dumps(safe_controls, ensure_ascii=False, separators=(",", ":"))
    with _connect() as db:
        db.execute("""INSERT INTO pages
            (domain,path,page_title,page_url,purpose,fingerprint,controls_json,visit_count,last_seen,last_verified)
            VALUES(?,?,?,?,?,?,?,?,?,NULL)
            ON CONFLICT(domain,path,page_title) DO UPDATE SET
                page_url=excluded.page_url, purpose=excluded.purpose,
                fingerprint=excluded.fingerprint, controls_json=excluded.controls_json,
                visit_count=pages.visit_count+CASE WHEN pages.fingerprint != excluded.fingerprint OR pages.last_seen < (excluded.last_seen - 300) THEN 1 ELSE 0 END,
                last_seen=excluded.last_seen""",
            (str(domain), str(path or "/"), title, str(page_url or "")[:1200],
             str(purpose or "")[:240], str(fingerprint or "")[:128], payload, 1, now))


def get_page_profiles(domain, path, limit=5):
    _init_db()
    with _connect() as db:
        rows = db.execute("SELECT * FROM pages WHERE domain=? AND path=? ORDER BY last_seen DESC LIMIT ?",
                          (str(domain), str(path or "/"), int(limit))).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["controls"] = json.loads(item.pop("controls_json", "{}"))
        except (TypeError, ValueError):
            item["controls"] = {}
        result.append(item)
    return result


def record_page_verified(domain, path, page_title):
    _init_db()
    with _connect() as db:
        db.execute("UPDATE pages SET last_verified=? WHERE domain=? AND path=? AND page_title=?",
                   (int(time.time()), str(domain), str(path or "/"), str(page_title or "")[:240]))


def _url_scope(url):
    try:
        parsed = urlsplit(str(url or ""))
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/") or "/"
        return host, path
    except Exception:
        return "", "/"


_WORKFLOW_ALLOWED_ACTIONS = {
    "OPEN_URL", "CLICK_TEXT", "CLICK_HREF", "OPEN_FIRST_ORGANIC_RESULT",
    "OPEN_FIRST_VIDEO", "OPEN_FIRST_YOUTUBE_VIDEO", "BACK", "FORWARD",
    "SCROLL", "WAIT", "READ_PAGE"
}
_WORKFLOW_RISK_TERMS = re.compile(
    r"\b(buy|purchase|pay|checkout|submit|send|delete|remove|cancel|transfer|"
    r"publish|post|confirm|accept|decline|unsubscribe|sign out|log out|"
    r"place order|book now|save changes)\b", re.IGNORECASE
)


def save_workflow(command, start_url, end_url, actions):
    """Save a verified, low-risk workflow, scoped to its starting website/page.

    Text entry, arbitrary key submission, and search queries are intentionally excluded
    from workflow replay; they remain supported by live semantic interaction and locator memory.
    """
    command_text = re.sub(r"\s+", " ", str(command or "")).strip()
    key = normalize_command(command_text)
    start_host, start_path = _url_scope(start_url)
    end_host, end_path = _url_scope(end_url)
    if not key or not start_host or not isinstance(actions, list) or not actions or len(actions) > 6:
        return False
    compact = []
    for item in actions:
        if not isinstance(item, dict):
            return False
        action = str(item.get("action", "")).upper().strip()
        args = item.get("args", {})
        if action not in _WORKFLOW_ALLOWED_ACTIONS or not isinstance(args, dict):
            return False
        # Never persist a workflow that could replay a consequential action.
        target_text = " ".join(str(args.get(k, "")) for k in ("text", "href", "url", "target"))
        if _WORKFLOW_RISK_TERMS.search(target_text):
            return False
        # Bound and validate stored data; no arbitrary scripts/code can be persisted.
        safe_args = {}
        for k, v in args.items():
            if k not in {"text", "href", "url", "amount", "seconds"}:
                continue
            if not isinstance(v, (str, int, float)):
                return False
            safe_args[k] = str(v)[:1200] if isinstance(v, str) else v
        compact.append({"action": action, "args": safe_args})
    payload = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
    if len(payload) > 8000:
        return False
    now = int(time.time())
    with _connect() as db:
        db.execute("""INSERT INTO workflows
            (command_key,start_host,start_path,command,actions_json,end_host,end_path,success_count,failure_count,updated_at)
            VALUES(?,?,?,?,?,?,?,1,0,?)
            ON CONFLICT(command_key,start_host,start_path) DO UPDATE SET
                command=excluded.command, actions_json=excluded.actions_json,
                end_host=excluded.end_host, end_path=excluded.end_path,
                success_count=workflows.success_count+1, updated_at=excluded.updated_at""",
            (key, start_host, start_path, command_text[:300], payload, end_host, end_path, now))
    return True


def get_workflow(command, start_url):
    """Return a learned workflow only when its starting host/path match exactly."""
    key = normalize_command(command)
    host, path = _url_scope(start_url)
    if not key or not host:
        return None
    _init_db()
    with _connect() as db:
        row = db.execute("""SELECT * FROM workflows
            WHERE command_key=? AND start_host=? AND start_path=?
            ORDER BY success_count DESC, updated_at DESC LIMIT 1""", (key, host, path)).fetchone()
    if not row:
        return None
    try:
        actions = json.loads(row["actions_json"])
    except (TypeError, ValueError):
        return None
    if not isinstance(actions, list) or not actions or len(actions) > 6:
        return None
    # Revalidate the allowlist at read time as a defense-in-depth check.
    if any(not isinstance(x, dict) or str(x.get("action", "")).upper() not in _WORKFLOW_ALLOWED_ACTIONS for x in actions):
        return None
    return actions


def get_stats():
    _init_db()
    with _connect() as db:
        locators = db.execute("SELECT COUNT(*) FROM locators").fetchone()[0]
        recipes = db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
        pages = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        workflows = db.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
        successes = db.execute("SELECT COALESCE(SUM(success_count),0) FROM locators").fetchone()[0]
        failures = db.execute("SELECT COALESCE(SUM(failure_count),0) FROM locators").fetchone()[0]
    return {"pages": pages, "locators": locators, "recipes": recipes, "workflows": workflows, "locator_successes": successes, "locator_failures": failures}


_init_db()
