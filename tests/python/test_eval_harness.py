import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

import tempfile
import unittest
from pathlib import Path
from nova_agents.contracts import AgentResult, TaskRequest
from nova_agents.eval_harness import EvalBenchmarkCase, EvalHarness
from nova_agents.memory import SharedMemory
from nova_agents.planner import TaskPlanner


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

    def test_shared_memory_reward_and_reflexion_tracking(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "test_memory.sqlite3"
        memory = SharedMemory(db_path)

        # Record a successful task reward (+100)
        memory.record_task_reward(
            task_id="task-win-1",
            command="write code to calculate fibonacci and run it",
            pipeline_agents=["coder", "computer", "chat"],
            reward=100,
            status="completed",
            reflection="Fibonacci code synthesized and verified.",
        )

        # Record a failed task penalty (-100)
        memory.record_task_reward(
            task_id="task-fail-1",
            command="open nonexistent_app and format disk",
            pipeline_agents=["computer"],
            reward=-100,
            status="failed",
            reflection="Blocked by security policy or missing app.",
        )

        summary = memory.get_reward_summary()
        self.assertEqual(summary["total_evals"], 2)
        self.assertEqual(summary["successes"], 1)
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["total_reward"], 0)
        self.assertEqual(summary["win_rate"], 50.0)

        # Query reflections
        fib_reflexions = memory.get_reflexions_for_query("calculate fibonacci")
        self.assertTrue(len(fib_reflexions) >= 1)
        self.assertEqual(fib_reflexions[0]["reward"], 100)
        temp_dir.cleanup()

    def test_orchestrator_reward_score_emission(self):
        from nova_agents.orchestrator import Orchestrator
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "test_memory2.sqlite3"
        memory = SharedMemory(db_path)

        class DummyAgentModule:
            def is_explicit_task_command(self, cmd):
                return False

        orch = Orchestrator(DummyAgentModule(), memory=memory)
        # Execute greeting (ReactionAgent)
        res = orch.execute("Hey NOVA, good morning!")
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.data.get("reward_score"), 100)
        self.assertIn("Task completed successfully", res.data.get("reflection", ""))

        summary = memory.get_reward_summary()
        self.assertEqual(summary["total_evals"], 1)
        self.assertEqual(summary["successes"], 1)
        self.assertEqual(summary["total_reward"], 100)
        temp_dir.cleanup()

    def test_multi_agent_pipeline_routing(self):
        class DummyAgentModule:
            def is_explicit_task_command(self, cmd):
                return False

        planner = TaskPlanner(DummyAgentModule())

        # Test deep research pipeline
        req1 = TaskRequest.create("deep research on quantum computing breakthroughs and report")
        plan1 = planner.create_plan(req1)
        self.assertEqual(plan1.source, "deep-research-pipeline")
        self.assertEqual(len(plan1.steps), 3)
        self.assertEqual([s.agent for s in plan1.steps], ["browser", "research", "chat"])

        # Test coder and verify pipeline
        req2 = TaskRequest.create("write a python script for factorial and run it")
        plan2 = planner.create_plan(req2)
        self.assertEqual(plan2.source, "coder-and-verify-pipeline")
        self.assertEqual(len(plan2.steps), 3)
        self.assertEqual([s.agent for s in plan2.steps], ["coder", "computer", "chat"])


if __name__ == "__main__":
    unittest.main()
