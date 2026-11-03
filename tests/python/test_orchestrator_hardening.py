import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from nova_agents.contracts import AgentResult, ExecutionPlan, PlanStep, TaskRequest
from nova_agents.memory import SharedMemory
from nova_agents.orchestrator import Orchestrator


class DummyAgent:
    MODEL = "qwen3:8b"
    QWEN_CONTEXT = 2048

    def __init__(self):
        self.__file__ = str(Path(tempfile.gettempdir()) / "agent.py")
        self.stop_event = threading.Event()
        self.response = '{"agent":"chat","confidence":95,"reply":"Done."}'
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(message=SimpleNamespace(content=self.response))

    def add_history(self, *_args):
        pass

    def handle_conversation(self, command):
        return True, "Handled: " + command

    def is_explicit_task_command(self, command):
        return command.lower().startswith(("open ", "send ", "delete "))


class StaticPlanner:
    def __init__(self, plan):
        self.plan = plan

    def create_plan(self, _request):
        return self.plan


class DummySpecialist:
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0

    def execute(self, request):
        self.calls += 1
        return self.fn(request, self.calls)


def make_result(request, agent="chat", status="completed", message="ok", data=None, errors=None):
    return AgentResult(
        task_id=request.task_id, agent=agent, status=status, message=message,
        data=data or {}, errors=errors or [],
    ).finish()


class OrchestratorHardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.agent = DummyAgent()
        self.memory = SharedMemory(Path(self.temp.name) / "nova.sqlite3")
        self.orchestrator = Orchestrator(self.agent, memory=self.memory)

    def tearDown(self):
        self.temp.cleanup()

    def test_typed_handoff_filters_data_and_normalises_artifacts(self):
        result = AgentResult(
            task_id="t1", agent="files", status="completed", message="Created report",
            data={"answer": "ready", "private_debug_dump": "do not hand off", "artifacts": [
                {"name": "report.pdf", "path": "output/report.pdf", "mime_type": "application/pdf"},
                {"name": "missing-location.pdf"},
            ]},
        )
        handoff = result.to_handoff()
        self.assertEqual(handoff["schema_version"], 2)
        self.assertEqual(handoff["data"]["answer"], "ready")
        self.assertNotIn("private_debug_dump", handoff["data"])
        self.assertEqual(len(handoff["artifacts"]), 1)
        self.assertEqual(handoff["artifacts"][0]["name"], "report.pdf")

    def test_execution_steps_are_journalled_and_run_finalised(self):
        task_id = "stable-task-id"
        result = self.orchestrator.execute("Explain inflation", conversation_id="chat-1", task_id=task_id)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.task_id, task_id)
        self.assertEqual(self.memory.interrupted_executions(), [])
        steps = self.memory.execution_steps(task_id)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["status"], "completed")
        self.assertEqual(steps[0]["agent"], "chat")
        self.assertEqual(self.memory.stats()["execution_runs"], 1)

    def test_timeout_signal_marks_step_timed_out(self):
        plan = ExecutionPlan(
            task_id="timeout-task",
            steps=[PlanStep(agent="chat", objective="slow operation", timeout_seconds=0.05, max_retries=0)],
            explanation="test timeout", source="test",
        )
        self.orchestrator.planner = StaticPlanner(plan)

        def slow(_request, _call):
            time.sleep(0.12)
            return AgentResult(task_id="timeout-task", agent="chat", status="completed", message="late result").finish()

        self.orchestrator.specialists["chat"] = DummySpecialist(slow)
        result = self.orchestrator.execute("slow operation", task_id="timeout-task")
        self.assertEqual(result.status, "timed_out")
        self.assertTrue(self.agent.stop_event.is_set())
        self.assertIn("time budget", result.message.lower())

    def test_retry_budget_retries_safe_chat_failure_once(self):
        plan = ExecutionPlan(
            task_id="retry-task",
            steps=[PlanStep(agent="chat", objective="retry this", max_retries=1)],
            explanation="test retry", source="test",
        )
        self.orchestrator.planner = StaticPlanner(plan)

        def flaky(request, call):
            if call == 1:
                return make_result(request, status="failed", message="transient", errors=["temporary model error"])
            return make_result(request, message="success after retry")

        specialist = DummySpecialist(flaky)
        self.orchestrator.specialists["chat"] = specialist
        result = self.orchestrator.execute("retry this", task_id="retry-task")
        self.assertEqual(result.status, "completed")
        self.assertEqual(specialist.calls, 2)
        self.assertEqual(result.data["execution_steps"][0]["attempts"], 2)
        self.assertEqual(len(self.memory.execution_steps("retry-task")), 2)

    def test_browser_failure_is_not_automatically_retried(self):
        plan = ExecutionPlan(
            task_id="browser-no-retry",
            steps=[PlanStep(agent="browser", objective="Open YouTube")],
            explanation="safe navigation", source="test",
        )
        self.orchestrator.planner = StaticPlanner(plan)
        specialist = DummySpecialist(
            lambda request, call: make_result(
                request, agent="browser", status="failed", message="navigation failed",
                errors=["temporary browser error"],
            )
        )
        self.orchestrator.specialists["browser"] = specialist
        result = self.orchestrator.execute("Open YouTube", task_id="browser-no-retry")
        self.assertEqual(result.status, "failed")
        self.assertEqual(specialist.calls, 1)

    def test_high_impact_browser_action_fails_closed_without_approval(self):
        plan = ExecutionPlan(
            task_id="approval-task",
            steps=[PlanStep(agent="browser", objective="Send this email from Outlook")],
            explanation="sensitive send", source="test",
        )
        self.orchestrator.planner = StaticPlanner(plan)
        invoked = []
        self.orchestrator.specialists["browser"] = DummySpecialist(
            lambda request, call: invoked.append(request) or make_result(request, agent="browser")
        )
        self.orchestrator.approval_callback = None
        result = self.orchestrator.execute("Send this email from Outlook", task_id="approval-task")
        self.assertEqual(result.status, "stopped")
        self.assertEqual(invoked, [])
        self.assertIn("not perform", result.message.lower())

    def test_explicit_user_approval_unlocks_one_sensitive_browser_step(self):
        plan = ExecutionPlan(
            task_id="approved-task",
            steps=[PlanStep(agent="browser", objective="Send this email from Outlook")],
            explanation="sensitive send", source="test",
        )
        self.orchestrator.planner = StaticPlanner(plan)
        seen = []
        self.orchestrator.approval_callback = lambda payload: seen.append(payload) or {"approved": True}
        self.orchestrator.specialists["browser"] = DummySpecialist(
            lambda request, call: make_result(request, agent="browser", message="Email sent")
        )
        result = self.orchestrator.execute("Send this email from Outlook", task_id="approved-task")
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["risk_level"], "high")

    def test_interrupted_run_is_retained_for_review_not_replayed(self):
        self.memory.start_execution(
            task_id="crashed-task", conversation_id=None, command="Open a site",
            plan={"steps": [{"agent": "browser"}]},
        )
        pending = self.memory.interrupted_executions()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["task_id"], "crashed-task")
        self.assertEqual(pending[0]["plan"]["steps"][0]["agent"], "browser")

    def test_stop_before_execution_prevents_specialist_dispatch(self):
        self.agent.stop_event.set()
        invoked = []
        self.orchestrator.specialists["chat"] = DummySpecialist(
            lambda request, call: invoked.append(request) or make_result(request)
        )
        result = self.orchestrator.execute("Do something", task_id="stopped-task")
        self.assertEqual(result.status, "stopped")
        self.assertEqual(invoked, [])


if __name__ == "__main__":
    unittest.main()
