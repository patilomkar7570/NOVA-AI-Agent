import unittest
from nova_agents.specialists.browser_agent import BrowserAgent

class BrowserReplyTests(unittest.TestCase):
    def test_prefers_explicit_answer_block(self):
        output = "📌 ANSWER\nThe page lists three useful sources.\n\n🎉 Task complete."
        self.assertEqual(BrowserAgent._final_answer(output), "The page lists three useful sources.")

    def test_uses_last_successful_action_when_no_answer_block(self):
        output = "✅ Opened URL: https://www.youtube.com/\n🎉 Task complete."
        self.assertEqual(BrowserAgent._final_answer(output), "Done — Opened URL: https://www.youtube.com/")

if __name__ == "__main__":
    unittest.main()
