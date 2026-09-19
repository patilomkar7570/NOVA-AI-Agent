from __future__ import annotations

import io
import json
import queue
import threading
import time
from pathlib import Path
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import agent

HOST = "127.0.0.1"
PORT = 8000
MAX_EVENTS = 500

_events: list[dict[str, Any]] = []
_events_lock = threading.Lock()

running = False
current_task = ""
task_thread: threading.Thread | None = None

# One persistent worker owns Playwright for its entire lifetime.
_task_queue: queue.Queue[str | None] = queue.Queue()
_worker_ready = threading.Event()
_worker_shutdown = threading.Event()


# Persistent chat history lives beside api.py in the AI-Agent folder.
CHAT_HISTORY_FILE = Path(__file__).resolve().parent / "chat_history.json"
_chat_lock = threading.Lock()


def load_chats() -> list[dict[str, Any]]:
    if not CHAT_HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        add_event("error", f"Could not read chat history: {exc}")
        return []


def save_chats(data: list[dict[str, Any]]) -> bool:
    try:
        CHAT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CHAT_HISTORY_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(CHAT_HISTORY_FILE)
        return True
    except Exception as exc:
        add_event("error", f"Could not save chat history: {exc}")
        return False


def make_chat_title(command: str) -> str:
    """Generate a short local title with Qwen; fall back to the prompt."""
    try:
        from ollama import chat

        response = chat(
            model=getattr(agent, "MODEL", "qwen3:8b"),
            messages=[{
                "role": "user",
                "content": (
                    "Create a short 2-6 word title for this conversation. "
                    "Return only the title.\n\n"
                    f"First prompt: {command}"
                ),
            }],
            think=False,
        )
        title = " ".join(
            str(response.message.content)
            .strip()
            .strip("\"'`")
            .split()
        )
        if title:
            return title[:80]
    except Exception as exc:
        add_event("log", f"Local title generation unavailable: {exc}")

    return " ".join(command.split()[:7])[:80] or "New Chat"


def add_event(kind: str, message: str) -> None:
    event = {
        "id": time.time_ns(),
        "kind": kind,
        "message": str(message),
        "time": time.time(),
    }
    with _events_lock:
        _events.append(event)
        if len(_events) > MAX_EVENTS:
            del _events[:-MAX_EVENTS]


class EventStream(io.TextIOBase):
    """Turn agent.py console output into frontend live events."""

    def __init__(self) -> None:
        self.buffer = ""

    def write(self, text: str) -> int:
        if not text:
            return 0

        self.buffer += text

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                add_event("log", line)

        return len(text)

    def flush(self) -> None:
        if self.buffer.strip():
            add_event("log", self.buffer.strip())
            self.buffer = ""


def worker_loop() -> None:
    """The only thread that creates and uses Playwright."""
    global running, current_task, task_thread

    task_thread = threading.current_thread()

    try:
        try:
            agent.exit_event.clear()
        except Exception:
            pass

        if not agent.start_agent():
            add_event("error", "Could not start Brave.")
            _worker_ready.set()
            return

        _worker_ready.set()
        add_event("status", "NOVA browser worker ready")

        while not _worker_shutdown.is_set():
            command = _task_queue.get()

            if command is None:
                break

            running = True
            current_task = command
            add_event("status", f"Running: {command}")

            stream = EventStream()

            try:
                with redirect_stdout(stream):
                    agent.run_task(command)

                stream.flush()
                add_event("done", "Task finished")

            except Exception as exc:
                stream.flush()
                add_event("error", f"Backend error: {exc}")

            finally:
                running = False
                current_task = ""

                try:
                    agent.stop_event.clear()
                except Exception:
                    pass

    finally:
        try:
            agent.close_browser()
        except Exception as exc:
            add_event("error", f"Browser close error: {exc}")

        running = False
        current_task = ""
        task_thread = None
        add_event("status", "NOVA browser worker stopped")


