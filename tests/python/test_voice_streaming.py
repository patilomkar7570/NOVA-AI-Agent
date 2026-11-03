"""Regression tests for NOVA's opt-in voice answer token stream."""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from nova_agents.contracts import ExecutionPlan, PlanStep, TaskRequest
from nova_agents.specialists.chat_agent import ChatAgent, _consume_chat_response


class FakeAgent:
    MODEL = "qwen3:8b"
    QWEN_CONTEXT = 2048

    def __init__(self, root: str):
        self.__file__ = str(Path(root) / "agent.py")
        self.stop_event = threading.Event()
        self.saved = []

    def handle_conversation(self, command, stream_callback=None):
        del command
        answer = "NOVA is speaking progressively."
        if callable(stream_callback):
            stream_callback("NOVA is ")
            stream_callback("speaking progressively.")
        self.add_history("Explain this", answer)
        return True, answer

    def add_history(self, command, reply):
        self.saved.append((command, reply))


class StaticChatPlanner:
    def create_plan(self, request):
        return ExecutionPlan(
            task_id=request.task_id,
            steps=[PlanStep(agent="chat", objective=request.command)],
            source="test",
            confidence=100,
        )


class VoiceStreamingTests(unittest.TestCase):
    def test_generator_response_is_collected_and_forwarded(self):
        def chunks():
            yield SimpleNamespace(message=SimpleNamespace(content="First "))
            yield SimpleNamespace(message=SimpleNamespace(content="sentence."))

        deltas = []
        full = _consume_chat_response(chunks(), deltas.append)
        self.assertEqual(full, "First sentence.")
        self.assertEqual(deltas, ["First ", "sentence."])

    def test_chat_agent_forwards_the_existing_chat_response(self):
        with tempfile.TemporaryDirectory() as temp:
            agent = FakeAgent(temp)
            deltas = []
            from dataclasses import replace
            request = TaskRequest.create("Explain this")
            request = replace(request, context={"stream_callback": deltas.append})
            result = ChatAgent(agent).execute(request)
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.message, "NOVA is speaking progressively.")
            self.assertEqual(agent.saved[-1][1], result.message)
            self.assertEqual(deltas, ["NOVA is ", "speaking progressively."])

    def test_orchestrator_forwards_voice_callback_only_to_chat_specialist(self):
        from nova_agents.memory import SharedMemory
        from nova_agents.orchestrator import Orchestrator

        with tempfile.TemporaryDirectory() as temp:
            agent = FakeAgent(temp)
            memory = SharedMemory(Path(temp) / "nova.sqlite3")
            orchestrator = Orchestrator(agent, memory=memory)
            orchestrator.planner = StaticChatPlanner()
            deltas = []
            result = orchestrator.execute(
                "Explain this",
                conversation_id="voice-chat",
                response_callback=deltas.append,
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.message, "NOVA is speaking progressively.")
            self.assertEqual(deltas, ["NOVA is ", "speaking progressively."])


if __name__ == "__main__":
    unittest.main()
