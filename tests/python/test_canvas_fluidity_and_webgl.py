import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Tests for Continuous Fluid Drag-and-Drop & WebGL 3D Canvas Gestures."""
import os
import unittest
from unittest.mock import MagicMock, patch

import agent
from nova_agents.specialists.computer_agent import ActionExecutor


class CanvasFluidityAndWebGLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["NOVA_TEST_MODE"] = "1"

    @classmethod
    def tearDownClass(cls):
        pass

    def test_drag_and_drop_bezier_physics_trajectory(self):
        executor = ActionExecutor()
        res = executor.drag_and_drop_bezier(
            start_x=100,
            start_y=200,
            end_x=500,
            end_y=600,
            steps=30,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["start"], (100, 200))
        self.assertEqual(res["end"], (500, 600))
        self.assertEqual(res["steps"], 31)  # steps + 1
        self.assertIn("trajectory", res)
        # Verify first and last point
        self.assertEqual(res["trajectory"][0], (100, 200))
        self.assertEqual(res["trajectory"][-1], (500, 600))

    def test_webgl_canvas_orbit_gesture(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.bounding_box.return_value = {"x": 200, "y": 150, "width": 800, "height": 600}
        mock_page.locator.return_value.first = mock_locator

        with patch.object(agent, "_page", mock_page):
            res = agent.webgl_canvas_gesture(
                selector="canvas#3d-viewport",
                gesture="orbit",
                delta_x=150,
                delta_y=-50,
                steps=15,
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["gesture"], "orbit")
            mock_page.mouse.down.assert_called_with(button="left")
            mock_page.mouse.up.assert_called_with(button="left")
            self.assertGreaterEqual(mock_page.mouse.move.call_count, 15)

    def test_webgl_canvas_zoom_gesture(self):
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.bounding_box.return_value = {"x": 100, "y": 100, "width": 400, "height": 400}
        mock_page.locator.return_value.first = mock_locator

        with patch.object(agent, "_page", mock_page):
            res = agent.webgl_canvas_gesture(
                selector="canvas",
                gesture="zoom",
                delta_y=-120,
            )
            self.assertTrue(res["ok"])
            self.assertEqual(res["gesture"], "zoom")
            mock_page.mouse.wheel.assert_called_with(0, -120)


if __name__ == "__main__":
    unittest.main()
