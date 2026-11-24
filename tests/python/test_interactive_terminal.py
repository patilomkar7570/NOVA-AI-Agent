import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Tests for Live Streaming Interactive Terminal Engine (nova_terminal.py)."""
import os
import unittest
from nova_terminal import TerminalManager, TerminalSession, terminal_manager


class InteractiveTerminalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_test_mode = os.environ.get("NOVA_TEST_MODE")
        os.environ["NOVA_TEST_MODE"] = "1"

    @classmethod
    def tearDownClass(cls):
        if cls._prev_test_mode is not None:
            os.environ["NOVA_TEST_MODE"] = cls._prev_test_mode
        else:
            os.environ.setdefault("NOVA_TEST_MODE", "1")

    def setUp(self):
        self.manager = TerminalManager()

    def tearDown(self):
        self.manager.kill_all()

    def test_session_lifecycle_and_mock_mode(self):
        session = self.manager.create_session(shell="powershell.exe")
        self.assertTrue(session.is_mock)
        self.assertTrue(session.is_alive)
        self.assertIsNotNone(session.session_id)

        # Output contains initialization banner
        out = session.get_output(since_seq=0)
        self.assertTrue(out["ok"])
        self.assertIn("NOVA Sandbox Terminal Ready", out["text"])

        # Write prompt answers
        session.write_input("y")
        out2 = session.get_output(since_seq=out["seq"])
        self.assertIn("Proceeding with installation", out2["text"])

        # Kill session
        killed = self.manager.kill_session(session.session_id)
        self.assertTrue(killed)
        self.assertIsNone(self.manager.get_session(session.session_id))

    def test_interactive_vite_build_simulation(self):
        session = self.manager.create_session()
        session.write_input("npm run build")
        out = session.get_output()
        self.assertIn("Vite Build", out["text"])

    def test_exit_terminates_session(self):
        session = self.manager.create_session()
        session.write_input("exit")
        self.assertFalse(session.is_alive)
        self.assertEqual(session.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
