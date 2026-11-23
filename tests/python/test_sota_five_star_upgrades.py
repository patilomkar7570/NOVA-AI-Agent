"""Comprehensive unit and integration test suite verifying the SOTA 5.0 architectural upgrades.

Tests:
1. NormalizedCoordinateEngine & Sub-Image ROI patch cropping
2. ModalWatchdog closed-loop interstitial detection & auto-dismissal
3. WindowsShellLauncher direct AUMID & COM package execution
4. desktop_memory visual_anchors geometric relative vectors & drift validation
5. Dual-Engine CDP live tab attachment & hybrid extension bridge
"""
import os
import unittest
from unittest.mock import patch, MagicMock

# Enforce test mode
os.environ["NOVA_TEST_MODE"] = "1"

from nova_agents.vision_grounding import NormalizedCoordinateEngine
from nova_agents.modal_watchdog import ModalWatchdog
from nova_agents.shell_launcher import WindowsShellLauncher
import desktop_memory
import agent


class SOTAFiveStarUpgradesTests(unittest.TestCase):

    def setUp(self):
        os.environ["NOVA_TEST_MODE"] = "1"

    # =========================================================================
    # 1. NormalizedCoordinateEngine & ROI Patch Cropping
    # =========================================================================
    def test_screen_metrics_resolution(self):
        metrics = NormalizedCoordinateEngine.get_screen_metrics()
        self.assertIn("virtual_width", metrics)
        self.assertIn("virtual_height", metrics)
        self.assertGreater(metrics["virtual_width"], 0)
        self.assertGreater(metrics["virtual_height"], 0)

    def test_coordinate_normalization_and_inversion(self):
        metrics = NormalizedCoordinateEngine.get_screen_metrics()
        abs_x, abs_y = 960, 540
        norm_x, norm_y = NormalizedCoordinateEngine.to_normalized(abs_x, abs_y)
        self.assertGreaterEqual(norm_x, 0.0)
        self.assertLessEqual(norm_x, 1.0)
        self.assertGreaterEqual(norm_y, 0.0)
        self.assertLessEqual(norm_y, 1.0)

        # Invert back to physical pixels
        recon_x, recon_y = NormalizedCoordinateEngine.to_absolute_pixels(norm_x, norm_y)
        self.assertAlmostEqual(abs_x, recon_x, delta=2)
        self.assertAlmostEqual(abs_y, recon_y, delta=2)

    def test_roi_patch_cropping(self):
        img, offset = NormalizedCoordinateEngine.crop_window_roi(quadrant="top_header")
        self.assertIsNotNone(img)
        self.assertEqual(len(offset), 2)

    # =========================================================================
    # 2. ModalWatchdog Interstitial Interception
    # =========================================================================
    def test_modal_watchdog_foreground_info(self):
        info = ModalWatchdog.get_foreground_info()
        self.assertIn("hwnd", info)
        self.assertIn("title", info)

    def test_modal_watchdog_blocking_modal_detection(self):
        # Foreground matches target -> not blocking
        self.assertFalse(ModalWatchdog.is_blocking_modal(fg_hwnd=123, target_hwnd=123))

        # Title with update keyword is detected
        with patch.object(ModalWatchdog, "get_foreground_info", return_value={"title": "Software Update Available", "hwnd": 999}):
            self.assertTrue(ModalWatchdog.is_blocking_modal(fg_hwnd=999, target_hwnd=123))

    def test_modal_watchdog_clear_interstitials(self):
        # In test mode, should return cleared=True
        res = ModalWatchdog.check_and_clear_blocking_modals(target_hwnd=123)
        self.assertTrue(res.get("cleared"))
        self.assertTrue(res.get("focus_restored"))

    # =========================================================================
    # 3. WindowsShellLauncher Direct AUMID & COM Execution
    # =========================================================================
    def test_known_aumid_resolution(self):
        calc_aumid = WindowsShellLauncher.find_aumid_in_registry("calc")
        self.assertIsNotNone(calc_aumid)
        self.assertIn("WindowsCalculator", calc_aumid)

        settings_aumid = WindowsShellLauncher.find_aumid_in_registry("settings")
        self.assertIsNotNone(settings_aumid)

        spotify_aumid = WindowsShellLauncher.find_aumid_in_registry("spotify")
        self.assertIsNotNone(spotify_aumid)

    def test_shell_launcher_dispatch(self):
        res = WindowsShellLauncher.launch("calculator")
        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("protocol"), "shell:AppsFolder")

    # =========================================================================
    # 4. Desktop Memory Visual Anchors & Drift Validation
    # =========================================================================
    def test_visual_anchor_save_and_retrieve(self):
        app = "OmniDeskTest"
        elem = "search_box"
        desktop_memory.save_visual_anchor(app, elem, norm_x=0.25, norm_y=0.10, context_signature="Search bar")

        anchor = desktop_memory.get_visual_anchor(app, elem)
        self.assertIsNotNone(anchor)
        self.assertAlmostEqual(anchor["norm_x"], 0.25, delta=0.01)
        self.assertAlmostEqual(anchor["norm_y"], 0.10, delta=0.01)

    def test_visual_anchor_drift_detection(self):
        app = "OmniDeskTest"
        elem = "send_btn"
        desktop_memory.save_visual_anchor(app, elem, norm_x=0.85, norm_y=0.90)

        # Minor shift within tolerance (e.g. 0.86, 0.91) -> valid
        self.assertTrue(desktop_memory.verify_anchor_drift(app, elem, (0.86, 0.91), tolerance=0.15))

        # Major UI redesign shift (e.g. button moved to top-right 0.85, 0.10) -> detected as drift
        self.assertFalse(desktop_memory.verify_anchor_drift(app, elem, (0.85, 0.10), tolerance=0.15))

    # =========================================================================
    # 5. Dual-Engine CDP Live Tab Bridge
    # =========================================================================
    def test_cdp_probe_endpoint(self):
        # Non-listening port returns None cleanly without hanging
        cdp_ws = agent.check_cdp_available(port=49999)
        self.assertIsNone(cdp_ws)

    def test_desktop_stats_include_anchors(self):
        stats = desktop_memory.get_desktop_stats()
        self.assertIn("anchors", stats)
        self.assertGreaterEqual(stats["anchors"], 0)


if __name__ == "__main__":
    unittest.main()
