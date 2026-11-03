"""Versioned, validated contracts shared by NOVA's Orchestrator and specialists."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
import time
import uuid

TaskStatus = Literal["completed", "failed", "stopped", "partial", "timed_out"]
TaskState = Literal[
    "queued", "planning", "validating", "executing", "awaiting_approval",
    "retrying", "handing_off", "synthesising", "completed", "partial",
    "failed", "cancelled", "timed_out", "interrupted",
]

ACTIVE_TASK_STATES = frozenset({
    "queued", "planning", "validating", "executing", "awaiting_approval",
    "retrying", "handing_off", "synthesising",
})
FINAL_TASK_STATES = frozenset({
    "completed", "partial", "failed", "cancelled", "timed_out", "interrupted",
})
TASK_STATE_TRANSITIONS = {
    "queued": frozenset({"planning", "cancelled", "failed", "interrupted"}),
    "planning": frozenset({"validating", "cancelled", "failed", "timed_out"}),
    "validating": frozenset({"executing", "cancelled", "failed", "timed_out"}),
    "executing": frozenset({"awaiting_approval", "handing_off", "retrying", "synthesising", "completed", "partial", "failed", "cancelled", "timed_out"}),
    "awaiting_approval": frozenset({"executing", "cancelled", "failed", "timed_out"}),
    "retrying": frozenset({"executing", "failed", "cancelled", "timed_out"}),
    "handing_off": frozenset({"executing", "synthesising", "partial", "failed", "cancelled", "timed_out"}),
    "synthesising": frozenset({"completed", "partial", "failed", "cancelled", "timed_out"}),
    "completed": frozenset(), "partial": frozenset(), "failed": frozenset(),
    "cancelled": frozenset(), "timed_out": frozenset(), "interrupted": frozenset(),
}


def is_valid_task_transition(previous: str, current: str) -> bool:
    """Return whether a task-state transition is allowed by the execution model."""
    if previous == current:
        return True
    return current in TASK_STATE_TRANSITIONS.get(previous, frozenset())


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    command: str
    created_at: float = field(default_factory=time.time)
    conversation_id: str | None = None
    # Private hand-off data from Planner to a specialist. It is not user input.
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, command: str, conversation_id: str | None = None) -> "TaskRequest":
        return cls(
            task_id=uuid.uuid4().hex,
            command=command.strip(),
            conversation_id=conversation_id,
        )


@dataclass(frozen=True)
class PlanStep:
    agent: str
    objective: str
    reason: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    # Runtime policy values are assigned by the Orchestrator, never trusted from Qwen.
    timeout_seconds: float | None = None
    max_retries: int | None = None
    expected_output: str = ""
    required_capabilities: tuple[str, ...] = ()
    dependencies: tuple[int, ...] = ()
    risk_level: str = "low"


@dataclass(frozen=True)
class ExecutionPlan:
    task_id: str
    steps: list[PlanStep]
    explanation: str = ""
    source: str = "rules"
    confidence: float = 0.0
    clarification_required: bool = False


@dataclass(frozen=True)
class ArtifactReference:
    """Portable reference to a future or existing NOVA output artifact."""
    name: str
    uri: str = ""
    path: str = ""
    mime_type: str = "application/octet-stream"
    description: str = ""

    @classmethod
    def from_value(cls, value: Any) -> "ArtifactReference | None":
        if isinstance(value, ArtifactReference):
            return value
        if not isinstance(value, dict):
            return None
        name = str(value.get("name") or value.get("filename") or "").strip()[:240]
        uri = str(value.get("uri") or value.get("url") or "").strip()[:2000]
        path = str(value.get("path") or "").strip()[:2000]
        mime = str(value.get("mime_type") or value.get("mime") or "application/octet-stream").strip()[:160]
        description = str(value.get("description") or "").strip()[:800]
        if not name or not (uri or path):
            return None
        return cls(name=name, uri=uri, path=path, mime_type=mime, description=description)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class AgentResult:
    task_id: str
    agent: str
    status: TaskStatus
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    output_type: str = "text"
    artifacts: list[ArtifactReference | dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int | None:
        if self.finished_at is None:
            return None
        return max(0, int((self.finished_at - self.started_at) * 1000))

    def finish(self) -> "AgentResult":
        self.finished_at = time.time()
        return self

    def validated(self, *, task_id: str, expected_agent: str) -> list[str]:
        """Return contract violations without discarding a specialist's useful message."""
        issues: list[str] = []
        if self.task_id != task_id:
            issues.append("Specialist result task_id does not match the active task.")
        if self.agent != expected_agent:
            issues.append("Specialist result agent does not match the assigned specialist.")
        if self.status not in {"completed", "failed", "stopped", "partial", "timed_out"}:
            issues.append("Specialist returned an unsupported status.")
        if not isinstance(self.message, str):
            issues.append("Specialist message must be text.")
        if not isinstance(self.data, dict):
            issues.append("Specialist data must be an object.")
        if not isinstance(self.errors, list):
            issues.append("Specialist errors must be a list.")
        if not isinstance(self.metadata, dict):
            issues.append("Specialist metadata must be an object.")
        return issues

    def normalised_artifacts(self) -> list[dict[str, str]]:
        values = list(self.artifacts or [])
        if isinstance(self.data, dict) and isinstance(self.data.get("artifacts"), list):
            values.extend(self.data["artifacts"])
        result = []
        seen = set()
        for value in values[:30]:
            item = ArtifactReference.from_value(value)
            if item is None:
                continue
            key = (item.uri, item.path)
            if key in seen:
                continue
            seen.add(key)
            result.append(item.to_dict())
        return result

    def to_handoff(self, *, message_limit: int = 5000) -> dict[str, Any]:
        """Emit the v2 specialist envelope, retaining a bounded v1-compatible shape."""
        data = self.data if isinstance(self.data, dict) else {}
        allowed_data = (
            "sources", "answer", "reply", "routing", "output_type", "metadata",
            "title", "summary", "url", "page_title", "console_output",
            "evidence", "warnings", "confidence", "verification", "published_at",
        )
        safe_data: dict[str, Any] = {}
        for key in allowed_data:
            if key not in data:
                continue
            value = data[key]
            if key in {"answer", "reply", "title", "summary", "url", "page_title", "console_output", "published_at"}:
                safe_data[key] = str(value or "")[: (4000 if key != "console_output" else 3000)]
            elif key == "sources" and isinstance(value, list):
                safe_data[key] = [
                    {
                        "title": str(item.get("title") or "")[:240],
                        "url": str(item.get("url") or "")[:2000],
                        "excerpt": str(item.get("excerpt") or "")[:2000],
                        "published_at": str(item.get("published_at") or "")[:100],
                    }
                    for item in value[:8] if isinstance(item, dict)
                ]
            elif key in {"routing", "metadata", "verification"} and isinstance(value, dict):
                compact = {}
                for meta_key, meta_value in list(value.items())[:24]:
                    if isinstance(meta_value, (str, int, float, bool)) or meta_value is None:
                        compact[str(meta_key)[:80]] = meta_value if not isinstance(meta_value, str) else meta_value[:600]
                safe_data[key] = compact
            elif key in {"warnings", "evidence"} and isinstance(value, list):
                safe_data[key] = [str(item)[:1200] if not isinstance(item, dict) else {
                    str(k)[:80]: (str(v)[:1200] if not isinstance(v, (int, float, bool)) else v)
                    for k, v in list(item.items())[:12]
                } for item in value[:12]]
            elif key == "confidence":
                try:
                    safe_data[key] = max(0.0, min(1.0, float(value)))
                except (TypeError, ValueError):
                    continue
            elif key == "output_type":
                safe_data[key] = str(value or "text")[:80]
        artifacts = self.normalised_artifacts()
        if artifacts:
            safe_data["artifacts"] = artifacts

        # Keep specialist metadata portable and bounded. Arbitrary metadata can
        # otherwise grow the handoff or accidentally carry non-serialisable data.
        raw_metadata = self.metadata if isinstance(self.metadata, dict) else {}
        safe_metadata: dict[str, Any] = {}
        for meta_key, meta_value in list(raw_metadata.items())[:30]:
            key = str(meta_key)[:80]
            if isinstance(meta_value, str):
                safe_metadata[key] = meta_value[:600]
            elif isinstance(meta_value, (int, float, bool)) or meta_value is None:
                safe_metadata[key] = meta_value
            elif isinstance(meta_value, list):
                safe_metadata[key] = [
                    item[:500] if isinstance(item, str) else item
                    for item in meta_value[:12]
                    if isinstance(item, (str, int, float, bool)) or item is None
                ]
            elif isinstance(meta_value, dict):
                safe_metadata[key] = {
                    str(inner_key)[:80]: (inner_value[:500] if isinstance(inner_value, str) else inner_value)
                    for inner_key, inner_value in list(meta_value.items())[:16]
                    if isinstance(inner_value, (str, int, float, bool)) or inner_value is None
                }
        return {
            "schema_version": 2,
            "task_id": self.task_id,
            "agent": self.agent,
            "status": self.status,
            "message": str(self.message or "")[:message_limit],
            "output_type": str(self.output_type or data.get("output_type") or "text")[:80],
            "data": safe_data,
            "artifacts": artifacts,
            "errors": [str(item)[:500] for item in (self.errors or [])[:10]],
            "warnings": [str(item)[:500] for item in (data.get("warnings") or [])[:10]] if isinstance(data.get("warnings"), list) else [],
            "confidence": safe_data.get("confidence"),
            "metadata": safe_metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["artifacts"] = self.normalised_artifacts()
        value["duration_ms"] = self.duration_ms
        value["schema_version"] = 2
        return value
