"""Fast front-door router. It validates and packages requests; it does not call an LLM."""
from __future__ import annotations

from .contracts import TaskRequest


class TaskRouter:
    MAX_COMMAND_CHARS = 8000

    def route(self, command: str, conversation_id: str | None = None) -> TaskRequest:
        clean = " ".join(str(command or "").strip().split())
        if not clean:
            raise ValueError("Command is empty.")
        if len(clean) > self.MAX_COMMAND_CHARS:
            raise ValueError(
                f"Command is too long (maximum {self.MAX_COMMAND_CHARS} characters)."
            )
        return TaskRequest.create(clean, conversation_id=conversation_id)
