import unittest
from pathlib import Path
import tempfile

from nova_browser_runtime import browser_from_prog_id, choose_browser_name


class BrowserSelectionTests(unittest.TestCase):
    def test_brave_progids(self):
        self.assertEqual(browser_from_prog_id("BraveHTML"), "brave")
        self.assertEqual(browser_from_prog_id("BraveHTML.abc123"), "brave")

    def test_chrome_progids(self):
        self.assertEqual(browser_from_prog_id("ChromeHTML"), "chrome")
        self.assertEqual(browser_from_prog_id("GoogleChrome"), "chrome")

    def test_edge_progids(self):
        self.assertEqual(browser_from_prog_id("MSEdgeHTM"), "edge")
        self.assertEqual(browser_from_prog_id("MicrosoftEdgeHTM"), "edge")

    def test_unsupported_default_falls_back_to_edge(self):
        self.assertEqual(choose_browser_name("FirefoxURL", "auto"), "edge")
        self.assertEqual(choose_browser_name(None, "auto"), "edge")

    def test_explicit_override_wins(self):
        self.assertEqual(choose_browser_name("BraveHTML", "chrome"), "chrome")
        self.assertEqual(choose_browser_name("MSEdgeHTM", "brave"), "brave")

    def test_invalid_override_rejected(self):
        with self.assertRaises(ValueError):
            choose_browser_name("BraveHTML", "firefox")


if __name__ == "__main__":
    unittest.main()
