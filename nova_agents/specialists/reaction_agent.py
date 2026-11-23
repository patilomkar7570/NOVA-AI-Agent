from __future__ import annotations
import sys

def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            text = sep.join(str(a) for a in args) + end
            encoding = getattr(sys.stdout, "encoding", None) or "ascii"
            sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding))
            sys.stdout.flush()
        except Exception:
            pass

"""Zero-LLM response specialist for exact, safe conversational reactions."""

from ..contracts import AgentResult, TaskRequest


class ReactionAgent:
    name = "reaction"

    def __init__(self, agent_module, memory=None):
        self.agent = agent_module
        self.memory = memory

    def execute(self, request: TaskRequest) -> AgentResult:
        reply = str(request.context.get("reply") or "").strip()
        if not reply:
            return AgentResult(
                task_id=request.task_id,
                agent=self.name,
                status="failed",
                message="No matching reaction was prepared.",
            ).finish()
        try:
            add_history = getattr(self.agent, "add_history", None)
            if callable(add_history):
                add_history(request.command, reply)
        except Exception:
            pass
        _safe_print("\n💬 NOVA")
        _safe_print(reply)
        print()
        return AgentResult(
            task_id=request.task_id,
            agent=self.name,
            status="completed",
            message=reply,
            data={"reply": reply, "mode": "instant-reaction"},
        ).finish()
