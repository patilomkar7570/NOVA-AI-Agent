"""Zero-LLM response specialist for exact, safe conversational reactions."""
from __future__ import annotations

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
        print("\n💬 NOVA")
        print(reply)
        print()
        return AgentResult(
            task_id=request.task_id,
            agent=self.name,
            status="completed",
            message=reply,
            data={"reply": reply, "mode": "instant-reaction"},
        ).finish()
