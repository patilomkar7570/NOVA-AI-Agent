import unittest
from types import SimpleNamespace

from nova_agents.contracts import TaskRequest
from nova_agents.specialists.coder_agent import CoderAgent


class DummyAgent:
    def chat_response(self, prompt: str) -> str:
        return "```python\ndef add(a, b):\n    return a + b\n```"


class CoderAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = CoderAgent(DummyAgent())

    def test_coder_generates_ast_valid_python(self):
        req = TaskRequest.create("Write a function to add two numbers")
        res = self.agent.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.agent, "coder")
        self.assertTrue(res.data.get("syntax_validated"))
        self.assertIn("def add(a, b):", res.message)

    def test_inspect_existing_file(self):
        req = TaskRequest.create("inspect file nova_agents/version.py")
        res = self.agent.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertTrue(res.data.get("ast_valid"))
        self.assertIn("APP_NAME", res.message)


if __name__ == "__main__":
    unittest.main()
