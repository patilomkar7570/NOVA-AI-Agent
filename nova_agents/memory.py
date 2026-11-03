"""Local shared SQLite memory for NOVA agents.

Stores task history and sourced research notes locally. It uses only Python's
standard-library sqlite3 module and creates the database lazily on first use.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any


_STOPWORDS = {
    "about", "after", "again", "also", "and", "are", "can", "could", "does",
    "for", "from", "have", "how", "into", "just", "latest", "make", "more",
    "most", "much", "what", "when", "where", "which", "with", "would", "your",
    "that", "this", "then", "them", "there", "their", "they", "will", "you",
}


class SharedMemory:
    """One local database shared by the Router/Planner and all specialists."""

    def __init__(self, db_path: str | os.PathLike[str]):
        self.db_path = str(Path(db_path).expanduser().resolve())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    @contextmanager
    def _connection(self):
        """Commit/rollback and always close the short-lived SQLite connection."""
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL UNIQUE,
                    conversation_id TEXT,
                    command TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_task_conversation_time
                    ON task_history(conversation_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL DEFAULT 'research',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0.5,
                    tags TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(category, title, source_url)
                );
                CREATE INDEX IF NOT EXISTS idx_knowledge_updated
                    ON knowledge_items(updated_at DESC);

                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'user',
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    conversation_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    source_task_id TEXT NOT NULL DEFAULT ''
                );

                -- Durable execution journal. A row left as 'running' after a
                -- crash is surfaced for review, never silently replayed.
                CREATE TABLE IF NOT EXISTS execution_runs (
                    task_id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    command TEXT NOT NULL,
                    plan_json TEXT NOT NULL DEFAULT '{}',
                    status TEXT NOT NULL DEFAULT 'running',
                    state TEXT NOT NULL DEFAULT 'queued',
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    final_agent TEXT NOT NULL DEFAULT '',
                    final_message TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_execution_runs_status
                    ON execution_runs(status, started_at DESC);

                CREATE TABLE IF NOT EXISTS execution_steps (
                    task_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    attempt INTEGER NOT NULL,
                    agent TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    duration_ms INTEGER,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    error_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY(task_id, step_index, attempt)
                );
                CREATE INDEX IF NOT EXISTS idx_execution_steps_task
                    ON execution_steps(task_id, step_index, attempt);
                """
            )
            # Backward-compatible schema migration for databases created by Alpha 0.4/0.5.
            knowledge_columns = {
                str(row["name"]) for row in conn.execute("PRAGMA table_info(knowledge_items)").fetchall()
            }
            if "published_at" not in knowledge_columns:
                conn.execute("ALTER TABLE knowledge_items ADD COLUMN published_at TEXT NOT NULL DEFAULT ''")
            execution_columns = {
                str(row["name"]) for row in conn.execute("PRAGMA table_info(execution_runs)").fetchall()
            }
            if "state" not in execution_columns:
                conn.execute("ALTER TABLE execution_runs ADD COLUMN state TEXT NOT NULL DEFAULT 'queued'")
            # Older Alpha journals recorded only a coarse status. Backfill terminal
            # states so the new state machine does not label historical completed
            # or failed executions as if they were still queued.
            conn.execute(
                """UPDATE execution_runs SET state = CASE status
                       WHEN 'completed' THEN 'completed'
                       WHEN 'partial' THEN 'partial'
                       WHEN 'failed' THEN 'failed'
                       WHEN 'stopped' THEN 'cancelled'
                       WHEN 'timed_out' THEN 'timed_out'
                       WHEN 'interrupted' THEN 'interrupted'
                       ELSE state
                   END
                   WHERE state='queued' AND status != 'running'"""
            )

    def record_task(
        self,
        *,
        task_id: str,
        conversation_id: str | None,
        command: str,
        agent: str,
        status: str,
        result: str,
        duration_ms: int | None = None,
    ) -> None:
        """Persist a local task receipt; repeated writes update the same task."""
        now = time.time()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO task_history
                   (task_id, conversation_id, command, agent, status, result, duration_ms, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                     agent=excluded.agent, status=excluded.status, result=excluded.result,
                     duration_ms=excluded.duration_ms""",
                (
                    task_id, conversation_id, command[:8000], agent[:40], status[:30],
                    result[:12000], duration_ms, now,
                ),
            )

    def start_execution(
        self,
        *,
        task_id: str,
        conversation_id: str | None,
        command: str,
        plan: dict[str, Any] | None = None,
    ) -> None:
        """Create or refresh a durable run record before any specialist acts."""
        now = time.time()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO execution_runs
                   (task_id, conversation_id, command, plan_json, status, state, started_at)
                   VALUES (?, ?, ?, ?, 'running', 'queued', ?)
                   ON CONFLICT(task_id) DO UPDATE SET
                     conversation_id=excluded.conversation_id,
                     command=excluded.command, plan_json=excluded.plan_json,
                     status='running', state='queued', started_at=excluded.started_at,
                     finished_at=NULL, final_agent='', final_message=''""",
                (
                    task_id, conversation_id, str(command)[:8000],
                    json.dumps(plan or {}, ensure_ascii=False, default=str)[:30000], now,
                ),
            )

    def update_execution_state(self, task_id: str, state: str) -> None:
        """Persist the validated Orchestrator state transition for crash review."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE execution_runs SET state=? WHERE task_id=?",
                (str(state)[:30], task_id),
            )

    def update_execution_plan(self, task_id: str, plan: dict[str, Any]) -> None:
        with self._connection() as conn:
            conn.execute(
                "UPDATE execution_runs SET plan_json=? WHERE task_id=?",
                (json.dumps(plan, ensure_ascii=False, default=str)[:30000], task_id),
            )

    def record_execution_step(
        self,
        *,
        task_id: str,
        step_index: int,
        attempt: int,
        agent: str,
        objective: str,
        status: str,
        started_at: float,
        finished_at: float | None = None,
        duration_ms: int | None = None,
        result: dict[str, Any] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        """Upsert each attempt; a crash leaves a visible 'running' journal row."""
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO execution_steps
                   (task_id, step_index, attempt, agent, objective, status,
                    started_at, finished_at, duration_ms, result_json, error_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_id, step_index, attempt) DO UPDATE SET
                     status=excluded.status, finished_at=excluded.finished_at,
                     duration_ms=excluded.duration_ms, result_json=excluded.result_json,
                     error_json=excluded.error_json""",
                (
                    task_id, int(step_index), int(attempt), str(agent)[:40],
                    str(objective)[:8000], str(status)[:30], float(started_at),
                    finished_at, duration_ms,
                    json.dumps(result or {}, ensure_ascii=False, default=str)[:30000],
                    json.dumps(errors or [], ensure_ascii=False, default=str)[:10000],
                ),
            )

    def finish_execution(
        self, *, task_id: str, status: str, final_agent: str, final_message: str,
        state: str | None = None,
    ) -> None:
        final_state = state or {
            "completed": "completed", "partial": "partial", "failed": "failed",
            "stopped": "cancelled", "timed_out": "timed_out",
        }.get(str(status), "failed")
        with self._connection() as conn:
            conn.execute(
                """UPDATE execution_runs SET status=?, state=?, finished_at=?,
                   final_agent=?, final_message=? WHERE task_id=?""",
                (str(status)[:30], str(final_state)[:30], time.time(), str(final_agent)[:40], str(final_message)[:12000], task_id),
            )

    def interrupted_executions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return runs that were still active at last shutdown for explicit review."""
        limit = max(1, min(int(limit), 100))
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT task_id, conversation_id, command, plan_json, status, state, started_at
                   FROM execution_runs WHERE status IN ('running', 'interrupted')
                   ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            try:
                item['plan'] = json.loads(item.pop('plan_json') or '{}')
            except (TypeError, ValueError):
                item['plan'] = {}
            output.append(item)
        return output

    def execution_steps(self, task_id: str) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT step_index, attempt, agent, objective, status, started_at,
                          finished_at, duration_ms, result_json, error_json
                   FROM execution_steps WHERE task_id=? ORDER BY step_index, attempt""",
                (task_id,),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            for key in ('result_json', 'error_json'):
                try:
                    item[key.removesuffix('_json')] = json.loads(item.pop(key) or ('{}' if key == 'result_json' else '[]'))
                except (TypeError, ValueError):
                    item[key.removesuffix('_json')] = {} if key == 'result_json' else []
            output.append(item)
        return output

    def conversation_context(self, conversation_id: str | None, limit: int = 5) -> str:
        """Return recent turns for this chat only, avoiding cross-chat leakage."""
        if not conversation_id:
            return ""
        limit = max(1, min(int(limit), 10))
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT command, agent, status, result FROM task_history
                   WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
        summary = self.get_conversation_summary(conversation_id)
        if summary:
            return "RECENT CONVERSATION SNAPSHOT (extractive; may omit older turns):\n" + summary[:5000]
        lines = []
        for row in reversed(rows):
            lines.append(f"USER: {row['command']}")
            if row["result"]:
                lines.append(f"NOVA ({row['agent']}, {row['status']}): {row['result'][:700]}")
        return "\n".join(lines)

    def save_knowledge(
        self,
        *,
        category: str,
        title: str,
        content: str,
        source_url: str = "",
        published_at: str = "",
        confidence: float = 0.55,
        tags: str = "",
    ) -> None:
        """Save a source-attributed note, with an explicit confidence and timestamp."""
        title = str(title or "").strip()[:300]
        content = str(content or "").strip()[:6000]
        if not title or not content:
            return
        confidence = max(0.0, min(float(confidence), 1.0))
        now = time.time()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO knowledge_items
                   (category, title, content, source_url, published_at, confidence, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(category, title, source_url) DO UPDATE SET
                     content=excluded.content, published_at=excluded.published_at,
                     confidence=excluded.confidence, tags=excluded.tags, updated_at=excluded.updated_at""",
                (category[:40], title, content, source_url[:2000], str(published_at or "")[:100], confidence, tags[:500], now, now),
            )

    def search_knowledge(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        tokens = [
            token for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", query.lower())
            if token not in _STOPWORDS
        ][:8]
        if not tokens:
            return []
        conditions = " OR ".join("(lower(title) LIKE ? OR lower(content) LIKE ? OR lower(tags) LIKE ?)" for _ in tokens)
        params: list[str] = []
        for token in tokens:
            pattern = f"%{token}%"
            params.extend((pattern, pattern, pattern))
        params.append(str(max(12, min(int(limit) * 5, 50))))
        with self._connection() as conn:
            rows = conn.execute(
                f"""SELECT category, title, content, source_url, published_at, confidence, updated_at
                    FROM knowledge_items WHERE {conditions}
                    ORDER BY updated_at DESC, confidence DESC LIMIT ?""",
                params,
            ).fetchall()
        now = time.time()
        ranked = []
        token_set = set(tokens)
        for row in rows:
            item = dict(row)
            title = str(item.get("title") or "").lower()
            content = str(item.get("content") or "").lower()
            tags = str(item.get("tags") or "").lower()
            title_hits = sum(token in title for token in token_set)
            content_hits = sum(token in content for token in token_set)
            tag_hits = sum(token in tags for token in token_set)
            age_days = max(0.0, (now - float(item.get("updated_at") or now)) / 86400.0)
            freshness = 1.0 / (1.0 + age_days / 45.0)
            published_at = str(item.get("published_at") or "").strip()
            publication_age_days = None
            if published_at:
                try:
                    from datetime import datetime, timezone
                    parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    publication_age_days = max(0.0, (now - parsed.timestamp()) / 86400.0)
                except (TypeError, ValueError, OverflowError):
                    publication_age_days = None
            publication_freshness = (
                1.0 / (1.0 + publication_age_days / 90.0)
                if publication_age_days is not None else 0.35
            )
            confidence = max(0.0, min(1.0, float(item.get("confidence") or 0.0)))
            item["relevance_score"] = round(
                title_hits * 3.0 + tag_hits * 1.6 + content_hits * 0.7
                + confidence * 0.8 + freshness * 0.4 + publication_freshness * 0.5, 4
            )
            item["publication_age_days"] = publication_age_days
            ranked.append(item)
        ranked.sort(key=lambda item: item["relevance_score"], reverse=True)
        return ranked[:max(1, min(int(limit), 8))]

    def set_preference(self, key: str, value: str, source: str = "user") -> None:
        key = str(key or "").strip()[:100]
        if not key:
            return
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO preferences(key, value, source, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                     source=excluded.source, updated_at=excluded.updated_at""",
                (key, str(value)[:2000], str(source)[:100], time.time()),
            )

    def get_preference(self, key: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def mark_interrupted_runs(self) -> list[str]:
        """Mark runs left active by a previous process; never replay them automatically."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT task_id FROM execution_runs WHERE status='running'"
            ).fetchall()
            task_ids = [str(row["task_id"]) for row in rows]
            if task_ids:
                conn.execute(
                    "UPDATE execution_runs SET status='interrupted', state='interrupted', finished_at=? WHERE status='running'",
                    (time.time(),),
                )
        return task_ids

    def refresh_conversation_summary(
        self, conversation_id: str, max_chars: int = 8000, source_task_id: str = ""
    ) -> str:
        """Rebuild a bounded, extractive snapshot after each completed task."""
        conversation_id = str(conversation_id or "").strip()[:160]
        if not conversation_id:
            return ""
        max_chars = max(1000, min(int(max_chars), 12000))
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT command, agent, status, result FROM task_history
                   WHERE conversation_id=? ORDER BY created_at DESC LIMIT 6""",
                (conversation_id,),
            ).fetchall()
        if not rows:
            return self.get_conversation_summary(conversation_id)
        entries = []
        for row in reversed(rows):
            entries.append(
                f"User request: {str(row['command'])[:900]}\n"
                f"NOVA ({row['agent']}, {row['status']}): {str(row['result'])[:1100]}"
            )
        # This is an extractive snapshot, not an incremental append. Rebuilding it
        # from the latest turns avoids duplicating overlapping history on every run.
        latest = "\n\n".join(entries)
        snapshot = latest[-max_chars:]
        self.save_conversation_summary(conversation_id, snapshot, source_task_id)
        return snapshot

    def save_conversation_summary(
        self, conversation_id: str, summary: str, source_task_id: str = ""
    ) -> None:
        conversation_id = str(conversation_id or "").strip()[:160]
        summary = str(summary or "").strip()[:8000]
        if not conversation_id or not summary:
            return
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO conversation_summaries
                   (conversation_id, summary, updated_at, source_task_id)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(conversation_id) DO UPDATE SET
                     summary=excluded.summary, updated_at=excluded.updated_at,
                     source_task_id=excluded.source_task_id""",
                (conversation_id, summary, time.time(), str(source_task_id or "")[:128]),
            )

    def get_conversation_summary(self, conversation_id: str | None) -> str:
        if not conversation_id:
            return ""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT summary FROM conversation_summaries WHERE conversation_id=?",
                (str(conversation_id)[:160],),
            ).fetchone()
        return str(row["summary"]) if row else ""

    def delete_conversation_memory(self, conversation_id: str) -> int:
        """Delete only conversation-scoped memory; global knowledge/preferences remain untouched."""
        conversation_id = str(conversation_id or "").strip()[:160]
        if not conversation_id:
            return 0
        with self._connection() as conn:
            history_rows = conn.execute(
                "SELECT task_id FROM task_history WHERE conversation_id=?", (conversation_id,)
            ).fetchall()
            run_rows = conn.execute(
                "SELECT task_id FROM execution_runs WHERE conversation_id=?", (conversation_id,)
            ).fetchall()
            task_ids = sorted({str(row["task_id"]) for row in (*history_rows, *run_rows)})
            conn.execute("DELETE FROM task_history WHERE conversation_id=?", (conversation_id,))
            conn.execute("DELETE FROM conversation_summaries WHERE conversation_id=?", (conversation_id,))
            for task_id in task_ids:
                conn.execute("DELETE FROM execution_steps WHERE task_id=?", (task_id,))
                conn.execute("DELETE FROM execution_runs WHERE task_id=?", (task_id,))
        return len(task_ids)

    def export_conversation_memory(self, conversation_id: str) -> dict[str, Any]:
        conversation_id = str(conversation_id or "").strip()[:160]
        if not conversation_id:
            return {"conversation_id": "", "summary": "", "turns": [], "executions": []}
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT task_id, command, agent, status, result, duration_ms, created_at
                   FROM task_history WHERE conversation_id=? ORDER BY created_at ASC""",
                (conversation_id,),
            ).fetchall()
            runs = conn.execute(
                """SELECT task_id, command, plan_json, status, state, started_at, finished_at,
                          final_agent, final_message
                   FROM execution_runs WHERE conversation_id=? ORDER BY started_at ASC""",
                (conversation_id,),
            ).fetchall()
        executions = []
        for row in runs:
            item = dict(row)
            try:
                item["plan"] = json.loads(item.pop("plan_json") or "{}")
            except (TypeError, ValueError):
                item["plan"] = {}
            item["steps"] = self.execution_steps(str(item["task_id"]))
            executions.append(item)
        return {
            "conversation_id": conversation_id,
            "summary": self.get_conversation_summary(conversation_id),
            "turns": [dict(row) for row in rows],
            "executions": executions,
        }

    def stats(self) -> dict[str, int]:
        with self._connection() as conn:
            tasks = conn.execute("SELECT COUNT(*) FROM task_history").fetchone()[0]
            knowledge = conn.execute("SELECT COUNT(*) FROM knowledge_items").fetchone()[0]
            preferences = conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0]
            executions = conn.execute("SELECT COUNT(*) FROM execution_runs").fetchone()[0]
            steps = conn.execute("SELECT COUNT(*) FROM execution_steps").fetchone()[0]
            interrupted = conn.execute("SELECT COUNT(*) FROM execution_runs WHERE status IN ('running', 'interrupted')").fetchone()[0]
            summaries = conn.execute("SELECT COUNT(*) FROM conversation_summaries").fetchone()[0]
        return {
            "tasks": int(tasks), "knowledge_items": int(knowledge),
            "preferences": int(preferences), "execution_runs": int(executions),
            "execution_steps": int(steps), "interrupted_runs": int(interrupted),
            "conversation_summaries": int(summaries),
        }
