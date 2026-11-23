"""Tests for multi-strategy application launch verification, Voicebox detection, and multi-step pipeline planning."""
import unittest
from nova_agents.contracts import TaskRequest
from nova_agents.planner import TaskPlanner
from nova_agents.specialists.computer_agent import (
    ComputerAgent,
    TaskVerifier,
    WindowInspector,
    COMMON_APP_MAP,
    ALLOWLISTED_APPS,
)
import desktop_memory


class TestAppLaunchAndVerification(unittest.TestCase):
    def setUp(self):
        self.agent = ComputerAgent(None)
        self.planner = TaskPlanner(None)

    def test_voicebox_in_app_maps(self):
        """Voicebox must be in ALLOWLISTED_APPS and COMMON_APP_MAP."""
        self.assertIn("voicebox", ALLOWLISTED_APPS)
        self.assertIn("voicebox", COMMON_APP_MAP)
        self.assertIn("voicebox", COMMON_APP_MAP["voicebox"]["aliases"])

    def test_window_inspector_pids_not_zero(self):
        """Open windows must report valid non-zero PIDs."""
        windows = WindowInspector.list_open_windows()
        self.assertIsInstance(windows, list)
        if windows:
            # At least one real top-level window must have a non-zero PID
            pids = [w["pid"] for w in windows]
            self.assertTrue(any(pid > 0 for pid in pids), f"All window PIDs were zero: {windows}")

    def test_task_verifier_toolhelp32_processes(self):
        """TaskVerifier.get_running_processes must enumerate system processes natively."""
        procs = TaskVerifier.get_running_processes()
        self.assertIsInstance(procs, list)
        self.assertGreater(len(procs), 10)
        exes = [p["exe"].lower() for p in procs]
        self.assertTrue(any("python" in e or "explorer" in e for e in exes))

    def test_task_verifier_voicebox_running(self):
        """Voicebox process liveness must be verified by TaskVerifier."""
        # Voicebox is running on the machine (voicebox.exe)
        procs = TaskVerifier.get_running_processes()
        has_voicebox = any("voicebox" in p["exe"].lower() for p in procs)
        if has_voicebox:
            verified = TaskVerifier.verify_app_running("voicebox")
            self.assertTrue(verified, "TaskVerifier failed to detect running Voicebox process.")

    def test_voicebox_execute_completed(self):
        """Executing 'open voicebox' must return completed status without active window error."""
        req = TaskRequest(task_id="test_vb", command="open voicebox")
        result = self.agent.execute(req)
        self.assertEqual(result.status, "completed")
        self.assertTrue("voicebox" in result.message.lower())
        self.assertNotIn("could not confirm its active window", result.message)

    def test_search_and_paste_pipeline_planning(self):
        """Commands like 'search for ... and paste it in PowerPoint' must produce a 4-step pipeline."""
        cmd = "search for top 10 countries with the highest passport rank and paste it in PowerPoint"
        req = TaskRequest(task_id="t_plan", command=cmd)
        plan = self.planner.create_plan(req)
        self.assertEqual(len(plan.steps), 4)
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertIn("search", plan.steps[0].objective)
        self.assertEqual(plan.steps[1].agent, "research")
        self.assertEqual(plan.steps[2].agent, "chat")
        self.assertEqual(plan.steps[3].agent, "computer")
        self.assertIn("PowerPoint", plan.steps[3].objective)

    def test_anaphoric_resolution_conversation_isolated(self):
        """Resolving 'it in' must fetch from the specific conversation_id."""
        cid1 = "conv_test_iso_1"
        cid2 = "conv_test_iso_2"
        desktop_memory.save_last_assistant_output("Passport ranking: Singapore #1", conversation_id=cid1)
        desktop_memory.save_last_assistant_output("AI breakthroughs: Quantum quantum", conversation_id=cid2)

        content1, is_anaph1 = self.agent._resolve_anaphoric_content("it in", conversation_id=cid1)
        self.assertTrue(is_anaph1)
        self.assertIn("Passport ranking", content1)

        content2, is_anaph2 = self.agent._resolve_anaphoric_content("paste it in", conversation_id=cid2)
        self.assertTrue(is_anaph2)
        self.assertIn("AI breakthroughs", content2)

        # Cleanup test memory
        desktop_memory.delete_conversation_memory(cid1)
        desktop_memory.delete_conversation_memory(cid2)


if __name__ == "__main__":
    unittest.main()
