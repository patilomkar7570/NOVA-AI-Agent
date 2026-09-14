from __future__ import annotations

import io
import json
import threading
import time
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import agent

HOST = "127.0.0.1"
PORT = 8000
MAX_EVENTS = 500

_events: list[dict[str, Any]] = []
_events_lock = threading.Lock()
task_lock = threading.Lock()
task_thread: threading.Thread | None = None
running = False
current_task = ""


class EventStream(io.TextIOBase):
    """Turns the existing agent.py console output into frontend events."""

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


def run_agent_task(command: str) -> None:
    global running, current_task, task_thread

    running = True
    current_task = command
    add_event("status", f"Running: {command}")

    try:
        stream = EventStream()
        with redirect_stdout(stream):
            agent.run_task(command)
        stream.flush()
        add_event("done", "Task finished")
    except Exception as exc:
        add_event("error", f"Backend error: {exc}")
    finally:
        running = False
        current_task = ""
        task_thread = None


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
            self._send_json(200, {
                "ok": True,
                "running": running,
                "task": current_task,
                "browserOpen": getattr(agent, "_page", None) is not None,
                "model": getattr(agent, "MODEL", "qwen3:8b"),
            })
            return

        if self.path.startswith("/api/events"):
            with _events_lock:
                events = list(_events)
            self._send_json(200, {"events": events})
            return

        if self.path == "/api/health":
            self._send_json(200, {"ok": True, "service": "NOVA backend"})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        global task_thread

        if self.path == "/api/task":
            try:
                body = self._read_json()
            except Exception:
                self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                return

            command = str(body.get("command", "")).strip()
            if not command:
                self._send_json(400, {"ok": False, "error": "Command is empty"})
                return

            if running or task_lock.locked():
                self._send_json(409, {"ok": False, "error": "A task is already running"})
                return

            def worker() -> None:
                with task_lock:
                    run_agent_task(command)

            task_thread = threading.Thread(target=worker, daemon=True)
            task_thread.start()
            self._send_json(202, {"ok": True, "message": "Task started"})
            return

        if self.path == "/api/stop":
            try:
                agent.stop_agent()
                add_event("status", "Stop requested")
                self._send_json(200, {"ok": True, "message": "Stop requested"})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[NOVA API] {format % args}")


def main() -> None:
    print("=" * 60)
    print("NOVA BACKEND")
    print(f"API: http://{HOST}:{PORT}")
    print("Frontend: http://localhost:5173")
    print("Model: " + str(getattr(agent, "MODEL", "qwen3:8b")))
    print("=" * 60)
    print("Waiting for tasks from the NOVA frontend...\n")

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NOVA backend...")
    finally:
        try:
            agent.close_browser()
        except Exception:
            pass
        server.server_close()


if __name__ == "__main__":
    main()
