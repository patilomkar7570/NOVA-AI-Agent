import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

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

    def test_planner_mode_coder(self):
        planner = TaskPlanner(None)
        req = TaskRequest(command="refactor api endpoint", task_id="test-coder-1", context={"agent_mode": "coder"})
        plan = planner.create_plan(req)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].agent, "coder")
        self.assertEqual(plan.source, "user-mode-override")

    def test_planner_mode_coding_alias(self):
        planner = TaskPlanner(None)
        req = TaskRequest(command="write binary search", task_id="test-coder-2", context={"agent_mode": "coding"})
        plan = planner.create_plan(req)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].agent, "coder")
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
