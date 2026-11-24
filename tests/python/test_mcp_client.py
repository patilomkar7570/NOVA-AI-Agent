import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

import tempfile
import unittest
from pathlib import Path

from nova_agents.mcp_client import SkillManager


class SkillManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.temp_dir.name)
        self.manager = SkillManager(self.skills_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_scan_and_match_skills(self):
        skill_path = self.skills_dir / "git_helper.md"
        skill_path.write_text(
            "---\nname: Git Helper\ndescription: Commit and push changes safely\ntags: git, commit, vcs\n---\nAlways check git status before commit.",
            encoding="utf-8",
        )

        skills = self.manager.scan_skills()
        self.assertEqual(len(skills), 1)
        self.assertIn("git_helper", skills)
        self.assertEqual(skills["git_helper"]["title"], "Git Helper")

        matched = self.manager.match_skill("Please run git commit for me")
        self.assertIsNotNone(matched)
        self.assertEqual(matched["id"], "git_helper")


if __name__ == "__main__":
    unittest.main()
