import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

import unittest
from pathlib import Path
from types import SimpleNamespace

from nova_agents.contracts import TaskRequest
from nova_agents.specialists.coder_agent import CoderAgent
from nova_agents.coder_permissions import (
    get_coder_permissions,
    set_coder_permission_stage,
    STAGE_MINIMAL,
    STAGE_NECESSARY,
    STAGE_ALL,
    PERMISSION_STAGES,
)


class DummyAgent:
    def chat_response(self, prompt: str) -> str:
        return (
            "<thought>\n"
            "- Boundary check: handle empty inputs and NoneType\n"
            "- Invariant: a + b == b + a\n"
            "- Complexity: O(1) time and space\n"
            "</thought>\n\n"
            "```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```"
        )


class CoderAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = CoderAgent(DummyAgent())
        # Reset to default necessary stage for clean test baseline
        set_coder_permission_stage(STAGE_NECESSARY)

    def tearDown(self):
        set_coder_permission_stage(STAGE_NECESSARY)

    def test_coder_generates_ast_valid_python(self):
        req = TaskRequest.create("Write a function to add two numbers")
        res = self.agent.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.agent, "coder")
        self.assertTrue(res.data.get("syntax_validated"))
        self.assertTrue(res.data.get("has_thought_scratchpad"))
        self.assertTrue(res.data.get("deepseek_hardness"))
        self.assertEqual(res.data.get("model_role"), "work")
        self.assertIn("def add(a: int, b: int) -> int:", res.message)

    def test_inspect_existing_file(self):
        req = TaskRequest.create("inspect file nova_agents/version.py")
        res = self.agent.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertTrue(res.data.get("ast_valid"))
        self.assertIn("APP_NAME", res.message)

    def test_three_permission_stages_metadata(self):
        """Verify the 3 stages: minimal, necessary, all with hover info."""
        perms = get_coder_permissions()
        stages = perms["available_stages"]
        stage_ids = [s["id"] for s in stages]
        self.assertIn("minimal", stage_ids)
        self.assertIn("necessary", stage_ids)
        self.assertIn("all", stage_ids)

        for stage in stages:
            self.assertIn("hover_info", stage)
            self.assertGreater(len(stage["hover_info"]), 20)
            self.assertIn("label", stage)
            self.assertIn("summary", stage)

    def test_permission_stage_switching(self):
        updated = set_coder_permission_stage("minimal")
        self.assertEqual(updated["current_stage"], "minimal")
        self.assertFalse(updated["stage_info"]["allow_write"])
        self.assertFalse(updated["stage_info"]["allow_execute"])

        updated = set_coder_permission_stage("necessary")
        self.assertEqual(updated["current_stage"], "necessary")
        self.assertTrue(updated["stage_info"]["allow_write"])
        self.assertTrue(updated["stage_info"]["allow_execute"])
        self.assertFalse(updated["stage_info"]["allow_external"])

        updated = set_coder_permission_stage("all")
        self.assertEqual(updated["current_stage"], "all")
        self.assertTrue(updated["stage_info"]["allow_write"])
        self.assertTrue(updated["stage_info"]["allow_external"])

    def test_minimal_permission_blocks_file_patching(self):
        set_coder_permission_stage(STAGE_MINIMAL)
        diff_text = "--- a/dummy.py\n+++ b/dummy.py\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        req = TaskRequest(command="apply patch", task_id="test-diff-1", context={"diff": diff_text})
        res = self.agent.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertIn("Permission Denied", res.message)
        self.assertIn("minimal", res.message)

    def test_minimal_permission_blocks_test_execution(self):
        set_coder_permission_stage(STAGE_MINIMAL)
        req = TaskRequest.create("run tests")
        res = self.agent.execute(req)
        self.assertEqual(res.status, "failed")
        self.assertIn("Permission Denied", res.message)

    def test_autonomous_debug_repair_loop(self):
        broken_code = "def divide(a, b):\n    return a / b"
        test_code = "assert divide(10, 2) == 5\nassert divide(10, 0) == 0"
        res = self.agent.run_debug_loop(broken_code, test_code=test_code, max_attempts=3)
        self.assertTrue(res["success"])
        self.assertTrue(res["repaired"])
        self.assertIn("if", res["final_code"])


if __name__ == "__main__":
    unittest.main()
