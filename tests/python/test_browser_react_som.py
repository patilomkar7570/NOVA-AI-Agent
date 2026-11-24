import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Tests for Set-of-Marks (SOM) grounding, smart locators, ReAct engine, and verified memory."""
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import agent
import website_memory
from nova_agents.contracts import TaskRequest
from nova_agents.specialists.browser_agent import BrowserAgent


class BrowserReactSomTests(unittest.TestCase):
    def setUp(self):
        self.mock_page = MagicMock()
        self.mock_page.is_closed.return_value = False
        self.mock_page.url = "https://example.com/test"
        self.mock_page.title.return_value = "Test Portal"

    def test_format_som_for_llm_indexes_elements(self):
        candidates = [
            {"id": 1, "tag": "button", "text": "Submit Form"},
            {"id": 2, "tag": "input", "placeholder": "Search query...", "aria": "Search Box"},
            {"id": 3, "tag": "a", "role": "link", "text": "Privacy Policy"},
        ]
        formatted = agent.format_som_for_llm(candidates)
        self.assertIn('[1] <button "Submit Form">', formatted)
        self.assertIn('[2] <input placeholder="Search query..." aria="Search Box">', formatted)
        self.assertIn('[3] <a role="link" "Privacy Policy">', formatted)

    def test_format_som_for_llm_handles_empty(self):
        self.assertEqual(agent.format_som_for_llm([]), "- No indexed interactive elements detected.")
        self.assertEqual(agent.format_som_for_llm(None), "- No indexed interactive elements detected.")

    def test_click_text_targets_som_index(self):
        locator_mock = MagicMock()
        locator_mock.count.return_value = 1
        target_elem = MagicMock()
        locator_mock.first = target_elem
        self.mock_page.locator.return_value = locator_mock

        with patch.object(agent, "_page", self.mock_page):
            with patch.object(agent, "_ensure_browser_ready", return_value=(True, "")):
                with patch.object(agent, "tiny_wait"):
                    with patch.object(agent, "dismiss_cookie_and_popups"):
                        ok, msg = agent.click_text("1")
                        self.assertTrue(ok)
                        self.assertIn("[1]", msg)
                        self.mock_page.locator.assert_called_with('[data-nova-id="1"]')
                        target_elem.click.assert_called()

    def test_click_text_smart_cascade_fallback(self):
        def locator_side_effect(selector):
            mock = MagicMock()
            if "Checkout" in selector:
                mock.count.return_value = 1
                mock.first = MagicMock()
            else:
                mock.count.return_value = 0
            return mock

        self.mock_page.locator.side_effect = locator_side_effect

        with patch.object(agent, "_page", self.mock_page):
            with patch.object(agent, "_ensure_browser_ready", return_value=(True, "")):
                with patch.object(agent, "tiny_wait"):
                    with patch.object(agent, "dismiss_cookie_and_popups"):
                        ok, msg = agent.click_text("Checkout")
                        self.assertTrue(ok)
                        self.assertIn("Checkout", msg)

    def test_type_text_targets_som_index(self):
        locator_mock = MagicMock()
        locator_mock.count.return_value = 1
        target_elem = MagicMock()
        locator_mock.first = target_elem
        self.mock_page.locator.return_value = locator_mock

        with patch.object(agent, "_page", self.mock_page):
            with patch.object(agent, "_ensure_browser_ready", return_value=(True, "")):
                with patch.object(agent, "tiny_wait"):
                    ok, msg = agent.type_text("AI Agent breakthroughs", target="2", press_enter=True)
                    self.assertTrue(ok)
                    self.assertIn("[2]", msg)
                    target_elem.fill.assert_called_with("AI Agent breakthroughs", timeout=agent.TYPE_TIMEOUT)
                    self.mock_page.keyboard.press.assert_called_with("Enter")

    def test_outcome_verification_rejects_empty_answers(self):
        self.assertFalse(agent._is_task_outcome_verified("what is quantum computing?", "", [], "https://google.com", "https://google.com"))
        self.assertFalse(agent._is_task_outcome_verified("summarize page", "Task complete.", [], "https://google.com", "https://google.com"))
        self.assertFalse(agent._is_task_outcome_verified("find tech news", "Done — Searched Google.", [], "https://google.com", "https://google.com"))

    def test_outcome_verification_accepts_verified_content(self):
        detailed_answer = (
            "### Quantum Milestones\n\n"
            "- Coherence times have reached multi-millisecond scales in superconducting qubits.\n"
            "- Neutral atom quantum computers now support logical qubits with error correction."
        )
        self.assertTrue(agent._is_task_outcome_verified(
            "what is the latest quantum computing breakthrough?",
            detailed_answer,
            [{"action": "OPEN_URL", "args": {"url": "https://google.com"}}],
            "about:blank",
            "https://google.com/search?q=quantum+breakthrough"
        ))

    def test_dismiss_cookie_and_popups_clicks_matching_buttons(self):
        self.mock_page.evaluate.return_value = True
        with patch.object(agent, "_page", self.mock_page):
            dismissed = agent.dismiss_cookie_and_popups()
            self.assertTrue(dismissed)
            self.mock_page.evaluate.assert_called()


import tempfile

class VerifiedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.temp_dir.name) / "test_memory.sqlite3"
        self.old_db = website_memory.DB_PATH
        website_memory.DB_PATH = self.test_db
        website_memory._init_db()

    def tearDown(self):
        website_memory.DB_PATH = self.old_db
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_unverified_workflow_is_not_saved(self):
        workflow = [{"action": "OPEN_URL", "args": {"url": "https://example.com"}}]
        saved = website_memory.save_workflow(
            "unverified query",
            "https://example.com",
            "https://example.com",
            workflow,
            verified=False,
        )
        self.assertFalse(saved)
        self.assertIsNone(website_memory.get_workflow("unverified query", "https://example.com"))

    def test_verified_workflow_is_saved_and_retrieved(self):
        workflow = [{"action": "OPEN_URL", "args": {"url": "https://example.com"}}]
        saved = website_memory.save_workflow(
            "verified query",
            "https://example.com",
            "https://example.com",
            workflow,
            verified=True,
        )
        self.assertTrue(saved)
        retrieved = website_memory.get_workflow("verified query", "https://example.com")
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["action"], "OPEN_URL")

    def test_record_failure_purges_broken_workflow(self):
        workflow = [{"action": "OPEN_URL", "args": {"url": "https://example.com"}}]
        website_memory.save_workflow("flaky command", "https://example.com", "https://example.com", workflow, verified=True)
        # 1 success registered initially. Recording 1 failure makes failure_count >= success_count (1 >= 1)
        website_memory.record_workflow_failure("flaky command", "https://example.com")
        self.assertIsNone(website_memory.get_workflow("flaky command", "https://example.com"))

    def test_human_click_locator_bezier(self):
        mock_page = MagicMock()
        locator_mock = MagicMock()
        locator_mock.bounding_box.return_value = {"x": 100, "y": 200, "width": 50, "height": 30}
        with patch.object(agent, "_page", mock_page):
            res = agent.human_click_locator(locator_mock)
            self.assertTrue(res)
            mock_page.mouse.move.assert_called()
            mock_page.mouse.down.assert_called()
            mock_page.mouse.up.assert_called()

    def test_human_type_locator_gaussian(self):
        locator_mock = MagicMock()
        res = agent.human_type_locator(locator_mock, "hello")
        self.assertTrue(res)
        locator_mock.focus.assert_called()
        self.assertEqual(locator_mock.type.call_count, 5)

    def test_distill_page_content(self):
        mock_page = MagicMock()
        mock_page.evaluate.return_value = "Distilled Article Content"
        with patch.object(agent, "_page", mock_page):
            res = agent.distill_page_content()
            self.assertEqual(res, "Distilled Article Content")


class BrowserAgentTelemetryTests(unittest.TestCase):
    def test_browser_agent_records_som_count_and_evidence(self):
        mock_backend = SimpleNamespace(
            run_task=lambda cmd, **kwargs: print("📌 ANSWER\nDiscovered 3 verified links.\n\n🎉 Task complete."),
            observe_page=lambda: {
                "title": "Quantum Lab",
                "url": "https://lab.example.org",
                "ai_overview": "Research lab overview.",
                "search_results": [
                    {"title": "Lab Publications", "url": "https://lab.example.org/papers", "snippet": "Recent papers."}
                ],
                "interactive": [
                    {"nova_id": 1, "role": "button", "text": "Explore"},
                    {"nova_id": 2, "role": "link", "text": "Docs"},
                ],
                "article_content": "",
                "text": "Lab text...",
            },
            chat=None,
        )
        browser = BrowserAgent(mock_backend)
        req = TaskRequest.create("find lab documentation")
        res = browser.execute(req)
        self.assertEqual(res.status, "completed")
        self.assertEqual(res.message, "Discovered 3 verified links.")
        verification = res.data.get("verification", {})
        self.assertEqual(verification.get("som_count"), 2)
        self.assertTrue(verification.get("has_search_results"))
        self.assertTrue(verification.get("has_ai_overview"))
        evidence = res.data.get("evidence", [])
        self.assertTrue(any(e.get("type") == "search_result" for e in evidence))


if __name__ == "__main__":
    unittest.main()