def ensure_worker() -> bool:
    if task_thread is not None and task_thread.is_alive():
        return not _worker_shutdown.is_set()

    _worker_shutdown.clear()
    _worker_ready.clear()

    worker = threading.Thread(
        target=worker_loop,
        name="NOVA-Agent-Worker",
        daemon=True,
    )
    worker.start()

    _worker_ready.wait(timeout=20)

    return task_thread is not None and task_thread.is_alive()


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(data)),
        )
        self.send_header(
            "Access-Control-Allow-Origin",
            "http://localhost:5173",
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type",
        )
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        if self.path.startswith("/api/status"):
            self._send_json(
                200,
                {
                    "ok": True,
                    "running": running,
                    "task": current_task,
                    "browserOpen": getattr(agent, "_page", None) is not None,
                    "model": getattr(agent, "MODEL", "qwen3:8b"),
                    "activeSite": getattr(agent, "ACTIVE_SITE", ""),
                    "workerAlive": (
                        task_thread is not None
                        and task_thread.is_alive()
                    ),
                },
            )
            return

        if self.path.startswith("/api/events"):
            with _events_lock:
                events = list(_events)

            self._send_json(200, {"events": events})
            return

        if self.path == "/api/chats":
            with _chat_lock:
                chats = load_chats()
            self._send_json(200, {"ok": True, "chats": chats})
            return

        if self.path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "NOVA backend",
                    "workerAlive": (
                        task_thread is not None
                        and task_thread.is_alive()
                    ),
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        if self.path == "/api/chats":
            try:
                body = self._read_json()
                command = str(body.get("command", "")).strip()
                if not command:
                    self._send_json(400, {"ok": False, "error": "Command is empty"})
                    return

                chat_id = str(time.time_ns())
                chat = {
                    "id": chat_id,
                    "title": make_chat_title(command),
                    "messages": [{
                        "role": "user",
                        "content": command,
                        "time": time.time(),
                    }],
                    "created_at": time.time(),
                    "updated_at": time.time(),
                }

                with _chat_lock:
                    chats = load_chats()
                    chats = [chat] + [item for item in chats if item.get("id") != chat_id]
                    if not save_chats(chats):
                        self._send_json(
                            500,
                            {"ok": False, "error": "Could not save chat history"},
                        )
                        return

                self._send_json(201, {"ok": True, "chat": chat})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/chats/append":
            try:
                body = self._read_json()
                chat_id = str(body.get("chat_id", "")).strip()
                command = str(body.get("command", "")).strip()

                if not chat_id or not command:
                    self._send_json(
                        400,
                        {"ok": False, "error": "chat_id and command are required"},
                    )
                    return

                with _chat_lock:
                    chats = load_chats()
                    target = next(
                        (item for item in chats if str(item.get("id")) == chat_id),
                        None,
                    )
                    if target is None:
                        self._send_json(404, {"ok": False, "error": "Chat not found"})
                        return

                    target.setdefault("messages", []).append({
                        "role": "user",
                        "content": command,
                        "time": time.time(),
                    })
                    target["updated_at"] = time.time()

                    chats = sorted(
                        chats,
                        key=lambda item: item.get("updated_at", 0),
                        reverse=True,
                    )

                    if not save_chats(chats):
                        self._send_json(
                            500,
                            {"ok": False, "error": "Could not save chat history"},
                        )
                        return

                self._send_json(200, {"ok": True, "chat": target})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/chats/delete":
            try:
                body = self._read_json()
                chat_id = str(body.get("chat_id", "")).strip()

                if not chat_id:
                    self._send_json(400, {"ok": False, "error": "chat_id is required"})
                    return

                with _chat_lock:
                    chats = load_chats()
                    new_chats = [
                        item for item in chats
                        if str(item.get("id")) != chat_id
                    ]

                    if len(new_chats) == len(chats):
                        self._send_json(404, {"ok": False, "error": "Chat not found"})
                        return

                    if not save_chats(new_chats):
                        self._send_json(
                            500,
                            {"ok": False, "error": "Could not save chat history"},
                        )
                        return

                self._send_json(200, {"ok": True, "chats": new_chats})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/task":
            try:
                body = self._read_json()
            except Exception:
                self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                return

            command = str(body.get("command", "")).strip()

            if not command:
                self._send_json(
                    400,
                    {"ok": False, "error": "Command is empty"},
                )
                return

            if running:
                self._send_json(
                    409,
                    {"ok": False, "error": "A task is already running"},
                )
                return

            if not ensure_worker():
                self._send_json(
                    503,
                    {
                        "ok": False,
                        "error": "NOVA browser worker could not start",
                    },
                )
                return

            _task_queue.put(command)

            self._send_json(
                202,
                {"ok": True, "message": "Task queued"},
            )
            return

        if self.path == "/api/stop":
            try:
                agent.stop_agent()
                add_event("status", "Stop requested")
                self._send_json(
                    200,
                    {"ok": True, "message": "Stop requested"},
                )
            except Exception as exc:
                self._send_json(
                    500,
                    {"ok": False, "error": str(exc)},
                )
            return

        if self.path == "/api/close":
            try:
                # Match the old ESC behavior: stop the current task and
                # close the browser worker. The API process itself stays
                # alive so NOVA can start a fresh worker on the next task.
                agent.stop_agent()
                try:
                    agent.exit_event.set()
                except Exception:
                    pass

                _worker_shutdown.set()
                _task_queue.put(None)
                add_event("status", "NOVA agent close requested")

                worker = task_thread
                if worker is not None and worker.is_alive():
                    worker.join(timeout=10)

                self._send_json(
                    200,
                    {"ok": True, "message": "NOVA agent closed"},
                )
            except Exception as exc:
                self._send_json(
                    500,
                    {"ok": False, "error": str(exc)},
                )
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[NOVA API] {format % args}")


def main() -> None:
    global _worker_shutdown

    print("=" * 60)
    print("NOVA BACKEND")
    print(f"API: http://{HOST}:{PORT}")
    print("Frontend: http://localhost:5173")
    print("Model: " + str(getattr(agent, "MODEL", "qwen3:8b")))
    print("Architecture: Persistent single Playwright worker")
    print("=" * 60)

    if not ensure_worker():
        print("❌ NOVA worker failed to start.")
        return

    print("Waiting for tasks from the NOVA frontend...\n")

    server = ThreadingHTTPServer((HOST, PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NOVA backend...")
    finally:
        _worker_shutdown.set()
        _task_queue.put(None)

        worker = task_thread
        if worker is not None and worker.is_alive():
            worker.join(timeout=10)

        server.server_close()


if __name__ == "__main__":
    main()
