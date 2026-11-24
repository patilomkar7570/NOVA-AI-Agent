import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Tests for Screen Glance Multimodal Vision Co-Pilot (nova_vision_glance.py)."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from nova_vision_glance import ScreenGlanceEngine, screen_glance_engine


class ScreenGlanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NOVA_TEST_MODE"] = "1"

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.engine = ScreenGlanceEngine()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_capture_active_window(self):
        capture = self.engine.capture_active_window()
        self.assertTrue(capture["ok"])
        self.assertIn("VS Code", capture["title"])
        self.assertGreater(capture["width"], 0)
        self.assertTrue(capture["thumbnail_base64"].startswith("data:image/jpeg;base64,"))

    def test_parse_js_typeerror_and_synthesize_fix(self):
        raw_trace = (
            "TypeError: Cannot read properties of undefined (reading 'map')\n"
            "    at renderResults (src/components/SearchResults.jsx:42:18)\n"
            "    at App (src/App.jsx:89:12)"
        )
        parsed = self.engine.parse_screen_error(raw_trace)
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed["has_error"])
        self.assertEqual(parsed["error_type"], "TypeError")
        self.assertIn("src/components/SearchResults.jsx", parsed["file"])
        self.assertEqual(parsed["line"], 42)
        self.assertIn("map", parsed["suggested_fix"]["description"].lower())

    def test_parse_python_traceback(self):
        raw_trace = (
            'Traceback (most recent call last):\n'
            '  File "server.py", line 124, in handle_request\n'
            '    return process_data(payload)\n'
            'KeyError: "missing session_token"'
        )
        parsed = self.engine.parse_screen_error(raw_trace)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["error_type"], "KeyError")
        self.assertEqual(parsed["file"], "server.py")
        self.assertEqual(parsed["line"], 124)

    def test_apply_surgical_fix_on_disk(self):
        target_file = Path(self.temp_dir) / "UserProfile.jsx"
        target_file.write_text("const list = user.posts.map(p => p.title);", encoding="utf-8")

        res = self.engine.apply_surgical_fix(
            str(target_file),
            old_snippet="user.posts.map",
            new_snippet="(user?.posts || []).map",
        )
        self.assertTrue(res["ok"])
        updated = target_file.read_text(encoding="utf-8")
        self.assertEqual(updated, "const list = (user?.posts || []).map(p => p.title);")


if __name__ == "__main__":
    unittest.main()
