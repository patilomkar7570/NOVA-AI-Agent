import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Unit tests for NOVA's dynamic instruction parser.

Verifies:
1. "Open Word and write an essay on Pune of 100 lines."
2. "Okay, now open Word and write an essay about Pune."
3. "Could you please open Word and write about artificial intelligence?"
4. "Write a paragraph on climate change in Notepad."
5. "Open Notepad and write notes about India."
6. "Open Word and create a document about Pune."
7. "Write an essay on Pune and save it in Word."
8. "Open the browser and search for the history of Pune."
9. Negative cases with natural prepositions ("on", "in", "to", "about").
"""
import unittest

from nova_agents.instruction_parser import parse_instruction, resolve_known_app, is_probable_application_name


class TestInstructionParser(unittest.TestCase):
    def test_case_1_open_word_essay_pune_100_lines(self):
        p = parse_instruction("Open Word and write an essay on Pune of 100 lines.")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Pune")
        self.assertEqual(p.length_constraints, {"lines": 100})
        self.assertTrue(p.is_computer_action)
        self.assertTrue(p.is_creative_generation)
        self.assertIn("open_app", p.required_actions)
        self.assertIn("generate_content", p.required_actions)
        self.assertIn("verify_content", p.required_actions)

    def test_case_2_conversational_prefix_okay_now(self):
        p = parse_instruction("Okay, now open Word and write an essay about Pune.")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Pune")
        self.assertTrue(p.is_computer_action)
        self.assertTrue(p.is_creative_generation)

    def test_case_3_conversational_prefix_could_you_please(self):
        p = parse_instruction("Could you please open Word and write about artificial intelligence?")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_topic, "artificial intelligence")
        self.assertTrue(p.is_computer_action)
        self.assertTrue(p.is_creative_generation)

    def test_case_4_paragraph_climate_change_in_notepad(self):
        p = parse_instruction("Write a paragraph on climate change in Notepad.")
        self.assertEqual(p.application, "notepad")
        self.assertEqual(p.content_type, "paragraph")
        self.assertEqual(p.content_topic, "climate change")
        self.assertTrue(p.is_computer_action)

    def test_case_5_open_notepad_write_notes_india(self):
        p = parse_instruction("Open Notepad and write notes about India.")
        self.assertEqual(p.application, "notepad")
        self.assertIn(p.content_type, ("notes", "note"))
        self.assertEqual(p.content_topic, "India")
        self.assertTrue(p.is_computer_action)

    def test_case_6_open_word_create_document_pune(self):
        p = parse_instruction("Open Word and create a document about Pune.")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "document")
        self.assertEqual(p.content_topic, "Pune")
        self.assertTrue(p.is_computer_action)

    def test_case_7_write_essay_save_in_word(self):
        p = parse_instruction("Write an essay on Pune and save it in Word.")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Pune")
        self.assertTrue(p.save_required)
        self.assertTrue(p.is_computer_action)
        self.assertIn("save_document", p.required_actions)

    def test_case_8_open_browser_search_history_pune(self):
        p = parse_instruction("Open the browser and search for the history of Pune.")
        self.assertEqual(p.application, "browser")
        self.assertTrue(p.is_browser_action)
        self.assertFalse(p.is_computer_action)
        self.assertEqual(p.content_type, "search")
        self.assertEqual(p.content_topic, "the history of Pune")
        self.assertIn("search", p.required_actions)

    def test_case_conversational_suffix_brooo(self):
        p = parse_instruction("okay now open word and write a essay on pune of 100 lines brooo")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic.lower(), "pune")
        self.assertEqual(p.length_constraints, {"lines": 100})
        self.assertTrue(p.is_creative_generation)
        self.assertTrue(p.is_computer_action)

    def test_case_direct_write_essay_with_suffix(self):
        p = parse_instruction("write a essay on pune of 100 lines brooo")
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic.lower(), "pune")
        self.assertEqual(p.length_constraints, {"lines": 100})
        self.assertTrue(p.is_creative_generation)
        self.assertTrue(p.is_computer_action)

    def test_negative_cases_natural_prepositions(self):
        negatives = [
            "Explain the impact of inflation on economic growth in developing countries",
            "Tell me about the flight to Tokyo",
            "What is happening in the news today?",
            "Search for recipes to cook on weekends",
        ]
        for cmd in negatives:
            p = parse_instruction(cmd)
            self.assertFalse(p.is_computer_action, f"Should not be computer action: {cmd}")
            # Neither Tokyo, economic growth, nor developing countries should be treated as an app
            self.assertNotIn(p.application, ("tokyo", "economic growth", "developing countries", "weekends"))

    def test_is_probable_application_name(self):
        self.assertTrue(is_probable_application_name("Word"))
        self.assertTrue(is_probable_application_name("Microsoft Word"))
        self.assertTrue(is_probable_application_name("Notepad"))
        self.assertTrue(is_probable_application_name("Excel"))
        self.assertFalse(is_probable_application_name("pune of 100 lines"))
        self.assertFalse(is_probable_application_name("climate change"))
        self.assertFalse(is_probable_application_name("artificial intelligence"))
        self.assertFalse(is_probable_application_name("Tokyo"))

    def test_system_audio_controls(self):
        for cmd, expected in [
            ("mute volume", "volume_mute"),
            ("silence audio", "volume_mute"),
            ("unmute", "volume_unmute"),
            ("volume up", "volume_up"),
            ("turn up the volume", "volume_up"),
            ("volume down", "volume_down"),
            ("turn down the volume", "volume_down"),
        ]:
            p = parse_instruction(cmd)
            self.assertTrue(p.is_system_control, f"Failed for {cmd}")
            self.assertEqual(p.system_action, expected, f"Failed for {cmd}")
            self.assertTrue(p.is_computer_action)

    def test_system_media_controls(self):
        for cmd, expected in [
            ("play music", "media_play_pause"),
            ("pause music", "media_play_pause"),
            ("pause", "media_play_pause"),
            ("toggle playback", "media_play_pause"),
            ("next track", "media_next"),
            ("skip song", "media_next"),
            ("previous track", "media_prev"),
            ("stop music", "media_stop"),
        ]:
            p = parse_instruction(cmd)
            self.assertTrue(p.is_system_control, f"Failed for {cmd}")
            self.assertEqual(p.system_action, expected, f"Failed for {cmd}")
            self.assertTrue(p.is_computer_action)

    def test_system_desktop_and_lock(self):
        for cmd, expected in [
            ("show desktop", "show_desktop"),
            ("minimize all windows", "show_desktop"),
            ("lock workstation", "lock_workstation"),
            ("lock screen", "lock_workstation"),
            ("lock my pc", "lock_workstation"),
        ]:
            p = parse_instruction(cmd)
            self.assertTrue(p.is_system_control, f"Failed for {cmd}")
            self.assertEqual(p.system_action, expected, f"Failed for {cmd}")
            self.assertTrue(p.is_computer_action)

    def test_screenshot_intent(self):
        for cmd in [
            "take a screenshot",
            "capture screen",
            "capture the desktop",
            "what's on my screen",
        ]:
            p = parse_instruction(cmd)
            self.assertTrue(p.is_screenshot, f"Failed for {cmd}")
            self.assertTrue(p.is_computer_action)
            self.assertIn("capture_screenshot", p.required_actions)

    def test_expanded_known_apps(self):
        self.assertEqual(resolve_known_app("Photoshop"), "photoshop")
        self.assertEqual(resolve_known_app("Blender"), "blender")
        self.assertEqual(resolve_known_app("OBS Studio"), "obs")
        self.assertEqual(resolve_known_app("Steam"), "steam")
        self.assertEqual(resolve_known_app("Zoom"), "zoom")
        self.assertEqual(resolve_known_app("Teams"), "teams")
        self.assertEqual(resolve_known_app("Firefox"), "browser")


if __name__ == "__main__":
    unittest.main()
