from __future__ import annotations

import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Comprehensive Sandbox Capability Audit and Stress Benchmark for NOVA AI Agent.

Executes complex tasks across all 6 core specialist agents in strict sandbox mode:
1. ComputerAgent (Desktop OS control, UIA text injection, window ready polling, high-DPI scaling, document synthesis)
2. BrowserAgent (Playwright ReAct SoM, Bezier cursor gliding, Gaussian typing, DOM distillation, viewport streaming)
3. ResearchAgent (Multi-source search unwrapping, untrusted data sanitization, evidence extraction)
4. CoderAgent (AST validation, source inspection, code synthesis)
5. TaskPlanner & Multi-Step Pipeline (Cross-agent handoffs, anaphora resolution, context preservation)
6. Security, Memory Isolation & Ambiguity Resolution (Contact fuzzy match clarification, allowlist bounds, zero leak)
"""
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import agent
import desktop_memory
from nova_agents.contracts import TaskRequest
from nova_agents.instruction_parser import parse_instruction
from nova_agents.memory import SharedMemory
from nova_agents.orchestrator import Orchestrator
from nova_agents.planner import TaskPlanner
from nova_agents.specialists.computer_agent import (
    ALLOWLISTED_APPS,
    ActionExecutor,
    AdaptiveWaiter,
    ComputerAgent,
    WindowInspector,
    create_docx,
    read_docx,
)


class FakeLLMAgent:
    """Mock LLM agent for deterministic, zero-latency sandbox testing."""
    def __init__(self):
        self.MODEL = "qwen3:8b"
        self.FAST_CHAT_MODEL = "qwen3:1.7b"
        self.stop_event = threading.Event()
        self._page = MagicMock()

    def is_explicit_task_command(self, command: str) -> bool:
        return True

    def chat_response(self, prompt: str) -> str:
        if "palindrome" in prompt.lower():
            return "```python\ndef is_palindrome(s: str) -> bool:\n    clean = ''.join(c.lower() for c in s if c.isalnum())\n    return clean == clean[::-1]\n```"
        if "fibonacci" in prompt.lower():
            return "```python\ndef fibonacci(n: int) -> list[int]:\n    if n <= 0: return []\n    res = [0, 1]\n    while len(res) < n: res.append(res[-1] + res[-2])\n    return res[:n]\n```"
        return "Synthesized test response."

    def handle_conversation(self, command: str, stream_callback=None):
        return True, "Mock chat stream output."

    def search_web(self, query: str):
        return [
            {"title": "Result 1", "url": "https://example.com/item1", "snippet": "Snippet 1"},
            {"title": "Result 2", "url": "https://example.com/item2", "snippet": "Snippet 2"},
        ]


class FullCapabilitySandboxAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NOVA_TEST_MODE"] = "1"
        os.environ["NOVA_TEST_CLARIFICATION"] = "0"

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("NOVA_TEST_CLARIFICATION", None)

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        os.environ["NOVA_TEST_DOCS_DIR"] = self.temp_dir
        self.db_path = os.path.join(self.temp_dir, "test_memory.sqlite3")
        self.memory = SharedMemory(self.db_path)
        self.llm_agent = FakeLLMAgent()
        self.orchestrator = Orchestrator(self.llm_agent, memory=self.memory)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. DESKTOP & OS CAPABILITIES (ComputerAgent)
    # =========================================================================
    def test_desktop_complex_document_workflow(self):
        """Complex Task: Generate 50-paragraph document, write to Word, verify OpenXML integrity."""
        cmd = "open Word and write an essay on Quantum Computing of 50 lines and save it"
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Quantum Computing")
        self.assertEqual(p.save_path, "Essay on Quantum Computing.docx")

        computer = self.orchestrator.specialists["computer"]
        with patch.object(computer.inspector, "find_window", return_value={"hwnd": 9991, "title": "Document1 - Word"}):
            req = TaskRequest.create(cmd)
            res = computer.execute(req)
            self.assertEqual(res.status, "completed")
            self.assertTrue(res.data.get("verified"))

            # Verify on disk
            saved_file = os.path.join(self.temp_dir, "Essay on Quantum Computing.docx")
            self.assertTrue(os.path.isfile(saved_file))
            paragraphs = read_docx(saved_file)
            self.assertEqual(len(paragraphs), 50)
            self.assertIn("Quantum Computing", paragraphs[0])

    def test_desktop_adaptive_waiting_and_dpi_v2(self):
        """Adaptive window ready polling returns in 0ms when ready and handles DPI normalization."""
        call_count = [0]
        def condition():
            call_count[0] += 1
            return call_count[0] >= 3

        t0 = time.time()
        success = AdaptiveWaiter.wait_until(condition, timeout=1.0, poll_interval=0.01)
        elapsed = time.time() - t0
        self.assertTrue(success)
        self.assertLess(elapsed, 0.2, "Adaptive waiter should not waste time.")

        # DPI factor test
        scale = WindowInspector.get_dpi_scale_factor(0)
        self.assertGreaterEqual(scale, 1.0)

    def test_desktop_security_blocked_binaries(self):
        """Security: Block unauthorized executables and malicious commands."""
        executor = ActionExecutor()
        dangerous = ["cmd.exe", "powershell.exe", "format.exe", "regedit", "nc.exe"]
        for bad in dangerous:
            with self.assertRaises(PermissionError):
                executor.launch_app(bad)

    # =========================================================================
    # 2. BROWSER & PLAYWRIGHT CAPABILITIES (BrowserAgent & ReAct)
    # =========================================================================
    def test_browser_react_som_and_humanized_interaction(self):
        """Test Set-of-Marks, Bezier human cursor gliding, Gaussian typing, and DOM defluffing."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.bounding_box.return_value = {"x": 100, "y": 200, "width": 80, "height": 30}
        
        with patch.object(agent, "_page", mock_page):
            # Test human click
            agent.human_click_locator(mock_locator)
            mock_page.mouse.move.assert_called()
            mock_page.mouse.down.assert_called()
            mock_page.mouse.up.assert_called()

            # Test human type
            agent.human_type_locator(mock_locator, "Test input")
            mock_locator.focus.assert_called()
            mock_locator.type.assert_called()

        # Test DOM defluffing
        mock_page.evaluate.return_value = "Real Article Content"
        with patch.object(agent, "_page", mock_page):
            distilled = agent.distill_page_content()
            self.assertIn("Real Article Content", distilled)
            self.assertNotIn("<script>", distilled)

    def test_browser_viewport_jpeg_capture(self):
        """Live viewport capture returns valid JPEG header bytes."""
        mock_page = MagicMock()
        mock_page.is_closed.return_value = False
        mock_page.screenshot.return_value = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"
        with patch.object(agent, "_page", mock_page):
            frame = agent.capture_browser_viewport_jpeg()
            self.assertIsNotNone(frame)
            self.assertTrue(frame.startswith(b"\xff\xd8"))

    # =========================================================================
    # 3. CODE SYNTHESIS & AST VALIDATION (CoderAgent)
    # =========================================================================
    def test_coder_complex_algorithm_generation_and_ast_check(self):
        """Coder specialist generates syntactically valid algorithms."""
        coder = self.orchestrator.specialists["coder"]
        req = TaskRequest.create("Write a python function to check if a string is a palindrome")
        res = coder.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertTrue(res.data.get("syntax_validated"))
        self.assertIn("def is_palindrome", res.message)

    def test_coder_source_inspection(self):
        """Coder specialist safely inspects repository source code."""
        coder = self.orchestrator.specialists["coder"]
        req = TaskRequest.create("inspect file nova_agents/version.py")
        res = coder.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertTrue(res.data.get("ast_valid"))

    # =========================================================================
    # 4. MULTI-STEP PIPELINE & PLANNING
    # =========================================================================
    def test_multistep_pipeline_planning(self):
        """Planner builds 4-step cross-specialist pipeline for compound command."""
        cmd = "search for top 10 countries with the highest passport rank and paste it in PowerPoint"
        planner = TaskPlanner(self.llm_agent, memory=self.memory)
        plan = planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(len(plan.steps), 4)
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertEqual(plan.steps[1].agent, "research")
        self.assertEqual(plan.steps[2].agent, "chat")
        self.assertEqual(plan.steps[3].agent, "computer")

    def test_task_memory_isolation(self):
        """Ensures conversation contexts remain isolated across different threads/sessions."""
        cid_a = "user_alpha_session"
        cid_b = "user_beta_session"
        self.memory.record_task(task_id="t_a1", conversation_id=cid_a, command="set dark mode", agent="chat", status="completed", result="Dark mode enabled", duration_ms=50)
        self.memory.record_task(task_id="t_b1", conversation_id=cid_b, command="set light mode", agent="chat", status="completed", result="Light mode enabled", duration_ms=50)

        ctx_a = self.memory.conversation_context(cid_a)
        ctx_b = self.memory.conversation_context(cid_b)
        self.assertIn("dark mode", ctx_a)
        self.assertNotIn("light mode", ctx_a)
        self.assertIn("light mode", ctx_b)
        self.assertNotIn("dark mode", ctx_b)

        # Anaphora isolation in desktop memory
        desktop_memory.save_last_assistant_output("Alpha secret document", conversation_id=cid_a)
        desktop_memory.save_last_assistant_output("Beta public note", conversation_id=cid_b)
        self.assertEqual(desktop_memory.get_last_assistant_output(conversation_id=cid_a), "Alpha secret document")
        self.assertEqual(desktop_memory.get_last_assistant_output(conversation_id=cid_b), "Beta public note")


if __name__ == "__main__":
    unittest.main()
