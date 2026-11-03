"""API approval callback tests use a minimal stub instead of launching Brave."""
import importlib.util
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]

# api.py imports the user's existing agent module. These tests only exercise
# the approval wait/resolve protocol, so substitute its stop/exit events.
stub_agent = ModuleType("agent")
stub_agent.__file__ = str(ROOT / "agent.py")
stub_agent.stop_event = threading.Event()
stub_agent.exit_event = threading.Event()
stub_agent.MODEL = "qwen3:8b"
_previous_agent_module = sys.modules.get("agent")
sys.modules["agent"] = stub_agent
try:
    spec = importlib.util.spec_from_file_location("nova_phase3_test_api", ROOT / "api.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
finally:
    if _previous_agent_module is None:
        sys.modules.pop("agent", None)
    else:
        sys.modules["agent"] = _previous_agent_module


class ApprovalApiTests(unittest.TestCase):
    def setUp(self):
        stub_agent.stop_event.clear()
        api._worker_shutdown.clear()
        with api._approval_condition:
            api._pending_approvals.clear()
        with api._task_records_lock:
            api._task_records.clear()

    def test_approval_is_correlated_and_releases_waiting_worker(self):
        task_id = "approval-test-task"
        with api._task_records_lock:
            api._task_records[task_id] = {"task_id": task_id, "status": "running"}
        result = {}

        def wait_for_approval():
            result.update(api.request_user_approval({
                "task_id": task_id, "agent": "browser",
                "objective": "Send a test email", "reason": "External message send",
            }))

        worker = threading.Thread(target=wait_for_approval)
        worker.start()
        approval_id = None
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and approval_id is None:
            with api._approval_condition:
                if api._pending_approvals:
                    approval_id = next(iter(api._pending_approvals))
            time.sleep(0.01)
        self.assertIsNotNone(approval_id)
        ok, detail = api.resolve_user_approval(approval_id, "wrong-task", "approve")
        self.assertFalse(ok)
        self.assertIn("no longer active", detail)
        ok, detail = api.resolve_user_approval(approval_id, task_id, "approve")
        self.assertTrue(ok)
        self.assertEqual(detail, "approve")
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(result["approved"])

    def test_capabilities_endpoint_snapshot_reports_only_active_agents(self):
        payload = api.capabilities_payload()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["application"]["version"], "0.5.0-alpha")
        self.assertEqual(
            {profile["id"] for profile in payload["agents"]},
            {"reaction", "chat", "browser", "research"},
        )
        self.assertFalse(payload["features"]["windows_desktop_control"])
        self.assertFalse(payload["features"]["file_operations"])
        self.assertFalse(payload["features"]["coding_operations"])

    def test_decline_and_expiry_are_fail_closed(self):
        task_id = "approval-decline-task"
        with api._task_records_lock:
            api._task_records[task_id] = {"task_id": task_id, "status": "running"}
        api._APPROVAL_TIMEOUT_SECONDS = 0.08
        result = api.request_user_approval({"task_id": task_id, "objective": "Delete records"})
        self.assertFalse(result["approved"])
        self.assertIn("expired", result["reason"].lower())
        api._APPROVAL_TIMEOUT_SECONDS = 120


    def test_task_submission_is_atomic_and_rejects_a_second_active_task(self):
        original_ensure_worker = api.ensure_worker
        original_running = api.running
        try:
            api.ensure_worker = lambda: True
            api.running = False
            with api._task_records_lock:
                api._task_records.clear()
                api._task_cancel_events.clear()
            while True:
                try:
                    api._task_queue.get_nowait()
                except Exception:
                    break
            status_one, payload_one = api.enqueue_task("Explain the EU", "chat-one")
            status_two, payload_two = api.enqueue_task("Research Finland", "chat-two")
            self.assertEqual(status_one, 202)
            self.assertTrue(payload_one["task_id"])
            self.assertEqual(status_two, 409)
            self.assertIn("already running", payload_two["error"])
            with api._task_records_lock:
                self.assertEqual(len(api._task_records), 1)
        finally:
            api.ensure_worker = original_ensure_worker
            api.running = original_running
            with api._task_records_lock:
                api._task_records.clear()
                api._task_cancel_events.clear()
            while True:
                try:
                    api._task_queue.get_nowait()
                except Exception:
                    break

    def test_event_ids_are_monotonic_and_safe_for_javascript(self):
        with api._events_lock:
            api._events.clear()
        api.add_event("test", "first", task_id="task-a")
        api.add_event("test", "second", task_id="task-a")
        with api._events_lock:
            first, second = api._events[-2:]
        self.assertLess(first["id"], second["id"])
        self.assertLess(second["id"], 2 ** 53)
        self.assertEqual(first["task_id"], "task-a")



if __name__ == "__main__":
    unittest.main()
