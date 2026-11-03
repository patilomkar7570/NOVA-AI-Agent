from __future__ import annotations

import io
import json
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit, quote
import sys

# Resolve imports relative to this api.py file, not the shell's current folder.
# The second location supports the original foundation ZIP's nested folder layout.
PROJECT_ROOT = Path(__file__).resolve().parent
FOUNDATION_ROOT_CANDIDATES = (
    PROJECT_ROOT,
    PROJECT_ROOT / "NOVA_MultiAgent_Foundation",
)

for _candidate in FOUNDATION_ROOT_CANDIDATES:
    if (_candidate / "nova_agents" / "__init__.py").is_file():
        _candidate_str = str(_candidate)
        if _candidate_str not in sys.path:
            sys.path.insert(0, _candidate_str)
        break
else:
    _expected = "\n  - ".join(str(p / "nova_agents" / "__init__.py") for p in FOUNDATION_ROOT_CANDIDATES)
    raise ModuleNotFoundError(
        "NOVA multi-agent package 'nova_agents' was not found. Checked:\n  - "
        + _expected
        + "\nExtract the foundation ZIP into the project folder, or place its nova_agents folder beside api.py."
    )

import agent
from nova_agents import Orchestrator, agent_catalog
from nova_agents.version import APP_NAME, APP_VERSION, BUILD_LABEL, RELEASE_CHANNEL

HOST = "127.0.0.1"
PORT = 8000
MAX_EVENTS = 500

# Voicebox is an optional local service. NOVA's normal chat/task routes do not
# depend on it being open. Override this URL with NOVA_VOICEBOX_URL if needed.
VOICEBOX_BASE_URL = os.environ.get(
    "NOVA_VOICEBOX_URL", "http://127.0.0.1:17493"
).rstrip("/")
VOICEBOX_MAX_AUDIO_BYTES = 12 * 1024 * 1024
_VOICEBOX_SCHEMA_CACHE: dict[str, Any] | None = None
_VOICEBOX_SCHEMA_CACHE_AT = 0.0
_VOICEBOX_SCHEMA_CACHE_LOCK = threading.Lock()
_VOICEBOX_SCHEMA_CACHE_TTL = 60.0


def _voicebox_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8", errors="replace"))
        return value if isinstance(value, dict) else {"detail": value}
    except (ValueError, UnicodeDecodeError):
        return {"detail": raw.decode("utf-8", errors="replace")[:1000]}


def _voicebox_openapi_schema() -> dict[str, Any] | None:
    """Read and briefly cache Voicebox's live schema for version-safe calls.

    TTS is generated sentence-by-sentence, so fetching /openapi.json before
    every sentence would add avoidable latency. Cache both success and failure
    for a short interval; a service restart is picked up after the TTL.
    """
    global _VOICEBOX_SCHEMA_CACHE, _VOICEBOX_SCHEMA_CACHE_AT
    now = time.monotonic()
    with _VOICEBOX_SCHEMA_CACHE_LOCK:
        cache_ttl = _VOICEBOX_SCHEMA_CACHE_TTL if _VOICEBOX_SCHEMA_CACHE is not None else 5.0
        if now - _VOICEBOX_SCHEMA_CACHE_AT < cache_ttl:
            return _VOICEBOX_SCHEMA_CACHE
        try:
            request = urllib.request.Request(
                f"{VOICEBOX_BASE_URL}/openapi.json",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read(4 * 1024 * 1024).decode("utf-8", errors="replace"))
            _VOICEBOX_SCHEMA_CACHE = payload if isinstance(payload, dict) else None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            _VOICEBOX_SCHEMA_CACHE = None
        _VOICEBOX_SCHEMA_CACHE_AT = now
        return _VOICEBOX_SCHEMA_CACHE


def _voicebox_resolve_schema_node(document: dict[str, Any], node: Any, depth: int = 0) -> dict[str, Any]:
    """Resolve local OpenAPI refs and composed schemas without assuming one generator version."""
    if not isinstance(node, dict) or depth > 12:
        return {}
    resolved: dict[str, Any] = {key: value for key, value in node.items() if key not in {"$ref", "allOf", "anyOf", "oneOf"}}
    ref = node.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        current: Any = document
        for raw_segment in ref[2:].split("/"):
            segment = raw_segment.replace("~1", "/").replace("~0", "~")
            current = current.get(segment) if isinstance(current, dict) else None
        if isinstance(current, dict):
            base = _voicebox_resolve_schema_node(document, current, depth + 1)
            resolved = {**base, **resolved}
    for composition_key in ("allOf", "anyOf", "oneOf"):
        members = node.get(composition_key)
        if isinstance(members, list):
            for member in members:
                extra = _voicebox_resolve_schema_node(document, member, depth + 1)
                if extra:
                    merged_properties = {**(resolved.get("properties") or {}), **(extra.get("properties") or {})}
                    resolved = {**extra, **resolved}
                    if merged_properties:
                        resolved["properties"] = merged_properties
                    resolved["required"] = list(dict.fromkeys([*(extra.get("required") or []), *(resolved.get("required") or [])]))
    return resolved


def _voicebox_request_properties(schema: dict[str, Any] | None, path: str, method: str = "post") -> tuple[dict[str, Any], set[str]] | None:
    if not isinstance(schema, dict):
        return None
    operation = (((schema.get("paths") or {}).get(path) or {}).get(method.lower()) or {})
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    media = content.get("multipart/form-data") or content.get("application/json") or {}
    request_schema = _voicebox_resolve_schema_node(schema, media.get("schema") or {})
    properties = request_schema.get("properties") or {}
    required = set(request_schema.get("required") or [])
    return properties, required


def _voicebox_transcription_upload_candidates(properties: dict[str, Any], required: set[str]) -> list[str]:
    """Find the multipart file key across Voicebox/OpenAPI versions.

    Some Voicebox builds publish ``file`` as format=binary; others use ``audio``.
    A few OpenAPI 3.1 generators omit format=binary while retaining a conventional
    upload property name. Prefer schema-declared keys, then try documented aliases.
    """
    aliases = ("file", "audio", "audio_file", "recording", "upload", "audio_data", "wav_file")
    declared = [name for name in aliases if name in properties]
    binary = [
        name for name, item in properties.items()
        if isinstance(item, dict) and (
            item.get("format") in {"binary", "byte"}
            or str(item.get("contentMediaType") or "").lower().startswith("audio/")
            or item.get("type") == "file"
        )
    ]
    # Include both documented Voicebox field names after schema-declared choices.
    # This handles a stale/partial OpenAPI schema without silently assuming that
    # one particular Voicebox release's request contract is installed.
    candidates = list(dict.fromkeys([*declared, *binary, "file", "audio"]))
    return candidates


def _voicebox_validation_mentions_upload(payload: dict[str, Any], candidates: list[str]) -> bool:
    detail = payload.get("detail")
    if not isinstance(detail, list):
        return False
    for item in detail:
        if not isinstance(item, dict):
            continue
        location = item.get("loc") or []
        message = str(item.get("msg") or "").lower()
        if "body" in location and any(field in location for field in candidates) and (
            "required" in message or "missing" in message
        ):
            return True
    return False


def _voicebox_multipart(audio: bytes, file_field: str, fields: dict[str, str]) -> tuple[str, bytes]:
    boundary = f"----NOVA-Voicebox-{uuid.uuid4().hex}"
    chunks = [
        f"--{boundary}\r\n".encode("ascii"),
        (f'Content-Disposition: form-data; name="{file_field}"; filename="nova-recording.wav"\r\n').encode("ascii"),
        b"Content-Type: audio/wav\r\n\r\n", audio, b"\r\n",
    ]
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode("ascii"),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
            str(value).encode("utf-8"), b"\r\n",
        ])
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return boundary, b"".join(chunks)


