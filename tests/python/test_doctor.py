import tempfile
import unittest
from pathlib import Path

from scripts.nova_doctor import check_project_layout, model_available


class DoctorTests(unittest.TestCase):
    def test_model_detection_accepts_exact_and_latest_tags(self):
        self.assertTrue(model_available({"models": [{"name": "qwen3:8b"}]}, "qwen3:8b"))
        self.assertTrue(model_available({"models": [{"name": "qwen3:8b:latest"}]}, "qwen3:8b"))
        self.assertFalse(model_available({"models": [{"name": "llama3:8b"}]}, "qwen3:8b"))

    def test_project_layout_reports_missing_required_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            checks = check_project_layout(root)
            self.assertTrue(checks)
            self.assertTrue(all(check.status == "FAIL" for check in checks))

    def test_project_layout_passes_when_required_paths_exist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            required = (
                "api.py", "agent.py", "nova_agents/__init__.py", "nova_agents/registry.py",
                "frontend/package.json", "frontend/src/App.jsx", "frontend/src/App.css",
                "frontend/src/voice/voiceController.js",
            )
            for relative in required:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")
            checks = check_project_layout(root)
            self.assertTrue(all(check.status == "PASS" for check in checks))


if __name__ == "__main__":
    unittest.main()
