"""Tests for fast web search routing, ambiguity clarification, and page synthesis."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nova_agents.contracts import TaskRequest
from nova_agents.planner import TaskPlanner
from nova_agents.specialists.browser_agent import BrowserAgent


class BrowserSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.mock_agent = SimpleNamespace(
            MODEL="qwen3:8b",
            FAST_CHAT_MODEL="qwen3:1.7b",
            QWEN_CONTEXT=2048,
            is_explicit_task_command=lambda cmd: False,
        )
        self.planner = TaskPlanner(self.mock_agent)

    def test_search_and_summarize_routes_instantly_without_model_delay(self):
        req = TaskRequest.create("search Google for the latest tech breakthroughs and summarize")
        plan = self.planner.create_plan(req)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertEqual(plan.source, "fast-search-route")
        self.assertGreaterEqual(plan.confidence, 90.0)

    def test_ambiguous_command_triggers_proactive_clarification(self):
        for ambiguous_cmd in ["open it", "search that", "do it", "open", "summarize it"]:
            req = TaskRequest.create(ambiguous_cmd)
            plan = self.planner.create_plan(req)
            self.assertTrue(plan.clarification_required, f"Expected clarification for: {ambiguous_cmd}")
            self.assertEqual(plan.steps[0].agent, "chat")

    def test_browser_agent_synthesizes_gemini_ai_overview_and_search_results(self):
        mock_backend = SimpleNamespace(
            run_task=lambda cmd, **kwargs: print("🎉 Task complete."),
            observe_page=lambda: {
                "title": "Google Search - Latest tech breakthroughs",
                "ai_overview": "Recent breakthroughs include quantum computing coherence milestones and neural interface advances.",
                "search_results": [
                    {"title": "MIT Tech Review: 10 Breakthroughs", "snippet": "Detailed look at generative biology, clean fusion, and next-gen silicon."}
                ],
                "article_content": "",
                "text": "Google Search results text...",
            },
            chat=None,  # Fallback to structured formatter
        )
        browser = BrowserAgent(mock_backend)
        req = TaskRequest.create("search Google for the latest tech breakthroughs and summarize")
        result = browser.execute(req)
        self.assertEqual(result.status, "completed")
        self.assertIn("quantum computing coherence", result.message)
        self.assertIn("MIT Tech Review", result.message)
        self.assertNotIn("Searched for", result.message)

    def test_obvious_command_site_search_wikipedia(self):
        import agent
        actions = agent.obvious_command("open Wikipedia and search when was the king henrey coronated and tell me the date and year")
        self.assertIsNotNone(actions)
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]["action"], "OPEN_URL")
        self.assertIn("wikipedia.org", actions[0]["args"]["url"])
        self.assertEqual(actions[1]["action"], "OPEN_FIRST_ORGANIC_RESULT")
        self.assertEqual(actions[2]["action"], "DONE")

    def test_open_first_organic_result_already_on_article(self):
        import agent
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "href": "https://en.wikipedia.org/wiki/Henry_VIII",
            "text": "Henry VIII",
            "alreadyOnArticle": True,
        }
        with patch.object(agent, "_page", mock_page):
            ok, msg = agent.open_first_organic_result()
            self.assertTrue(ok)
            self.assertIn("Already on article: Henry VIII", msg)

    def test_open_first_organic_result_clicks_top_result(self):
        import agent
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "href": "https://en.wikipedia.org/wiki/Coronation_of_the_British_monarch",
            "text": "Coronation of the British monarch",
        }
        with patch.object(agent, "_page", mock_page):
            with patch.object(agent, "open_url", return_value=(True, "Navigated successfully")) as mock_open:
                ok, msg = agent.open_first_organic_result()
                self.assertTrue(ok)
                self.assertIn("Opened first organic result: Coronation of the British monarch", msg)
                mock_open.assert_called_once_with("https://en.wikipedia.org/wiki/Coronation_of_the_British_monarch")


if __name__ == "__main__":
    unittest.main()
