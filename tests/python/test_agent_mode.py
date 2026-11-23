"""Tests for NOVA Agent / Model mode selection (auto, browser, desktop)."""
import unittest
from nova_agents.planner import TaskPlanner
from nova_agents.contracts import TaskRequest
import api

class TestAgentMode(unittest.TestCase):
    def test_planner_mode_browser(self):
        planner = TaskPlanner(None)
        req = TaskRequest(command="search recipes", task_id="test-1", context={"agent_mode": "browser"})
        plan = planner.create_plan(req)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertEqual(plan.source, "user-mode-override")

    def test_planner_mode_desktop(self):
        planner = TaskPlanner(None)
        req = TaskRequest(command="open notes", task_id="test-2", context={"agent_mode": "desktop"})
        plan = planner.create_plan(req)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].agent, "computer")
        self.assertEqual(plan.source, "user-mode-override")

    def test_planner_mode_auto(self):
        planner = TaskPlanner(None)
        req = TaskRequest(command="hello", task_id="test-3", context={"agent_mode": "auto"})
        plan = planner.create_plan(req)
        self.assertGreaterEqual(len(plan.steps), 1)
        self.assertIn(plan.steps[0].agent, {"chat", "planner", "reaction"})

    def test_api_mode_default(self):
        self.assertEqual(api._default_agent_mode, "auto")

    def test_api_mode_enqueue(self):
        api._default_agent_mode = "auto"
        code, res = api.enqueue_task("test command", chat_id="chat-1", mode="desktop")
        self.assertIn(code, (202, 409))

if __name__ == "__main__":
    unittest.main()