def _post_voicebox_transcription(audio: bytes, file_field: str, fields: dict[str, str], endpoint: str = "/transcribe") -> tuple[int, dict[str, Any]]:
    boundary, body = _voicebox_multipart(audio, file_field, fields)
    request = urllib.request.Request(
        f"{VOICEBOX_BASE_URL}{endpoint}", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return int(response.status), _voicebox_json(response.read(2 * 1024 * 1024))
    except urllib.error.HTTPError as exc:
        return int(exc.code), _voicebox_json(exc.read(64 * 1024))


def _transcript_from_voicebox(payload: dict[str, Any]) -> str:
    for key in ("text", "transcript_refined", "transcript_raw", "transcript"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def transcribe_with_voicebox(audio: bytes, language: str = "auto") -> tuple[int, dict[str, Any]]:
    """Transcribe WAV audio and pass an explicit Whisper language hint when selected."""
    from nova_agents.language import normalize_language

    selected_language = normalize_language(language, default="auto")
    if not audio or len(audio) < 44:
        return 400, {"ok": False, "error": "The microphone recording is empty."}
    if len(audio) > VOICEBOX_MAX_AUDIO_BYTES:
        return 413, {"ok": False, "error": "The recording is too large. Keep it below 12 MB and retry."}
    if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return 415, {"ok": False, "error": "NOVA received an invalid WAV recording. Please record again."}

    spec = _voicebox_openapi_schema()
    request_info = _voicebox_request_properties(spec, "/transcribe")
    if request_info:
        properties, _required = request_info
        upload_candidates = _voicebox_transcription_upload_candidates(properties, _required)
        fields: dict[str, str] = {}
        if "model_size" in properties:
            fields["model_size"] = str((properties.get("model_size") or {}).get("default") or "base")
        if selected_language != "auto":
            if "language" not in properties:
                return 409, {"ok": False, "error": "This Voicebox version does not expose a Whisper language hint. Update Voicebox to use a fixed conversation language."}
            fields["language"] = selected_language

        status, payload = 422, {}
        for index, file_field in enumerate(upload_candidates):
            attempt_fields = dict(fields)
            status, payload = _post_voicebox_transcription(audio, file_field, attempt_fields)
            if status == 422 and "model_size" in attempt_fields:
                # Some older Voicebox builds expose a /transcribe endpoint but
                # do not accept model_size as a form field.
                attempt_fields.pop("model_size", None)
                status, payload = _post_voicebox_transcription(audio, file_field, attempt_fields)
            if status in {404, 405}:
                continue
            if status == 422 and _voicebox_validation_mentions_upload(payload, upload_candidates):
                continue
            break
    else:
        # Compatibility path for releases without a readable OpenAPI schema.
        candidates = [("file", {**({"language": selected_language} if selected_language != "auto" else {}), "model_size": "base"})]
        candidates.append(("audio", {**({"language": selected_language} if selected_language != "auto" else {}), "model_size": "base"}))
        status, payload = 404, {}
        for file_field, fields in candidates:
            try:
                status, payload = _post_voicebox_transcription(audio, file_field, fields)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                return 503, {"ok": False, "error": "Voicebox is not reachable. Open Voicebox and retry local transcription.", "detail": str(exc)}
            if status == 422 and "model_size" in fields:
                retry_fields = dict(fields)
                retry_fields.pop("model_size", None)
                status, payload = _post_voicebox_transcription(audio, file_field, retry_fields)
            if status in {404, 405}:
                continue
            if status == 422 and _voicebox_validation_mentions_upload(payload, ["file", "audio"]):
                continue
            break

    if status in {404, 405} and selected_language == "auto":
        # Legacy /captures cannot carry a selected Whisper language reliably.
        try:
            status, payload = _post_voicebox_transcription(audio, "file", {"source": "recording"}, endpoint="/captures")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return 503, {"ok": False, "error": "Voicebox is not reachable. Open Voicebox and retry local transcription.", "detail": str(exc)}

    if not 200 <= status < 300:
        detail = payload.get("detail")
        if isinstance(detail, list):
            detail = "; ".join(str(item.get("msg") or item) if isinstance(item, dict) else str(item) for item in detail[:3])
        return status if status >= 400 else 502, {
            "ok": False,
            "error": str(detail or payload.get("error") or payload.get("message") or f"Voicebox transcription failed with HTTP {status}."),
            "detail": payload,
        }
    transcript = _transcript_from_voicebox(payload)
    if not transcript:
        return 502, {"ok": False, "error": "Voicebox accepted the recording but returned no transcription text.", "detail": payload}
    return 200, {
        "ok": True, "text": transcript,
        "language": str(payload.get("language") or selected_language),
        "transcript_raw": payload.get("transcript_raw", transcript),
        "transcript_refined": payload.get("transcript_refined"),
        "capture_id": payload.get("id") or payload.get("capture_id"),
        "engine": "Voicebox Whisper",
        "duration": payload.get("duration"),
    }


_events: list[dict[str, Any]] = []
_events_lock = threading.Lock()
_event_sequence = 0

running = False
current_task = ""
task_thread: threading.Thread | None = None
active_agent = ""
current_task_id = ""
_orchestrator_memory = None

# Cancellation is correlated to the task ID. The legacy agent.stop_event remains
# a cooperative bridge for agent.py and Playwright operations.
_task_cancel_events: dict[str, threading.Event] = {}

# One persistent worker owns Playwright for its entire lifetime.
_task_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
_worker_ready = threading.Event()
_worker_shutdown = threading.Event()

# Results are retained briefly so the React client can fetch the final reply
# after the browser/research specialist finishes. Chat messages themselves are
# persisted separately in chat_history.json.
_task_records: dict[str, dict[str, Any]] = {}
_task_records_lock = threading.Lock()
_task_submission_lock = threading.Lock()
_MAX_TASK_RECORDS = 100

# A single persistent worker handles one task at a time, so one pending
# confirmation at a time is sufficient. Decisions are correlated by both task
# and approval IDs to prevent stale approvals from unlocking another action.
_approval_condition = threading.Condition()
_pending_approvals: dict[str, dict[str, Any]] = {}
_APPROVAL_TIMEOUT_SECONDS = 120

def update_task_record(task_id: str, **updates: Any) -> None:
    with _task_records_lock:
        record = _task_records.get(task_id)
        if record is not None:
            record.update(updates)
            record["updated_at"] = time.time()


def resolve_user_approval(approval_id: str, task_id: str, decision: str) -> tuple[bool, str]:
    """Resolve one live approval; a stale or cross-task ID cannot approve work."""
    approval_id = str(approval_id or "").strip()
    task_id = str(task_id or "").strip()
    decision = str(decision or "").strip().lower()
    if not approval_id or not task_id or decision not in {"approve", "deny"}:
        return False, "approval_id, task_id and decision (approve/deny) are required"
    with _approval_condition:
        pending = _pending_approvals.get(approval_id)
        if pending is None or pending.get("task_id") != task_id:
            return False, "This approval request is no longer active"
        if pending.get("decision") is not None:
            return False, "This approval request has already been answered"
        pending["decision"] = decision
        pending["reason"] = "Approved by user." if decision == "approve" else "Declined by user."
        _approval_condition.notify_all()
    return True, decision


def request_user_approval(payload: dict[str, Any]) -> dict[str, Any]:
    """Pause the worker until this exact high-impact action is approved/denied."""
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return {"approved": False, "reason": "The approval request had no task ID."}

    approval_id = uuid.uuid4().hex
    public_request = {
        "approval_id": approval_id,
        "task_id": task_id,
        "agent": str(payload.get("agent") or "browser"),
        "objective": str(payload.get("objective") or "").strip()[:2000],
        "reason": str(payload.get("reason") or "").strip()[:1200],
        "risk_level": str(payload.get("risk_level") or "high"),
        "expires_in_seconds": _APPROVAL_TIMEOUT_SECONDS,
    }
    pending = {
        "task_id": task_id,
        "decision": None,
        "reason": "",
        "created_at": time.time(),
    }

    with _approval_condition:
        _pending_approvals[approval_id] = pending

    update_task_record(task_id, status="awaiting_approval", approval=public_request)
    add_event(
        "approval_required",
        "NOVA needs your approval before it can perform this high-impact browser action.",
    )

    deadline = time.monotonic() + _APPROVAL_TIMEOUT_SECONDS
    with _approval_condition:
        while pending["decision"] is None:
            if _worker_shutdown.is_set():
                pending["decision"] = "deny"
                pending["reason"] = "NOVA is shutting down."
                break
            try:
                if agent.stop_event.is_set():
                    pending["decision"] = "deny"
                    pending["reason"] = "You stopped the task while approval was pending."
                    break
            except Exception:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                pending["decision"] = "deny"
                pending["reason"] = "The approval request expired after two minutes."
                break
            _approval_condition.wait(timeout=min(0.35, remaining))
        decision = str(pending.get("decision") or "deny")
        reason = str(pending.get("reason") or "")
        _pending_approvals.pop(approval_id, None)

    update_task_record(task_id, status="running", approval=None)
    add_event(
        "approval_decision",
        "High-impact action approved." if decision == "approve" else "High-impact action was not approved.",
    )
    return {"approved": decision == "approve", "reason": reason or ("Approved by user." if decision == "approve" else "Approval declined or expired.")}

def append_assistant_message(
    chat_id: str | None, content: str, agent_name: str, status: str, task_id: str
) -> bool:
    """Persist a specialist's final answer in the originating chat."""
    if not chat_id:
        return True
    try:
        with _chat_lock:
            chats = load_chats()
            target = next(
                (item for item in chats if str(item.get("id")) == str(chat_id)),
                None,
            )
            if target is None:
                add_event("error", f"Could not save NOVA's reply: chat {chat_id} was not found.")
                return False
            target.setdefault("messages", []).append({
                "role": "assistant",
                "content": str(content or "").strip(),
                "time": time.time(),
                "agent": agent_name,
                "status": status,
                "task_id": task_id,
            })
            target["updated_at"] = time.time()
            chats.sort(key=lambda item: item.get("updated_at", 0), reverse=True)
            return save_chats(chats)
    except Exception as exc:
        add_event("error", f"Could not save NOVA's reply: {exc}")
        return False


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


def add_event(
    kind: str,
    message: str,
    *,
    task_id: str | None = None,
    agent_id: str | None = None,
    step: int | None = None,
    event_name: str | None = None,
) -> None:
    """Append a backward-compatible event with task-scoped execution metadata."""
    global _event_sequence
    now = time.time()
    event = {
        "kind": str(kind or "log"),
        "event": str(event_name or kind or "log"),
        "message": str(message),
        "time": now,
        "task_id": str(task_id or current_task_id or "") or None,
        "agent": str(agent_id or active_agent or "") or None,
        "step": step,
    }
    with _events_lock:
        _event_sequence += 1
        event["id"] = _event_sequence
        _events.append(event)
        if len(_events) > MAX_EVENTS:
            del _events[:-MAX_EVENTS]


class EventStream(io.TextIOBase):
    """Turn agent.py console output into frontend live events."""

    def __init__(self, task_id: str | None = None) -> None:
        self.buffer = ""
        self.task_id = task_id

    def write(self, text: str) -> int:
        if not text:
            return 0

        self.buffer += text

        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                add_event("log", line, task_id=self.task_id)

        return len(text)

    def flush(self) -> None:
        if self.buffer.strip():
            add_event("log", self.buffer.strip(), task_id=self.task_id)
            self.buffer = ""


def worker_loop() -> None:
    """Single queue worker; Browser/Research initialise Brave only on demand."""
    global running, current_task, task_thread, active_agent, current_task_id, _orchestrator_memory

    task_thread = threading.current_thread()

    def orchestrator_event(kind: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        global active_agent
        details = metadata if isinstance(metadata, dict) else {}
        event_task_id = str(details.get("task_id") or current_task_id or "") or None
        event_agent = str(details.get("agent") or "") or None
        event_step = details.get("step") if isinstance(details.get("step"), int) else None
        event_name = str(details.get("event") or kind)
        if event_agent:
            active_agent = event_agent
        if kind == "state" and event_task_id:
            update_task_record(event_task_id, execution_state=event_name)
        add_event(
            kind, message, task_id=event_task_id, agent_id=event_agent,
            step=event_step, event_name=event_name,
        )

    orchestrator = Orchestrator(
        agent, event_callback=orchestrator_event, approval_callback=request_user_approval
    )
    _orchestrator_memory = orchestrator.memory

    try:
        try:
            agent.exit_event.clear()
        except Exception:
            pass

        # Mark crash-left executions for review, never replay them automatically.
        try:
            interrupted = orchestrator.memory.mark_interrupted_runs()
            for interrupted_id in interrupted:
                add_event(
                    "warning", f"An earlier task was interrupted and is available for review: {interrupted_id}",
                    task_id=interrupted_id, event_name="execution_interrupted",
                )
        except Exception as exc:
            add_event("warning", f"Could not reconcile the prior execution journal: {exc}")

        # Do not start Brave here. General Chat/Reaction remains functional even
        # when the browser executable, profile or Playwright runtime is unavailable.
        _worker_ready.set()
        add_event("status", "NOVA multi-agent worker ready · browser starts only when required")

        while not _worker_shutdown.is_set():
            task_item = _task_queue.get()
            if task_item is None:
                break

            command = str(task_item.get("command", "")).strip()
            chat_id = str(task_item.get("chat_id", "")).strip() or None
            task_id = str(task_item.get("task_id", "")).strip()
            cancel_event = task_item.get("cancel_event")
            if not isinstance(cancel_event, threading.Event):
                cancel_event = threading.Event()
                with _task_records_lock:
                    _task_cancel_events[task_id] = cancel_event

            running = True
            current_task = command
            current_task_id = task_id
            active_agent = "planner"
            update_task_record(
                task_id, status="running", execution_state="planning", started_at=time.time()
            )
            add_event("status", f"Running: {command}", task_id=task_id, event_name="task_started")

            stream = EventStream(task_id=task_id)
            result = None
            reply = "NOVA could not produce a response for this request."
            final_status = "failed"
            final_agent = "planner"
            errors: list[str] = []

            try:
                with redirect_stdout(stream):
                    voice_stream = bool(task_item.get("voice_stream"))
                    def forward_voice_delta(delta: str) -> None:
                        if not delta:
                            return
                        add_event(
                            "assistant_delta",
                            delta,
                            task_id=task_id,
                            agent_id="chat",
                            event_name="assistant_token",
                        )

                    result = orchestrator.execute(
                        command,
                        conversation_id=chat_id,
                        task_id=task_id,
                        cancellation_event=cancel_event,
                        response_callback=forward_voice_delta if voice_stream else None,
                        language=str(task_item.get("language") or "en"),
                    )

                stream.flush()
                if result is not None:
                    final_agent = str(result.agent or "planner")
                    final_status = str(result.status or "failed")
                    reply = str(result.message or "").strip() or reply
                    errors = [str(item) for item in (result.errors or []) if str(item).strip()]
                    active_agent = final_agent
                    if final_status == "failed" and errors:
                        reply = reply.rstrip() + "\n\nDetails: " + "\n".join(errors[:3])
                else:
                    errors.append("The orchestrator returned no result.")

                saved = append_assistant_message(chat_id, reply, final_agent, final_status, task_id)
                if chat_id and not saved:
                    errors.append("The response was generated but could not be saved to chat history.")
                if chat_id:
                    try:
                        orchestrator.memory.refresh_conversation_summary(chat_id, source_task_id=task_id)
                    except Exception as memory_exc:
                        add_event(
                            "warning", f"Conversation summary refresh failed: {memory_exc}",
                            task_id=task_id, event_name="memory_summary_warning",
                        )

                task_result = {
                    "task_id": task_id,
                    "agent": final_agent,
                    "status": final_status,
                    "reply": reply,
                    "errors": errors,
                    "duration_ms": result.duration_ms if result is not None else None,
                    "chat_saved": saved,
                    "execution_steps": (result.data or {}).get("execution_steps", []) if result is not None and isinstance(result.data, dict) else [],
                    "execution_journal": (result.data or {}).get("execution_journal", {}) if result is not None and isinstance(result.data, dict) else {},
                }
                update_task_record(
                    task_id, status=final_status, execution_state={
                        "completed": "completed", "partial": "partial", "failed": "failed",
                        "stopped": "cancelled", "timed_out": "timed_out",
                    }.get(final_status, "failed"), agent=final_agent,
                    reply=reply, result=task_result, errors=errors,
                    finished_at=time.time(),
                )
                add_event(
                    "log",
                    f"Task result · agent={final_agent} · status={final_status} · "
                    f"duration={task_result['duration_ms']}ms",
                    task_id=task_id, agent_id=final_agent, event_name="task_result",
                )
                for error in errors:
                    add_event("error", error, task_id=task_id, agent_id=final_agent)
                add_event("done", f"Task finished · {final_agent} · {final_status}", task_id=task_id)

            except Exception as exc:
                stream.flush()
                error_text = f"{type(exc).__name__}: {exc}"
                errors.append(error_text)
                reply = "I ran into an error while processing that request.\n\nDetails: " + error_text
                append_assistant_message(chat_id, reply, final_agent, "failed", task_id)
                task_result = {
                    "task_id": task_id, "agent": final_agent, "status": "failed",
                    "reply": reply, "errors": errors, "duration_ms": None,
                    "chat_saved": bool(chat_id),
                }
                update_task_record(
                    task_id, status="failed", execution_state="failed", agent=final_agent,
                    reply=reply, result=task_result, errors=errors, finished_at=time.time(),
                )
                add_event("error", f"Backend error: {error_text}", task_id=task_id)

            finally:
                running = False
                current_task = ""
                current_task_id = ""
                active_agent = ""
                with _task_records_lock:
                    _task_cancel_events.pop(task_id, None)
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
        current_task_id = ""
        active_agent = ""
        task_thread = None
        _worker_ready.set()
        add_event("status", "NOVA worker stopped")


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


def enqueue_task(command: str, chat_id: str, voice_stream: bool = False, language: str = "en") -> tuple[int, dict[str, Any]]:
    """Atomically accept one task so concurrent HTTP requests cannot overfill the worker."""
    from nova_agents.language import normalize_language
    language = normalize_language(language, default="en")
    with _task_submission_lock:
        with _task_records_lock:
            active_jobs = running or any(
                item.get("status") in {"queued", "running", "awaiting_approval"}
                for item in _task_records.values()
            )
        if active_jobs:
            return 409, {"ok": False, "error": "A task is already running"}
        if not ensure_worker():
            return 503, {"ok": False, "error": "NOVA task worker could not start"}

        task_id = uuid.uuid4().hex
        cancel_event = threading.Event()
        task_record = {
            "task_id": task_id, "chat_id": chat_id, "command": command, "language": language,
            "status": "queued", "execution_state": "queued", "agent": None, "reply": None,
            "result": None, "errors": [], "created_at": time.time(),
            "updated_at": time.time(),
        }
        with _task_records_lock:
            _task_cancel_events[task_id] = cancel_event
            _task_records[task_id] = task_record
            if len(_task_records) > _MAX_TASK_RECORDS:
                finished = [
                    key for key, value in _task_records.items()
                    if value.get("status") not in {"queued", "running", "awaiting_approval"}
                ]
                for old_id in finished[:-_MAX_TASK_RECORDS]:
                    _task_records.pop(old_id, None)
                    _task_cancel_events.pop(old_id, None)

        _task_queue.put({
            "task_id": task_id, "command": command, "chat_id": chat_id,
            "cancel_event": cancel_event,
            "voice_stream": bool(voice_stream), "language": language,
        })
        return 202, {"ok": True, "task_id": task_id, "status": "queued"}


def capabilities_payload() -> dict[str, Any]:
    """Return the active, serialisable capability snapshot for the UI."""
    return {
        "ok": True,
        "application": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "channel": RELEASE_CHANNEL,
            "build": BUILD_LABEL,
        },
        "agents": agent_catalog(),
        "features": {
            "multi_step_orchestration": True,
            "typed_agent_handoffs": True,
            "task_state_machine": True,
            "task_scoped_cancellation": True,
            "task_scoped_events": True,
            "execution_journal": True,
            "interrupted_run_review": True,
            "browser_approval_gate": True,
            "lazy_browser_startup": True,
            "memory_export_and_delete": True,
            "bounded_partial_synthesis": True,
            "source_attributed_research": True,
            "browser_completion_verification": True,
            "durable_task_states": True,
            "runtime_diagnostics": True,
            "voice_input": True,
            "voice_response_streaming": True,
            "progressive_voice_tts": True,
            "voice_interruption_resume": True,
            "file_operations": False,
            "coding_operations": False,
            "windows_desktop_control": False,
        },
        "runtime": {
            "model": getattr(agent, "MODEL", "qwen3:8b"),
            "worker_alive": task_thread is not None and task_thread.is_alive(),
            "browser_open": getattr(agent, "_page", None) is not None,
            "active_agent": active_agent,
            "active_task_id": current_task_id or None,
            "active_site": getattr(agent, "ACTIVE_SITE", ""),
            "browser_required_for_chat": False,
        },
    }


def _probe_http(url: str, timeout: float = 1.5) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= int(response.status) < 400, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        # An HTTP response proves a local service is listening even if this
        # particular optional endpoint is not implemented by that service.
        return True, f"HTTP {exc.code} (service reachable)"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)[:300]


def diagnostics_payload() -> dict[str, Any]:
    """Read-only runtime checks. Optional components never block API startup."""
    checks: list[dict[str, Any]] = []

    ollama_url = os.environ.get("NOVA_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_ok, ollama_detail = _probe_http(f"{ollama_url}/api/version")
    selected_model = str(os.environ.get("NOVA_MODEL") or getattr(agent, "MODEL", "qwen3:8b"))
    model_detail = "Model availability was not checked because Ollama is unreachable."
    if ollama_ok:
        try:
            tags_request = urllib.request.Request(
                f"{ollama_url}/api/tags", headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(tags_request, timeout=1.5) as response:
                tags_payload = json.loads(response.read(1024 * 1024).decode("utf-8"))
            installed = {
                str(item.get("name") or "").strip()
                for item in tags_payload.get("models", []) if isinstance(item, dict)
            } if isinstance(tags_payload, dict) else set()
            model_present = selected_model in installed or f"{selected_model}:latest" in installed
            model_detail = (
                f"{selected_model} is installed" if model_present
                else f"Ollama is online, but {selected_model} was not listed by /api/tags"
            )
        except Exception as exc:
            model_detail = f"Ollama is online; model check failed: {type(exc).__name__}"
    checks.append({
        "id": "ollama", "name": "Ollama + selected model",
        "status": "available" if ollama_ok and "was not listed" not in model_detail else "unavailable",
        "required_for": ["chat", "planner", "research"],
        "detail": f"{ollama_detail}; {model_detail}",
    })

    try:
        import importlib.util
        playwright_ok = importlib.util.find_spec("playwright") is not None
    except (ImportError, ValueError):
        playwright_ok = False
    brave_candidates: list[Path] = []
    for env_key in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env_key)
        if base:
            brave_candidates.append(Path(base) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe")
    configured_brave = os.environ.get("NOVA_BRAVE_EXECUTABLE")
    if configured_brave:
        brave_candidates.insert(0, Path(configured_brave).expanduser())
    brave_path = next((item for item in brave_candidates if item.is_file()), None)
    browser_available = bool(playwright_ok and brave_path)
    checks.append({
        "id": "browser", "name": "Brave + Playwright",
        "status": "available" if browser_available else "unavailable",
        "required_for": ["browser", "research"],
        "detail": str(brave_path) if brave_path else ("Playwright installed but Brave executable was not found" if playwright_ok else "Playwright package is not installed"),
    })

    voice_ok, voice_detail = _probe_http(VOICEBOX_BASE_URL, timeout=1.0)
    checks.append({
        "id": "voicebox", "name": "Voicebox", "status": "available" if voice_ok else "optional_unavailable",
        "required_for": ["on_device_voice"], "detail": voice_detail,
    })

    memory_ok = _orchestrator_memory is not None
    memory_detail = "Shared SQLite memory is initialised" if memory_ok else "Memory service is not ready"
    if memory_ok:
        try:
            memory_detail = str(_orchestrator_memory.stats())
        except Exception as exc:
            memory_ok = False
            memory_detail = str(exc)[:300]
    checks.append({
        "id": "memory", "name": "SQLite memory", "status": "available" if memory_ok else "unavailable",
        "required_for": ["conversation_memory", "execution_journal"], "detail": memory_detail,
    })
    checks.append({
        "id": "worker", "name": "Task worker",
        "status": "available" if task_thread is not None and task_thread.is_alive() else "unavailable",
        "required_for": ["task_execution"],
        "detail": "Worker is running" if task_thread is not None and task_thread.is_alive() else "Worker is stopped",
    })

    return {
        "ok": True,
        "application": {"name": APP_NAME, "version": APP_VERSION, "build": BUILD_LABEL},
        "checked_at": time.time(),
        "components": checks,
        "summary": {
            "available": sum(item["status"] == "available" for item in checks),
            "unavailable": sum(item["status"] == "unavailable" for item in checks),
            "optional_unavailable": sum(item["status"] == "optional_unavailable" for item in checks),
        },
        "note": "Diagnostics are read-only. Browser and Voicebox are optional and do not prevent ordinary Chat startup.",
    }


VOICEBOX_MAX_TTS_CHARS = 5000
VOICEBOX_MAX_TTS_AUDIO_BYTES = 48 * 1024 * 1024
VOICEBOX_SHARED_AUDIO_DIR = PROJECT_ROOT / "runtime" / "voicebox_audio"
VOICEBOX_TTS_TIMEOUT_SECONDS = 300
_WHISPER_PRELOAD_LOCK = threading.Lock()


def _voicebox_request_json(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 15.0) -> dict[str, Any] | list[Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{VOICEBOX_BASE_URL}{path}", data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(2 * 1024 * 1024)
    parsed = json.loads(raw.decode("utf-8", errors="replace"))
    if isinstance(parsed, (dict, list)):
        return parsed
    return {"detail": parsed}


def _voicebox_audio_extension(content_type: str) -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    known = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/flac": ".flac",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/webm": ".webm",
    }
    return known.get(mime, ".wav")


def _save_voicebox_audio_for_nova(audio: bytes, content_type: str) -> tuple[bytes, str, Path]:
    """Persist Voicebox output in NOVA's own readable runtime folder, then reopen it."""
    if not audio:
        raise ValueError("Voicebox returned an empty audio file.")
    if len(audio) > VOICEBOX_MAX_TTS_AUDIO_BYTES:
        raise ValueError("The generated audio file is too large for NOVA to play.")

    VOICEBOX_SHARED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    suffix = _voicebox_audio_extension(content_type)
    file_id = uuid.uuid4().hex
    destination = VOICEBOX_SHARED_AUDIO_DIR / f"nova_readaloud_{file_id}{suffix}"
    temporary = VOICEBOX_SHARED_AUDIO_DIR / f".{file_id}.part"

    try:
        temporary.write_bytes(audio)
        if temporary.stat().st_size != len(audio):
            raise OSError("The generated audio was not fully written to NOVA's audio folder.")
        temporary.replace(destination)
        # Read the saved file back from disk. This verifies the hand-off that
        # the NOVA UI depends on, instead of returning only Voicebox's memory buffer.
        saved_audio = destination.read_bytes()
        if not saved_audio or len(saved_audio) != len(audio):
            raise OSError("NOVA could not read back the saved Voicebox audio file.")
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass

    # Keep this hand-off folder tidy: retain the newest 20 generated files.
    try:
        saved_files = sorted(
            VOICEBOX_SHARED_AUDIO_DIR.glob("nova_readaloud_*")
            , key=lambda item: item.stat().st_mtime, reverse=True
        )
        for old_file in saved_files[20:]:
            try:
                old_file.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass

    mime = (content_type or "audio/wav").split(";", 1)[0].strip().lower() or "audio/wav"
    if not mime.startswith("audio/") and mime != "application/octet-stream":
        mime = "audio/wav"
    return saved_audio, mime, destination


def _stream_voicebox_audio(profile_id: str, speech_text: str, language: str, engine: str | None = None) -> tuple[bytes, str] | None:
    """Use Voicebox's direct WAV stream endpoint when the installed build supports it."""
    body = json.dumps({
        "profile_id": profile_id,
        "text": speech_text,
        "language": language,
        **({"engine": engine} if engine else {}),
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{VOICEBOX_BASE_URL}/generate/stream",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "audio/wav, audio/*"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=VOICEBOX_TTS_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "audio/wav").split(";", 1)[0].strip().lower()
            audio = response.read(VOICEBOX_MAX_TTS_AUDIO_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # Older Voicebox builds may not expose /generate/stream. In that case
        # fall through to the asynchronous /generate + history + /audio path.
        if exc.code in {404, 405, 422, 501}:
            return None
        detail = _voicebox_json(exc.read(64 * 1024))
        message = detail.get("detail") or detail.get("error") or detail.get("message")
        if isinstance(message, (dict, list)):
            message = json.dumps(message, ensure_ascii=False)
        raise RuntimeError(str(message or f"Voicebox stream generation failed (HTTP {exc.code})."))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"NOVA could not reach Voicebox's speech generator: {exc}") from exc

    if len(audio) > VOICEBOX_MAX_TTS_AUDIO_BYTES:
        raise RuntimeError("The generated audio file is too large for NOVA to play.")
    if not audio:
        raise RuntimeError("Voicebox's streaming endpoint returned an empty audio file.")
    if not content_type.startswith("audio/") and content_type != "application/octet-stream":
        detail = _voicebox_json(audio[:64 * 1024])
        message = detail.get("detail") or detail.get("error") or detail.get("message")
        raise RuntimeError(str(message or "Voicebox returned a non-audio response instead of speech."))
    return audio, content_type or "audio/wav"


def _generate_voicebox_audio_async(profile_id: str, speech_text: str, language: str, engine: str | None = None) -> tuple[bytes, str]:
    """Compatibility path for Voicebox versions without /generate/stream."""
    try:
        generation_payload = _voicebox_request_json(
            "/generate", method="POST",
            payload={"profile_id": profile_id, "text": speech_text, "language": language, **({"engine": engine} if engine else {})},
            timeout=VOICEBOX_TTS_TIMEOUT_SECONDS,
        )
    except urllib.error.HTTPError as exc:
        detail = _voicebox_json(exc.read(64 * 1024))
        message = detail.get("detail") or detail.get("error") or detail.get("message")
        raise RuntimeError(str(message or f"Voicebox speech generation failed (HTTP {exc.code}).")) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(f"Voicebox could not start speech generation: {exc}") from exc

    if not isinstance(generation_payload, dict):
        raise RuntimeError("Voicebox returned an unexpected generation response.")
    generation_id = str(generation_payload.get("id") or generation_payload.get("generation_id") or "").strip()
    if not generation_id:
        message = generation_payload.get("detail") or generation_payload.get("message") or "Voicebox did not return a generation ID."
        raise RuntimeError(str(message))

    deadline = time.monotonic() + VOICEBOX_TTS_TIMEOUT_SECONDS
    last_status = str(generation_payload.get("status") or "generating")
    last_error = ""
    while time.monotonic() < deadline:
        try:
            history = _voicebox_request_json(f"/history/{quote(generation_id, safe='')}", timeout=10)
            if isinstance(history, dict):
                record = history.get("generation") or history.get("item") or history.get("data") or history
                if isinstance(record, dict):
                    last_status = str(record.get("status") or last_status).lower()
                    last_error = str(record.get("error") or record.get("detail") or last_error)
        except urllib.error.HTTPError as exc:
            if exc.code not in {404, 409, 425}:
                last_error = f"Voicebox history returned HTTP {exc.code}."
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = str(exc)

        if last_status in {"failed", "error", "cancelled"}:
            raise RuntimeError(last_error or "Voicebox reported that speech generation failed.")

        if last_status in {"completed", "complete", "done", "ready"}:
            audio_request = urllib.request.Request(
                f"{VOICEBOX_BASE_URL}/audio/{quote(generation_id, safe='')}",
                headers={"Accept": "audio/*, application/octet-stream"},
                method="GET",
            )
            try:
                with urllib.request.urlopen(audio_request, timeout=30) as response:
                    content_type = response.headers.get("Content-Type", "audio/wav").split(";", 1)[0].strip().lower()
                    audio = response.read(VOICEBOX_MAX_TTS_AUDIO_BYTES + 1)
                if not audio:
                    raise RuntimeError("Voicebox completed generation but returned an empty audio file.")
                if len(audio) > VOICEBOX_MAX_TTS_AUDIO_BYTES:
                    raise RuntimeError("The generated audio file is too large for NOVA to play.")
                if not content_type.startswith("audio/") and content_type != "application/octet-stream":
                    raise RuntimeError("Voicebox returned a non-audio file for the completed generation.")
                return audio, content_type or "audio/wav"
            except urllib.error.HTTPError as exc:
                if exc.code not in {404, 409, 425}:
                    raise RuntimeError(f"Voicebox completed generation, but its audio endpoint returned HTTP {exc.code}.") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
        time.sleep(0.8)

    raise RuntimeError(
        f"Voicebox did not make the audio file available before the {VOICEBOX_TTS_TIMEOUT_SECONDS}-second timeout. "
        f"Last generation status: {last_status}. {last_error}".strip()
    )


def _voicebox_profile_engine(profile: dict[str, Any]) -> str:
    return str(
        profile.get("preset_engine") or profile.get("default_engine")
        or profile.get("engine") or profile.get("engine_name") or ""
    ).strip().lower().replace("-", "_")


def _voicebox_profile_is_preset(profile: dict[str, Any]) -> bool:
    return str(profile.get("voice_type") or "").lower() == "preset" or bool(profile.get("preset_engine") or profile.get("preset_voice_id"))


def _select_voicebox_profile(profiles: list[dict[str, Any]], preferred_profile_id: str | None, language: str) -> tuple[dict[str, Any] | None, str | None, str]:
    """Pick a profile and an engine compatible with the requested output language."""
    from nova_agents.language import preferred_voicebox_engine, voicebox_engine_supports_language

    usable = [item for item in profiles if isinstance(item, dict) and (item.get("id") or item.get("profile_id"))]
    if not usable:
        return None, None, "No Voicebox voice profile is available. Create or import a voice profile first."
    preferred = next((item for item in usable if str(item.get("id") or item.get("profile_id")) == str(preferred_profile_id)), None) if preferred_profile_id else None

    def profile_language(profile: dict[str, Any]) -> str:
        return str(profile.get("language") or "").lower().replace("_", "-").split("-", 1)[0]

    def preset_compatible(profile: dict[str, Any]) -> bool:
        engine = _voicebox_profile_engine(profile)
        declared = profile_language(profile)
        return bool(engine and voicebox_engine_supports_language(engine, language) and (not declared or declared == language))

    # Preset voices are locked to their engine and language.
    if preferred and _voicebox_profile_is_preset(preferred):
        if preset_compatible(preferred):
            return preferred, _voicebox_profile_engine(preferred), ""
        preferred = None

    # A cloned profile's source samples can be reused with another cloning engine.
    if preferred and not _voicebox_profile_is_preset(preferred):
        default_engine = _voicebox_profile_engine(preferred)
        engine = default_engine if voicebox_engine_supports_language(default_engine, language) else preferred_voicebox_engine(language)
        return preferred, engine, ""

    compatible_presets = [profile for profile in usable if _voicebox_profile_is_preset(profile) and preset_compatible(profile)]
    if compatible_presets:
        return compatible_presets[0], _voicebox_profile_engine(compatible_presets[0]), ""

    cloned = [profile for profile in usable if not _voicebox_profile_is_preset(profile)]
    if cloned:
        chosen = cloned[0]
        default_engine = _voicebox_profile_engine(chosen)
        engine = default_engine if voicebox_engine_supports_language(default_engine, language) else preferred_voicebox_engine(language)
        return chosen, engine, ""

    if language == "hi":
        return None, None, "No Hindi-compatible Voicebox profile is available. Hindi speech requires a Hindi Kokoro preset or a cloned profile routed through Chatterbox Multilingual. Qwen3-TTS presets cannot speak Hindi."
    language_name = {"en": "English", "de": "German", "fr": "French", "es": "Spanish", "ja": "Japanese"}.get(language, language)
    return None, None, f"No Voicebox profile is compatible with {language_name}. Select a matching preset or create a cloned voice profile."


def generate_voicebox_audio(text: str, preferred_profile_id: str | None = None, requested_language: str = "auto") -> tuple[int, bytes | None, str, dict[str, Any]]:
    """Generate speech using the selected language and a compatible Voicebox profile."""
    from nova_agents.language import detect_language_from_text, normalize_language

    speech_text = str(text or "").strip()
    if not speech_text:
        return 400, None, "audio/wav", {"ok": False, "error": "There is no response text to read aloud."}
    if len(speech_text) > VOICEBOX_MAX_TTS_CHARS:
        return 413, None, "audio/wav", {
            "ok": False,
            "error": f"This response is longer than Voicebox's {VOICEBOX_MAX_TTS_CHARS:,}-character limit.",
        }

    try:
        profiles_payload = _voicebox_request_json("/profiles", timeout=10)
    except urllib.error.HTTPError as exc:
        detail = _voicebox_json(exc.read(64 * 1024))
        return 502, None, "audio/wav", {"ok": False, "error": f"Voicebox could not list its voice profiles (HTTP {exc.code}).", "detail": detail}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return 503, None, "audio/wav", {"ok": False, "error": "Voicebox is not reachable. Make sure its local server is running.", "detail": str(exc)[:500]}

    if isinstance(profiles_payload, dict):
        profiles = profiles_payload.get("profiles") or profiles_payload.get("items") or []
    else:
        profiles = profiles_payload
    if not isinstance(profiles, list):
        profiles = []

    selected_language = normalize_language(requested_language, default="auto")
    if selected_language == "auto":
        selected_language = detect_language_from_text(speech_text, fallback="en") or "en"
    profile, engine, profile_error = _select_voicebox_profile(profiles, preferred_profile_id, selected_language)
    if profile is None or not engine:
        return 409, None, "audio/wav", {"ok": False, "error": profile_error or "No compatible Voicebox engine is available."}

    # Inspect the installed Voicebox request schema. Newer releases support
    # per-generation engine routing and multilingual codes; older ones may be
    # limited to en/zh and should fail clearly rather than speak the wrong language.
    request_info = _voicebox_request_properties(_voicebox_openapi_schema(), "/generate")
    if request_info:
        generation_properties, _required = request_info
        language_field = generation_properties.get("language") or {}
        enum_values = language_field.get("enum") or []
        language_pattern = str(language_field.get("pattern") or "")
        declared_languages = {str(item).lower() for item in enum_values}
        if declared_languages and selected_language not in declared_languages:
            return 409, None, "audio/wav", {"ok": False, "error": f"Your installed Voicebox version does not advertise {selected_language} TTS support. Update Voicebox before using this conversation language."}
        if language_pattern:
            try:
                if not re.fullmatch(language_pattern, selected_language):
                    return 409, None, "audio/wav", {"ok": False, "error": f"Your installed Voicebox version does not advertise {selected_language} TTS support. Update Voicebox before using this conversation language."}
            except re.error:
                pass
        elif not language_field and selected_language != "en":
            return 409, None, "audio/wav", {"ok": False, "error": "Your installed Voicebox API does not expose a language field for speech generation. Update Voicebox to use multilingual speech."}

        engine_field = generation_properties.get("engine") or {}
        engine_values = {str(item).lower() for item in (engine_field.get("enum") or [])}
        engine_pattern = str(engine_field.get("pattern") or "")
        if engine_values and engine not in engine_values:
            return 409, None, "audio/wav", {"ok": False, "error": f"Your installed Voicebox does not expose the {engine} speech engine. Enable or install a compatible multilingual engine before using {selected_language}."}
        if engine_pattern:
            try:
                if not re.fullmatch(engine_pattern, engine):
                    return 409, None, "audio/wav", {"ok": False, "error": f"Your installed Voicebox does not expose the {engine} speech engine. Enable or install a compatible multilingual engine before using {selected_language}."}
            except re.error:
                pass
        if "engine" not in generation_properties and engine != _voicebox_profile_engine(profile):
            return 409, None, "audio/wav", {"ok": False, "error": f"Your installed Voicebox API cannot switch this voice to the {engine} engine. Update Voicebox to enable multilingual engine routing."}

    profile_id = str(profile.get("id") or profile.get("profile_id"))
    try:
        generated = _stream_voicebox_audio(profile_id, speech_text, selected_language, engine)
        if generated is None:
            generated = _generate_voicebox_audio_async(profile_id, speech_text, selected_language, engine)
        audio_bytes, content_type = generated
        saved_audio, saved_type, saved_path = _save_voicebox_audio_for_nova(audio_bytes, content_type)
        return 200, saved_audio, saved_type, {
            "ok": True,
            "profile_name": str(profile.get("name") or "Voicebox voice"),
            "language": selected_language,
            "engine": engine,
            "saved_audio": str(saved_path),
        }
    except RuntimeError as exc:
        return 502, None, "audio/wav", {"ok": False, "error": str(exc)[:900]}
    except OSError as exc:
        return 500, None, "audio/wav", {
            "ok": False,
            "error": "Voicebox generated speech, but NOVA could not save/read the shared audio file.",
            "detail": str(exc)[:500],
        }



def list_voicebox_profiles() -> tuple[int, dict[str, Any]]:
    """Return a safe, normalised profile list for NOVA's local voice picker."""
    try:
        payload = _voicebox_request_json("/profiles", timeout=12)
    except urllib.error.HTTPError as exc:
        detail = _voicebox_json(exc.read(64 * 1024))
        return 502, {"ok": False, "error": f"Voicebox returned HTTP {exc.code} while listing voices.", "detail": detail}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return 503, {"ok": False, "error": "Voicebox is not reachable. Start its local server and retry.", "detail": str(exc)[:400]}

    profiles = (payload.get("profiles") or payload.get("items") or []) if isinstance(payload, dict) else payload
    if not isinstance(profiles, list):
        profiles = []

    default_profile_id = None
    try:
        capture_settings = _voicebox_request_json("/settings/captures", timeout=8)
        if isinstance(capture_settings, dict):
            default_profile_id = capture_settings.get("default_playback_voice_id")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        # Older Voicebox releases do not expose capture settings; this is optional.
        pass

    safe_profiles: list[dict[str, Any]] = []
    for item in profiles:
        if not isinstance(item, dict):
            continue
        profile_id = item.get("id") or item.get("profile_id")
        if not profile_id:
            continue
        safe_profiles.append({
            "id": str(profile_id),
            "name": str(item.get("name") or "Voice profile"),
            "description": str(item.get("description") or ""),
            "language": str(item.get("language") or "en"),
            "voice_type": str(item.get("voice_type") or "cloned"),
            "preset_engine": item.get("preset_engine"),
            "preset_voice_id": item.get("preset_voice_id"),
            "default_engine": item.get("default_engine"),
            "is_default": bool(
                str(profile_id) == str(default_profile_id) if default_profile_id else False
            ) or bool(item.get("is_default") or item.get("default") or item.get("is_default_playback")),
        })
    return 200, {"ok": True, "profiles": safe_profiles}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: Any) -> None:
        # A 204 preflight response must not contain a response body.
        data = b"" if status == 204 else json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        if status != 204:
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))

        # Vite may select 5174, 5175, etc. when the default port is occupied.
        # Permit only loopback browser origins, regardless of their local port.
        origin = self.headers.get("Origin", "")
        try:
            parsed_origin = urlsplit(origin)
            allowed_origin = (
                parsed_origin.scheme in {"http", "https"}
                and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        except ValueError:
            allowed_origin = False

        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()
        if status != 204 and data:
            self.wfile.write(data)

    def _send_audio(self, status: int, data: bytes, content_type: str = "audio/wav") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type or "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        try:
            parsed_origin = urlsplit(origin)
            allowed_origin = (
                parsed_origin.scheme in {"http", "https"}
                and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}
            )
        except ValueError:
            allowed_origin = False
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        # Ignore query parameters when matching routes; parse them separately below.
        route_path = urlsplit(self.path).path
        if route_path == "/api/voice/profiles":
            status, payload = list_voicebox_profiles()
            self._send_json(status, payload)
            return

        if route_path == "/api/voice/whisper/status":
            status, payload = get_voicebox_model_status("whisper-base")
            self._send_json(status, payload)
            return

        if route_path == "/api/capabilities":
            self._send_json(200, capabilities_payload())
            return

        if route_path.startswith("/api/status"):
            self._send_json(
                200,
                {
                    "ok": True,
                    "running": running,
                    "task": current_task,
                    "browserOpen": getattr(agent, "_page", None) is not None,
                    "model": getattr(agent, "MODEL", "qwen3:8b"),
                    "activeSite": getattr(agent, "ACTIVE_SITE", ""),
                    "activeAgent": active_agent,
                    "architecture": "router-planner-specialists",
                    "application": {
                        "name": APP_NAME,
                        "version": APP_VERSION,
                        "channel": RELEASE_CHANNEL,
                        "build": BUILD_LABEL,
                    },
                    "workerAlive": (
                        task_thread is not None
                        and task_thread.is_alive()
                    ),
                },
            )
            return

        if route_path.startswith("/api/events"):
            query = parse_qs(urlsplit(self.path).query)
            requested_task = str((query.get("task_id") or [""])[0]).strip()
            try:
                after = int((query.get("after") or ["0"])[0])
            except ValueError:
                after = 0
            with _events_lock:
                events = list(_events)
            if requested_task:
                events = [item for item in events if str(item.get("task_id") or "") == requested_task]
            if after:
                events = [item for item in events if int(item.get("id") or 0) > after]
            self._send_json(200, {"events": events, "count": len(events), "task_id": requested_task or None})
            return

        if route_path.startswith("/api/diagnostics"):
            self._send_json(200, diagnostics_payload())
            return

        if route_path.startswith("/api/executions/interrupted"):
            try:
                runs = _orchestrator_memory.interrupted_executions() if _orchestrator_memory else []
                self._send_json(200, {"ok": True, "runs": runs, "count": len(runs), "automatic_replay": False})
            except Exception as exc:
                self._send_json(503, {"ok": False, "error": str(exc), "runs": []})
            return

        if route_path.startswith("/api/memory/conversation"):
            query = parse_qs(urlsplit(self.path).query)
            chat_id = str((query.get("chat_id") or [""])[0]).strip()
            if not chat_id:
                self._send_json(400, {"ok": False, "error": "chat_id is required"})
                return
            if _orchestrator_memory is None:
                self._send_json(503, {"ok": False, "error": "Memory service is not ready"})
                return
            self._send_json(200, {"ok": True, "memory": _orchestrator_memory.export_conversation_memory(chat_id)})
            return

        if route_path.startswith("/api/task-result"):
            query = parse_qs(urlsplit(self.path).query)
            task_id = str((query.get("task_id") or [""])[0]).strip()
            if not task_id:
                self._send_json(400, {"ok": False, "error": "task_id is required"})
                return
            with _task_records_lock:
                record = _task_records.get(task_id)
                snapshot = dict(record) if record is not None else None
            if snapshot is None:
                self._send_json(404, {"ok": False, "error": "Task not found"})
                return
            self._send_json(200, {"ok": True, "task": snapshot})
            return

        if route_path == "/api/chats":
            with _chat_lock:
                chats = load_chats()
            self._send_json(200, {"ok": True, "chats": chats})
            return

        if route_path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "NOVA backend",
                    "application": {"name": APP_NAME, "version": APP_VERSION},
                    "workerAlive": (
                        task_thread is not None
                        and task_thread.is_alive()
                    ),
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        route_path = self.path.split("?", 1)[0]
        if route_path == "/api/voice/whisper/preload":
            status, payload = preload_voicebox_whisper()
            self._send_json(status, payload)
            return

        if route_path == "/api/voice/whisper/download":
            status, payload = download_voicebox_whisper()
            self._send_json(status, payload)
            return

        if route_path == "/api/voice/speak":
            try:
                body = self._read_json()
            except Exception:
                self._send_json(400, {"ok": False, "error": "Invalid JSON request."})
                return
            text = str(body.get("text") or "").strip()
            profile_id = str(body.get("profile_id") or "").strip() or None
            language = str(body.get("language") or "auto")
            try:
                status, audio, content_type, payload = generate_voicebox_audio(text, profile_id, language)
            except Exception as exc:
                self.log_error("NOVA Voicebox speech route failed: %s", exc)
                self._send_json(500, {"ok": False, "error": "NOVA Voicebox speech handler failed before audio could be returned.", "detail": str(exc)[:1000]})
                return
            if audio is None:
                self._send_json(status, payload)
            else:
                self._send_audio(status, audio, content_type)
            return

        if self.path.split("?", 1)[0] == "/api/voice/transcribe":
            content_type = self.headers.get("Content-Type", "").lower()
            if not content_type.startswith("audio/wav"):
                self._send_json(
                    415,
                    {"ok": False, "error": "Expected an audio/wav recording."},
                )
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0

            if length <= 0:
                self._send_json(400, {"ok": False, "error": "No audio was uploaded."})
                return
            if length > VOICEBOX_MAX_AUDIO_BYTES:
                self._send_json(
                    413,
                    {"ok": False, "error": "The recording is too large (12 MB maximum)."},
                )
                return

            audio = self.rfile.read(length)
            if len(audio) != length:
                self._send_json(400, {"ok": False, "error": "The audio upload was incomplete."})
                return

            query = parse_qs(urlsplit(self.path).query)
            language = str((query.get("language") or ["auto"])[0])
            status, payload = transcribe_with_voicebox(audio, language)
            self._send_json(status, payload)
            return

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
            chat_id = str(body.get("chat_id", "")).strip()

            if not command:
                self._send_json(400, {"ok": False, "error": "Command is empty"})
                return

            if not chat_id:
                self._send_json(400, {"ok": False, "error": "chat_id is required so NOVA can save its reply"})
                return

            with _chat_lock:
                chats = load_chats()
                chat_exists = any(str(item.get("id")) == chat_id for item in chats)
            if not chat_exists:
                self._send_json(404, {"ok": False, "error": "Conversation not found. Start a new chat and retry."})
                return

            status, payload = enqueue_task(
                command,
                chat_id,
                voice_stream=bool(body.get("voice_stream", False)),
                language=str(body.get("language") or "en"),
            )
            self._send_json(status, payload)
            return

        if self.path == "/api/memory/conversation/summary":
            try:
                body = self._read_json()
                chat_id = str(body.get("chat_id") or "").strip()
                summary = str(body.get("summary") or "").strip()
                source_task_id = str(body.get("source_task_id") or "").strip()
                if not chat_id or not summary:
                    self._send_json(400, {"ok": False, "error": "chat_id and summary are required"})
                    return
                if _orchestrator_memory is None:
                    self._send_json(503, {"ok": False, "error": "Memory service is not ready"})
                    return
                _orchestrator_memory.save_conversation_summary(chat_id, summary, source_task_id)
                self._send_json(200, {"ok": True})
            except Exception as exc:
                self._send_json(400, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/executions/review":
            try:
                body = self._read_json()
                task_id = str(body.get("task_id") or "").strip()
                if not task_id or _orchestrator_memory is None:
                    self._send_json(400, {"ok": False, "error": "task_id is required and memory must be ready"})
                    return
                run = next((item for item in _orchestrator_memory.interrupted_executions(100) if item.get("task_id") == task_id), None)
                if run is None:
                    self._send_json(404, {"ok": False, "error": "Interrupted execution not found"})
                    return
                self._send_json(200, {
                    "ok": True, "run": run,
                    "steps": _orchestrator_memory.execution_steps(task_id),
                    "automatic_replay": False,
                    "message": "This execution is available for inspection only. NOVA will not replay actions automatically.",
                })
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/approval/respond":
            try:
                body = self._read_json()
                approval_id = str(body.get("approval_id") or "").strip()
                task_id = str(body.get("task_id") or "").strip()
                decision = str(body.get("decision") or "").strip().lower()
            except Exception:
                self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                return

            resolved, detail = resolve_user_approval(approval_id, task_id, decision)
            if not resolved:
                status = 400 if "required" in detail else (409 if "already" in detail else 404)
                self._send_json(status, {"ok": False, "error": detail})
                return

            self._send_json(200, {"ok": True, "decision": decision})
            return

        if self.path == "/api/stop":
            try:
                requested_task = current_task_id
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                if content_length:
                    try:
                        body = self._read_json()
                        requested_task = str(body.get("task_id") or requested_task).strip()
                    except Exception:
                        pass
                with _task_records_lock:
                    if not requested_task:
                        candidates = [
                            item for item in _task_records.values()
                            if item.get("status") in {"queued", "running", "awaiting_approval"}
                        ]
                        candidates.sort(key=lambda item: float(item.get("created_at") or 0), reverse=True)
                        requested_task = str(candidates[0].get("task_id") or "") if candidates else ""
                    cancel_event = _task_cancel_events.get(requested_task)
                if not requested_task or cancel_event is None:
                    self._send_json(409, {"ok": False, "error": "There is no active or queued task to stop"})
                    return
                cancel_event.set()
                # Only signal the shared legacy agent when this task is already running.
                if requested_task == current_task_id:
                    agent.stop_agent()
                with _approval_condition:
                    _approval_condition.notify_all()
                add_event("status", "Stop requested", task_id=requested_task, event_name="cancellation_requested")
                self._send_json(200, {
                    "ok": True, "message": "Stop requested",
                    "task_id": requested_task,
                    "cooperative": True,
                })
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
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

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/memory/conversation"):
            query = parse_qs(urlsplit(self.path).query)
            chat_id = str((query.get("chat_id") or [""])[0]).strip()
            if not chat_id:
                self._send_json(400, {"ok": False, "error": "chat_id is required"})
                return
            if _orchestrator_memory is None:
                self._send_json(503, {"ok": False, "error": "Memory service is not ready"})
                return
            with _task_records_lock:
                active_for_chat = any(
                    item.get("chat_id") == chat_id
                    and item.get("status") in {"queued", "running", "awaiting_approval"}
                    for item in _task_records.values()
                )
            if active_for_chat:
                self._send_json(409, {"ok": False, "error": "Cannot delete memory while a task from this conversation is active"})
                return
            try:
                deleted = _orchestrator_memory.delete_conversation_memory(chat_id)
                self._send_json(200, {"ok": True, "deleted_turns": deleted})
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})
            return
        self._send_json(404, {"ok": False, "error": "Not found"})

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[NOVA API] {format % args}")


def main() -> None:
    global _worker_shutdown

    print("=" * 60)
    print("NOVA BACKEND")
    print(f"API: http://{HOST}:{PORT}")
    print("Frontend: open the URL shown by the Vite frontend tab (port may vary)")
    print("Model: " + str(getattr(agent, "MODEL", "qwen3:8b")))
    print("Architecture: Router → Planner → Chat / Browser / Research")
    print("Inference: One shared Qwen model · Browser: lazy, task-scoped startup")
    print("=" * 60)

    if not ensure_worker():
        print("❌ NOVA task worker failed to start.")
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
