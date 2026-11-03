import json
import unittest
from types import SimpleNamespace

from nova_agents.contracts import TaskRequest
from nova_agents.planner import TaskPlanner


class DummyAgent:
    MODEL = "qwen3:8b"
    QWEN_CONTEXT = 2048

    def __init__(self):
        self.calls = 0
        self.response_agent = "chat"
        self.explicit_commands = ("open ", "send ", "delete ", "play ")

    def is_explicit_task_command(self, command):
        return command.lower().startswith(self.explicit_commands)

    def chat(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "confidence": 95,
            "clarification_required": False,
            "steps": [{
                "agent": self.response_agent,
                "objective": "Handle the selected request",
                "reason": "Test route",
                "required_capabilities": [],
                "dependencies": [],
                "risk_level": "low",
            }],
            "reply": "",
        })))


class FastChatRoutingTests(unittest.TestCase):
    def setUp(self):
        self.agent = DummyAgent()
        self.planner = TaskPlanner(self.agent)

    def test_unfamiliar_ordinary_question_bypasses_planner_model_call(self):
        request = TaskRequest.create("Why do some metals rust faster than others?")
        plan = self.planner.create_plan(request)
        self.assertEqual(plan.source, "fast-chat-route")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(self.agent.calls, 0)

    def test_greeting_bypasses_planner_model_call(self):
        request = TaskRequest.create("Hi Noah")
        plan = self.planner.create_plan(request)
        self.assertEqual(plan.source, "fast-chat-route")
        self.assertEqual(self.agent.calls, 0)

    def test_explicit_browser_action_still_uses_planner(self):
        request = TaskRequest.create("Can you open YouTube?")
        self.agent.response_agent = "browser"
        plan = self.planner.create_plan(request)
        self.assertEqual(plan.source, "qwen")
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertEqual(self.agent.calls, 1)

    def test_research_request_still_uses_planner(self):
        request = TaskRequest.create("Research the latest developments in battery storage")
        self.agent.response_agent = "research"
        plan = self.planner.create_plan(request)
        self.assertEqual(plan.source, "qwen")
        self.assertEqual(self.agent.calls, 1)

    def test_current_weather_still_uses_planner(self):
        request = TaskRequest.create("What's the weather today?")
        self.agent.response_agent = "research"
        plan = self.planner.create_plan(request)
        self.assertEqual(plan.source, "qwen")
        self.assertEqual(self.agent.calls, 1)


if __name__ == "__main__":
    unittest.main()
