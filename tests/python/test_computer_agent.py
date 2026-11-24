from __future__ import annotations

import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Comprehensive regression tests for NOVA's ComputerAgent specialist."""
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from nova_agents.contracts import AgentResult, TaskRequest
from nova_agents.orchestrator import Orchestrator
from nova_agents.planner import TaskPlanner
from nova_agents.policy import classify_action_risk
from nova_agents.registry import agent_capabilities, agent_catalog, agent_ids
from nova_agents.specialists.computer_agent import (
    ALLOWLISTED_APPS,
    ActionExecutor,
    ComputerAgent,
    TaskVerifier,
    WindowInspector,
)


class FakeAgent:
    """Mock agent module for testing."""
    def __init__(self):
        self.MODEL = "qwen3:8b"
        self.stop_event = threading.Event()
        self.handled = []

    def is_explicit_task_command(self, command: str) -> bool:
        return False

    def handle_conversation(self, command: str, stream_callback=None):
        return True, "Mock chat answer"


class ComputerAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NOVA_TEST_MODE"] = "1"
        os.environ["NOVA_SANDBOX_MODE"] = "1"
        os.environ["NOVA_HEADLESS"] = "1"

    def setUp(self):
        os.environ["NOVA_TEST_MODE"] = "1"
        os.environ["NOVA_SANDBOX_MODE"] = "1"
        os.environ["NOVA_HEADLESS"] = "1"
        self.agent_module = FakeAgent()
        self.computer_agent = ComputerAgent(self.agent_module, sandbox=True)

    def test_registry_includes_computer_specialist(self):
        ids = agent_ids()
        self.assertIn("computer", ids)
        caps = agent_capabilities("computer")
        self.assertIn("desktop_observation", caps)
        self.assertIn("application_launch", caps)
        self.assertIn("desktop_interaction", caps)

        catalog = agent_catalog()
        computer_entry = next((item for item in catalog if item["id"] == "computer"), None)
        self.assertIsNotNone(computer_entry)
        self.assertEqual(computer_entry["name"], "Computer Agent")
        self.assertEqual(computer_entry["category"], "desktop-automation")

    def test_orchestrator_initializes_computer_specialist(self):
        orch = Orchestrator(self.agent_module)
        self.assertIn("computer", orch.specialists)
        self.assertIsInstance(orch.specialists["computer"], ComputerAgent)

    def test_planner_fallback_routes_desktop_commands_to_computer(self):
        planner = TaskPlanner(self.agent_module)
        for cmd in [
            "launch notepad",
            "open calculator",
            "type hello in notepad",
            "list open windows",
            "show windows",
            "close notepad",
        ]:
            plan = planner._fallback(TaskRequest.create(cmd))
            self.assertEqual(plan.steps[0].agent, "computer", f"Failed for command: {cmd}")

    def test_allowlist_enforcement(self):
        executor = ActionExecutor()
        # Non-allowlisted apps must be rejected
        with self.assertRaises(PermissionError) as ctx:
            executor.launch_app("powershell.exe")
        self.assertIn("not allowlisted", str(ctx.exception))

        with self.assertRaises(PermissionError) as ctx:
            executor.launch_app("cmd")
        self.assertIn("not allowlisted", str(ctx.exception))

        with self.assertRaises(PermissionError) as ctx:
            executor.launch_app("malicious_app")
        self.assertIn("not allowlisted", str(ctx.exception))

    def test_allowlisted_apps_definition(self):
        self.assertIn("notepad", ALLOWLISTED_APPS)
        self.assertIn("calculator", ALLOWLISTED_APPS)
        self.assertIn("calc", ALLOWLISTED_APPS)
        self.assertIn("explorer", ALLOWLISTED_APPS)

    def test_explorer_rejects_nonexistent_directory(self):
        executor = ActionExecutor()
        with self.assertRaises(ValueError):
            executor.launch_app("explorer", argument=r"C:\NonExistentDirectory_XYZ123")

    def test_cancellation_cooperation(self):
        cancel_event = threading.Event()
        cancel_event.set()
        req = TaskRequest.create("type text in notepad")
        from dataclasses import replace
        req = replace(req, context={"cancellation_event": cancel_event})

        result = self.computer_agent.execute(req)
        self.assertEqual(result.status, "stopped")
        self.assertIn("cancelled", result.message.lower())

    def test_policy_blocks_critical_desktop_destruction(self):
        critical_cmds = [
            "powershell -enc aW52b2tl",
            "cmd.exe /c del /f /s /q C:\\*",
            "regedit /s hack.reg",
            "format c:",
            "shutdown /s /t 0",
        ]
        for cmd in critical_cmds:
            assessment = classify_action_risk(cmd, cmd)
            self.assertEqual(assessment["risk_level"], "critical", f"Failed for {cmd}")
            self.assertTrue(assessment["blocked"])

    def test_list_open_windows(self):
        # Must return a list of window dicts with hwnd and title
        windows = WindowInspector.list_open_windows()
        self.assertIsInstance(windows, list)
        for w in windows:
            self.assertIn("hwnd", w)
            self.assertIn("title", w)
            self.assertIn("class_name", w)

    def test_observe_windows_command(self):
        req = TaskRequest.create("list open windows")
        result = self.computer_agent.execute(req)
        self.assertEqual(result.status, "completed")
        self.assertIn("windows", result.data)
        self.assertIn("Open Windows", result.message)

    def test_launch_and_close_notepad(self):
        # Functional test: launch Notepad, verify, and close it
        req_launch = TaskRequest.create("open notepad")
        res_launch = self.computer_agent.execute(req_launch)
        self.assertIn(res_launch.status, ["completed", "partial"])

        # Find window
        time.sleep(0.5)
        win = WindowInspector.find_window("notepad")
        if win:
            self.assertIsNotNone(win)
            self.assertTrue(TaskVerifier.verify_app_running("notepad", win.get("pid")))

            # Type text into Notepad
            req_type = TaskRequest.create("type Hello from NOVA in notepad")
            res_type = self.computer_agent.execute(req_type)
            self.assertIn(res_type.status, ["completed", "partial"])

            # Close Notepad without saving
            req_close = TaskRequest.create("close notepad")
            res_close = self.computer_agent.execute(req_close)
            self.assertEqual(res_close.status, "completed")
            time.sleep(0.3)



    def test_desktop_memory_app_profile_and_workflow(self):
        import desktop_memory
        desktop_memory.save_app_profile("discord", exe_name="Discord.exe", launch_command="Discord.exe")
        profile = desktop_memory.get_app_profile("discord")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["app_name"], "discord")

        desktop_memory.save_control("discord", "general", control_type="ListItem", action_type="click")
        controls = desktop_memory.get_controls("discord")
        self.assertTrue(any(c["control_name"] == "general" for c in controls))

        actions = [
            {"action": "LAUNCH_APP", "args": {"app": "discord"}},
            {"action": "CLICK_CONTROL", "args": {"name": "general"}},
            {"action": "TYPE_TEXT", "args": {"text": "hello team"}},
        ]
        saved = desktop_memory.save_desktop_workflow("send hi in general", "discord", actions)
        self.assertTrue(saved)

        recalled = desktop_memory.get_desktop_workflow("send hi in general", "discord")
        self.assertIsNotNone(recalled)
        self.assertEqual(len(recalled), 3)
        self.assertEqual(recalled[0]["action"], "LAUNCH_APP")

    def test_planner_agent_mode_overrides(self):
        planner = TaskPlanner(self.agent_module)

        # 1. Computer mode forced
        req_comp = TaskRequest.create("hello what is 2+2")
        from dataclasses import replace
        req_comp = replace(req_comp, context={"agent_mode": "computer"})
        plan_comp = planner.create_plan(req_comp)
        self.assertEqual(plan_comp.steps[0].agent, "computer")
        self.assertEqual(plan_comp.source, "user-mode-override")

        # 2. Browser mode forced
        req_browser = TaskRequest.create("what is the weather today")
        req_browser = replace(req_browser, context={"agent_mode": "browser"})
        plan_browser = planner.create_plan(req_browser)
        self.assertEqual(plan_browser.steps[0].agent, "browser")
        self.assertEqual(plan_browser.source, "user-mode-override")

    def test_planner_routes_note_creation_to_computer(self):
        planner = TaskPlanner(self.agent_module)
        commands = [
            "create a note saying write hello",
            "create a note and write hello in it",
            "make a note: meeting at 3pm",
            "take a note of grocery list",
            "open notepad and write hello",
        ]
        for cmd in commands:
            plan = planner._fallback(TaskRequest.create(cmd))
            self.assertEqual(plan.steps[0].agent, "computer", f"Failed for: {cmd}")


    def test_office_and_universal_app_discovery(self):
        from nova_agents.specialists.computer_agent import _find_app_path
        word_path = _find_app_path("word")
        self.assertIsNotNone(word_path)
        self.assertTrue("word" in word_path.lower() or "winword" in word_path.lower())

        excel_path = _find_app_path("excel")
        self.assertIsNotNone(excel_path)
        self.assertTrue("excel" in excel_path.lower())

    def test_planner_routes_office_and_pronouns_to_computer(self):
        planner = TaskPlanner(self.agent_module)
        office_cmds = [
            "open word",
            "launch word",
            "open excel",
            "open powerpoint",
            "open paint",
            "yes open it",
            "open it",
            "no its an app",
            "word is an app",
            "write hello world",
            "type test text",
        ]
        for cmd in office_cmds:
            plan = planner._fallback(TaskRequest.create(cmd))
            self.assertEqual(plan.steps[0].agent, "computer", f"Failed to route '{cmd}' to computer specialist")

    def test_contextual_app_pronoun_followup(self):
        import desktop_memory
        desktop_memory.save_last_app("word")
        self.assertEqual(desktop_memory.get_last_app(), "word")

        # Execute "yes open it" with mock launch_app
        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 12345, "title": "Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    mock_launch.return_value = {"app": "word", "pid": 9999}
                    req = TaskRequest.create("yes open it")
                    res = self.computer_agent.execute(req)
                    self.assertEqual(res.status, "completed")
                    self.assertIn("word", res.message.lower())

    def test_clipboard_text_setting(self):
        from nova_agents.specialists.computer_agent import _set_clipboard_text
        success = _set_clipboard_text("NOVA Integration Test Clipboard")
        self.assertTrue(success)

    def test_multi_agent_pipeline_plan_generation(self):
        planner = TaskPlanner(self.agent_module)
        cmd = "open Wikipedia and search when was the king henrey coronated and tell me the date and year"
        plan = planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertIn("Wikipedia", plan.steps[0].objective)
        self.assertEqual(plan.steps[1].agent, "research")
        self.assertEqual(plan.steps[2].agent, "chat")

    def test_compound_write_anaphoric_resolution_word(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Coronation Date: 24 June 1509 - King Henry VIII")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 12345, "title": "Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "word", "pid": 111}
                        req = TaskRequest.create("now open word and write it in")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Word", res.message)
                        self.assertIn("started a new document", res.message)
                        self.assertIn("24 June 1509", mock_type.call_args[0][1])

    def test_compound_write_anaphoric_resolution_excel(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Revenue: $500,000 | Profit: $120,000")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 54321, "title": "Excel"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "excel", "pid": 222}
                        req = TaskRequest.create("open excel and write it")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Excel", res.message)
                        self.assertIn("started a new document", res.message)
                        self.assertIn("$500,000", mock_type.call_args[0][1])

    def test_reverse_write_syntax(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Henry VIII ascended in 1509")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 12345, "title": "Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "word", "pid": 111}
                        req = TaskRequest.create("write it in word")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Word", res.message)
                        self.assertIn("1509", mock_type.call_args[0][1])

    def test_compound_write_anaphoric_resolution_powerpoint(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Keynote slide: Q3 Breakthroughs")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 77777, "title": "PowerPoint"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "powerpoint", "pid": 333}
                        req = TaskRequest.create("open powerpoint and write it")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Powerpoint", res.message)
                        self.assertIn("started a new document", res.message)
                        self.assertIn("Q3 Breakthroughs", mock_type.call_args[0][1])

    def test_compound_write_generic_app(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Generic Note Content")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 88888, "title": "Notepad"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "notepad", "pid": 444}
                        req = TaskRequest.create("now open notepad and write it in")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Notepad", res.message)
                        self.assertIn("started a new document", res.message)
                        self.assertIn("Generic Note Content", mock_type.call_args[0][1])

    def test_open_word_app_and_paste_it_in(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Latest tech breakthroughs: 1. Quantum computing. 2. Generative biology.")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 99999, "title": "Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "word", "pid": 555}
                        req = TaskRequest.create("open Word app and paste it in")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Word", res.message)
                        self.assertIn("Blank Document", res.message)
                        self.assertIn("Quantum computing", mock_type.call_args[0][1])

    def test_standalone_paste_it_in_resolves_anaphora_and_pastes(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Fusion energy net gain verified.")
        desktop_memory.save_last_app("word")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 99999, "title": "Document1 - Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                    req = TaskRequest.create("paste it in")
                    res = self.computer_agent.execute(req)
                    self.assertEqual(res.status, "completed")
                    self.assertIn("Word", res.message)
                    self.assertIn("Blank Document", res.message)
                    self.assertIn("Fusion energy", mock_type.call_args[0][1])

    def test_open_word_app_autopastes_when_research_exists(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("Breakthrough summary: Silicon photonic interconnects.")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 99999, "title": "Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    mock_launch.return_value = {"app": "word", "pid": 555}
                    req = TaskRequest.create("open Word app")
                    res = self.computer_agent.execute(req)
                    self.assertEqual(res.status, "completed")
                    self.assertIn("Word", res.message)
                    self.assertIn("Blank Document", res.message)
                    self.assertIn("pasted the recent summary", res.message)

    def test_open_word_app_selects_blank_document_without_prior_output(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output("")

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 99999, "title": "Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    mock_launch.return_value = {"app": "word", "pid": 555}
                    req = TaskRequest.create("open Word app")
                    res = self.computer_agent.execute(req)
                    self.assertEqual(res.status, "completed")
                    self.assertIn("Word", res.message)
                    self.assertIn("Blank Document", res.message)

    def test_paste_it_in_powerpoint_instead(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output(
            "Top 10 Passport Rankings:\n1. Singapore (195 destinations)\n2. France, Germany, Italy, Japan, Spain (192 destinations)"
        )

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 77777, "title": "PowerPoint"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "powerpoint", "pid": 777}
                        req = TaskRequest.create("paste it in PowerPoint instead")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Powerpoint", res.message)
                        self.assertIn("Blank Presentation", res.message)
                        self.assertIn("Singapore", mock_type.call_args[0][1])

    def test_open_powerpoint_and_paste_it_in_instead(self):
        import desktop_memory
        desktop_memory.save_last_assistant_output(
            "Top 10 Passport Rankings:\n1. Singapore (195 destinations)\n2. France, Germany, Italy, Japan, Spain (192 destinations)"
        )

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 77777, "title": "PowerPoint"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True) as mock_type:
                        mock_launch.return_value = {"app": "powerpoint", "pid": 777}
                        req = TaskRequest.create("open PowerPoint and paste it in instead")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Powerpoint", res.message)
                        self.assertIn("Blank Presentation", res.message)
                        self.assertIn("Singapore", mock_type.call_args[0][1])

    def test_direct_essay_writing_in_computer_agent(self):
        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 12345, "title": "Word - Document1"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent._send_paste", return_value=True) as mock_paste:
                        mock_launch.return_value = {"app": "word", "pid": 111}
                        req = TaskRequest.create("write a essay on pune of 100 lines brooo")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Word", res.message)
                        self.assertIn("pasted the essay of 100 lines on Pune", res.message)
                        mock_launch.assert_called_with("word")
                        mock_paste.assert_called_with(12345)

    def test_prepare_canvas_skips_non_canvas_apps(self):
        from nova_agents.specialists.computer_agent import _prepare_application_canvas
        self.assertTrue(_prepare_application_canvas(12345, "discord", "Discord"))
        self.assertTrue(_prepare_application_canvas(12345, "spotify", "Spotify"))
        self.assertTrue(_prepare_application_canvas(12345, "chrome", "Chrome"))

    def test_scroll_window_and_action_sequence(self):
        executor = ActionExecutor()
        self.assertTrue(executor.scroll_window(12345, direction="down", amount=3))
        self.assertTrue(executor.scroll_window(12345, direction="up", amount=2))

        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 12345, "title": "Notepad"}):
            actions = [{"action": "SCROLL", "args": {"direction": "down", "amount": 4}}]
            ok, msg = self.computer_agent._execute_actions_sequence(executor, "notepad", actions, {})
            self.assertTrue(ok)

    def test_focus_window_test_mode(self):
        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            self.assertTrue(WindowInspector.focus_window(12345))

    def test_desktop_memory_failure_purge(self):
        import desktop_memory
        desktop_memory.save_desktop_workflow("flaky desktop command", "notepad", [{"action": "LAUNCH_APP", "args": {"app": "notepad"}}])
        # Recording 1 failure purges it because failure_count (1) >= success_count (1)
        desktop_memory.record_workflow_result("flaky desktop command", "notepad", False)
        self.assertIsNone(desktop_memory.get_desktop_workflow("flaky desktop command", "notepad"))

    def test_system_audio_executor(self):
        executor = ActionExecutor()
        self.assertTrue(executor.set_volume("mute"))
        self.assertTrue(executor.set_volume("unmute"))
        self.assertTrue(executor.set_volume("up"))
        self.assertTrue(executor.set_volume("down"))

    def test_system_media_executor(self):
        executor = ActionExecutor()
        self.assertTrue(executor.media_control("play_pause"))
        self.assertTrue(executor.media_control("next"))
        self.assertTrue(executor.media_control("prev"))
        self.assertTrue(executor.media_control("stop"))

    def test_system_desktop_and_lock_executor(self):
        executor = ActionExecutor()
        self.assertTrue(executor.show_desktop())
        self.assertTrue(executor.lock_workstation())

    def test_capture_desktop_screenshot(self):
        executor = ActionExecutor()
        shot_path = executor.capture_desktop_screenshot()
        self.assertTrue(os.path.isfile(shot_path))
        self.assertTrue(shot_path.endswith(".png"))

    def test_computer_agent_executes_voice_system_controls(self):
        for cmd, expected_msg in [
            ("mute volume", "Muted system audio."),
            ("unmute", "Unmuted system audio."),
            ("turn up the volume", "Turned the volume up."),
            ("turn down the volume", "Turned the volume down."),
            ("pause music", "Toggled media playback."),
            ("next track", "Skipped to the next track."),
            ("previous track", "Returned to the previous track."),
            ("stop music", "Stopped media playback."),
            ("show desktop", "Minimised all windows and showed desktop."),
            ("lock workstation", "Locked your computer."),
        ]:
            req = TaskRequest.create(cmd)
            res = self.computer_agent.execute(req)
            self.assertEqual(res.status, "completed", f"Failed status for {cmd}")
            self.assertEqual(res.message, expected_msg, f"Failed message for {cmd}")

    def test_computer_agent_executes_screenshot(self):
        req = TaskRequest.create("take a screenshot")
        res = self.computer_agent.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertIn("screenshot", res.data)
        self.assertTrue(os.path.isfile(res.data["screenshot"]))

    def test_planner_routes_voice_system_controls_and_screenshots(self):
        planner = TaskPlanner(self.agent_module)
        for cmd in [
            "mute volume",
            "unmute",
            "turn up the volume",
            "turn down the volume",
            "pause music",
            "next track",
            "previous track",
            "show desktop",
            "minimize all windows",
            "lock pc",
            "lock screen",
            "take a screenshot",
            "capture screen",
            "what's on my screen",
        ]:
            req = TaskRequest.create(cmd)
            plan = planner.create_plan(req)
            self.assertEqual(plan.steps[0].agent, "computer", f"Failed route for {cmd}")

    def test_expanded_apps_and_probable_app(self):
        from nova_agents.specialists.computer_agent import _is_probable_app
        self.assertTrue(_is_probable_app("photoshop"))
        self.assertTrue(_is_probable_app("blender"))
        self.assertTrue(_is_probable_app("obs"))
        self.assertTrue(_is_probable_app("steam"))
        self.assertTrue(_is_probable_app("zoom"))
        self.assertTrue(_is_probable_app("teams"))

    def test_release_all_modifiers_safety(self):
        executor = ActionExecutor()
        # Ensure it runs without exception in test mode and live
        executor.release_all_modifiers()

    def test_index_interactive_marks_som(self):
        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            marks = WindowInspector.index_interactive_marks(12345)
            self.assertIsInstance(marks, list)
            self.assertGreater(len(marks), 0)
            first = marks[0]
            self.assertIn("mark_id", first)
            self.assertIn("name", first)
            self.assertIn("control_type", first)
            self.assertIn("rect", first)
            self.assertIn("center", first)

    def test_verify_visual_state_change(self):
        # Empty or identical bytes
        res_empty = TaskVerifier.verify_visual_state_change(None, None)
        self.assertFalse(res_empty["changed"])
        self.assertEqual(res_empty["change_ratio"], 0.0)

        res_same = TaskVerifier.verify_visual_state_change(b"mock_png_bytes", b"mock_png_bytes")
        self.assertFalse(res_same["changed"])

        # Different bytes
        res_diff = TaskVerifier.verify_visual_state_change(b"mock_png_bytes_1", b"mock_png_bytes_2")
        self.assertTrue(res_diff["changed"])
        self.assertGreater(res_diff["change_ratio"], 0.0)

    def test_dpi_v2_and_scaling(self):
        from nova_agents.specialists.computer_agent import enable_dpi_awareness_v2
        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            self.assertTrue(enable_dpi_awareness_v2())
            dpi = WindowInspector.get_window_dpi(12345)
            self.assertEqual(dpi, 96)
            scale = WindowInspector.get_dpi_scale_factor(12345)
            self.assertEqual(scale, 1.0)

    def test_ocr_locate_text_fallback(self):
        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            coords = WindowInspector.ocr_locate_text(12345, "Save")
            self.assertIsNotNone(coords)
            self.assertEqual(coords, (100, 100))

    def test_uia_set_control_value_and_bezier_click(self):
        executor = ActionExecutor()
        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            # Instant UIA ValuePattern set value
            res_val = executor.set_control_value(12345, "Sample Text", "Editor")
            self.assertTrue(res_val)

            # Smooth Bezier motion
            points = executor.move_cursor_bezier(100, 100, 500, 400, steps=10)
            self.assertEqual(len(points), 11)
            self.assertEqual(points[0], (100, 100))
            self.assertEqual(points[-1], (500, 400))

            # Sandbox coordinate click
            res_click = executor.click_point(500, 400, button="left")
            self.assertTrue(res_click)

    def test_strict_sandbox_never_spawns_real_apps(self):
        executor = ActionExecutor()
        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            res_launch = executor.launch_app("notepad")
            self.assertEqual(res_launch["app"], "notepad")
            self.assertEqual(res_launch["pid"], 99999)

            res_close = executor.close_window(12345)
            self.assertTrue(res_close)

    def test_adaptive_waiter_and_window_ready(self):
        from nova_agents.specialists.computer_agent import AdaptiveWaiter
        counter = {"n": 0}
        def check():
            counter["n"] += 1
            return counter["n"] >= 2
        # Should return in ~80ms without waiting full timeout
        res = AdaptiveWaiter.wait_until(check, timeout=1.0, poll_interval=0.02)
        self.assertTrue(res)

        with patch.dict(os.environ, {"NOVA_TEST_MODE": "1"}):
            win = WindowInspector.wait_for_window_ready("discord")
            self.assertIsNotNone(win)


if __name__ == "__main__":
    unittest.main()

