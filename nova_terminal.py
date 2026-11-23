"""Interactive Streaming Terminal & Shell Engine for NOVA AI Agent.

Provides persistent pseudo-terminal sessions with bidirectional stdin/stdout streaming,
ANSI color output buffering, interactive prompt support ([y/N], selections), and
graceful process lifecycle management on Windows.
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from typing import Any


class TerminalSession:
    """Represents a persistent interactive shell session."""

    def __init__(
        self,
        session_id: str,
        cwd: str | None = None,
        shell: str = "powershell.exe",
        env: dict[str, str] | None = None,
        is_mock: bool = False,
    ):
        self.session_id = session_id
        self.cwd = cwd or os.getcwd()
        self.shell = shell
        self.is_mock = is_mock
        self.created_at = time.time()
        self.is_alive = True
        self.exit_code: int | None = None
        self._lock = threading.Lock()
        self._output_chunks: list[dict[str, Any]] = []
        self._seq = 0
        self._input_queue: queue.Queue[str] = queue.Queue()
        self.proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None

        if not self.is_mock:
            self._start_process(env)
        else:
            self._append_output(f"\x1b[32m[NOVA Sandbox Terminal Ready - {self.shell}]\x1b[0m\r\n")

    def _start_process(self, env: dict[str, str] | None = None):
        """Spawns an interactive shell process with unbuffered pipes."""
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        run_env["PYTHONUNBUFFERED"] = "1"
        run_env["TERM"] = "xterm-256color"

        # On Windows, powershell.exe with -NoLogo and -NoExit works cleanly as an interactive shell
        cmd = [self.shell]
        if "powershell" in self.shell.lower():
            cmd = ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass"]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.cwd,
                env=run_env,
                bufsize=0,
            )
            self._reader_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
            self._reader_thread.start()
        except Exception as exc:
            self.is_alive = False
            self.exit_code = -1
            self._append_output(f"\x1b[31mFailed to start shell {self.shell}: {exc}\x1b[0m\r\n")

    def _read_stdout_loop(self):
        """Continuous background reader loop consuming pipe output."""
        if not self.proc or not self.proc.stdout:
            return

        try:
            while self.is_alive and self.proc.poll() is None:
                # Read chunks up to 4KB
                chunk = self.proc.stdout.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                self._append_output(text)
        except Exception as exc:
            self._append_output(f"\r\n\x1b[33m[Stream reader closed: {exc}]\x1b[0m\r\n")
        finally:
            self.is_alive = False
            if self.proc:
                self.exit_code = self.proc.poll()
            self._append_output(f"\r\n\x1b[90m[Process exited with code {self.exit_code}]\x1b[0m\r\n")

    def _append_output(self, text: str):
        with self._lock:
            self._seq += 1
            chunk = {
                "seq": self._seq,
                "text": text,
                "timestamp": time.time(),
            }
            self._output_chunks.append(chunk)
            # Keep maximum 5,000 chunks to prevent memory bloat
            if len(self._output_chunks) > 5000:
                self._output_chunks = self._output_chunks[-3000:]

    def write_input(self, text: str, append_newline: bool = True) -> bool:
        """Sends keystrokes or command lines into stdin."""
        payload = text + ("\r\n" if append_newline and not text.endswith("\n") else "")
        if self.is_mock:
            self._append_output(f"\x1b[36m> {text.strip()}\x1b[0m\r\n")
            if text.strip().lower() in ("y", "yes", "proceed"):
                self._append_output("\x1b[32mProceeding with installation... [OK]\x1b[0m\r\n")
            elif "npm" in text or "build" in text:
                self._append_output("\x1b[34m[Vite Build v8.3.5]\x1b[0m ✓ built in 380ms\r\n")
            elif text.strip() == "exit":
                self.is_alive = False
                self.exit_code = 0
                self._append_output("\x1b[90m[Process exited with code 0]\x1b[0m\r\n")
            return True

        if not self.is_alive or not self.proc or not self.proc.stdin:
            return False

        try:
            self.proc.stdin.write(payload.encode("utf-8", errors="replace"))
            self.proc.stdin.flush()
            return True
        except Exception:
            return False

    def get_output(self, since_seq: int = 0) -> dict[str, Any]:
        """Returns all output chunks since a specific sequence number."""
        with self._lock:
            if since_seq <= 0:
                recent = self._output_chunks[-500:] if len(self._output_chunks) > 500 else list(self._output_chunks)
            else:
                recent = [c for c in self._output_chunks if c["seq"] > since_seq]

            combined_text = "".join(c["text"] for c in recent)
            latest_seq = self._seq
            return {
                "ok": True,
                "session_id": self.session_id,
                "seq": latest_seq,
                "chunks_count": len(recent),
                "text": combined_text,
                "is_alive": self.is_alive if not self.proc else (self.proc.poll() is None),
                "exit_code": self.exit_code if not self.proc else self.proc.poll(),
            }

    def kill(self):
        """Terminates the shell session."""
        self.is_alive = False
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                time.sleep(0.05)
                if self.proc.poll() is None:
                    self.proc.kill()
            except Exception:
                pass


class TerminalManager:
    """Singleton manager tracking live terminal sessions."""

    def __init__(self):
        self._sessions: dict[str, TerminalSession] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        cwd: str | None = None,
        shell: str = "powershell.exe",
        env: dict[str, str] | None = None,
    ) -> TerminalSession:
        is_mock = os.environ.get("NOVA_TEST_MODE") == "1"
        session_id = str(uuid.uuid4())[:8]
        session = TerminalSession(session_id=session_id, cwd=cwd, shell=shell, env=env, is_mock=is_mock)
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> TerminalSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "session_id": s.session_id,
                    "cwd": s.cwd,
                    "shell": s.shell,
                    "created_at": s.created_at,
                    "is_alive": s.is_alive if not s.proc else (s.proc.poll() is None),
                    "exit_code": s.exit_code if not s.proc else s.proc.poll(),
                }
                for s in self._sessions.values()
            ]

    def kill_session(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            session.kill()
            return True
        return False

    def kill_all(self):
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for s in sessions:
            s.kill()


# Global terminal manager instance
terminal_manager = TerminalManager()
