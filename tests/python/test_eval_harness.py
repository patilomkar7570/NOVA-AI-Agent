import unittest
from nova_agents.contracts import AgentResult
from nova_agents.eval_harness import EvalBenchmarkCase, EvalHarness


class DummyOrchestrator:
    def execute(self, command: str) -> AgentResult:
        if "good morning" in command:
            return AgentResult(task_id="t1", agent="reaction", status="completed", message="Good morning!").finish()
        if "square root" in command:
            return AgentResult(task_id="t2", agent="chat", status="completed", message="16").finish()
        if "palindrome" in command:
            return AgentResult(task_id="t3", agent="coder", status="completed", message="def palindrome(): pass").finish()
        return AgentResult(task_id="t4", agent="chat", status="completed", message="Done").finish()


class EvalHarnessTests(unittest.TestCase):
    def test_run_eval_suite(self):
        orch = DummyOrchestrator()
        harness = EvalHarness(orch)
        cases = [
            EvalBenchmarkCase("c1", "good morning", "reaction"),
            EvalBenchmarkCase("c2", "square root of 256", "chat"),
            EvalBenchmarkCase("c3", "check palindrome function", "coder"),
        ]
        report = harness.run_suite(cases)
        self.assertEqual(report["total_cases"], 3)
        self.assertEqual(report["passed_cases"], 3)
        self.assertEqual(report["success_rate_percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
