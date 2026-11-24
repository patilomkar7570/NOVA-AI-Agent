import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Tests for strict per-chat conversational memory isolation and chat deletion purge."""
import unittest
import uuid
import agent
import desktop_memory


class TestMemoryIsolation(unittest.TestCase):
    def setUp(self):
        self.c1 = f"iso-c1-{uuid.uuid4().hex[:8]}"
        self.c2 = f"iso-c2-{uuid.uuid4().hex[:8]}"
        agent.clear_all_chat_histories()

    def tearDown(self):
        agent.clear_all_chat_histories()
        desktop_memory.delete_conversation_memory(self.c1)
        desktop_memory.delete_conversation_memory(self.c2)

    def test_per_chat_history_isolation(self):
        # Chat 1 records a conversation turn about passports
        agent.add_history(
            "search for top 10 countries with the highest passport rank",
            "1. Singapore, 2. Japan, 3. Germany",
            chat_id=self.c1,
        )

        # Chat 2 has not had any conversation yet
        h2 = agent.history_for_qwen(chat_id=self.c2)
        self.assertIn("No previous conversation in this chat", h2)
        self.assertNotIn("passport", h2)

        # Chat 1 has its conversation preserved
        h1 = agent.history_for_qwen(chat_id=self.c1)
        self.assertIn("passport", h1)
        self.assertIn("Singapore", h1)

    def test_desktop_memory_conversation_scoping(self):
        # Save output for chat-1
        desktop_memory.save_last_assistant_output(
            "Singapore is ranked #1 in the passport index.",
            conversation_id=self.c1,
        )

        # Chat-2 must NOT see Chat-1's output
        out2 = desktop_memory.get_last_assistant_output(conversation_id=self.c2)
        self.assertIsNone(out2)

        # Chat-1 sees its own output
        out1 = desktop_memory.get_last_assistant_output(conversation_id=self.c1)
        self.assertEqual(out1, "Singapore is ranked #1 in the passport index.")

    def test_delete_chat_purges_memory(self):
        # Add history & desktop memory for chat
        cid = self.c1
        agent.add_history("find tech breakthroughs", "Breakthroughs in AI", chat_id=cid)
        desktop_memory.save_last_assistant_output("Breakthroughs in AI", conversation_id=cid)

        # Verify exists
        self.assertIn("Breakthroughs", agent.history_for_qwen(chat_id=cid))
        self.assertEqual(desktop_memory.get_last_assistant_output(conversation_id=cid), "Breakthroughs in AI")

        # Delete
        agent.delete_chat_history(cid)
        desktop_memory.delete_conversation_memory(cid)

        # Verify completely purged
        self.assertIn("No previous conversation in this chat", agent.history_for_qwen(chat_id=cid))
        self.assertIsNone(desktop_memory.get_last_assistant_output(conversation_id=cid))

    def test_context_compactor(self):
        import tempfile
        from pathlib import Path
        from nova_agents.memory import SharedMemory, ContextCompactor
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_mem.sqlite3"
            mem = SharedMemory(str(db_path))
            cid = "test-compaction-chat"
            for i in range(10):
                mem.record_task(
                    task_id=f"t-{i}",
                    conversation_id=cid,
                    command=f"User command {i}",
                    agent="chat",
                    status="completed",
                    result=f"Result {i}",
                )
            compactor = ContextCompactor(mem)
            res = compactor.compact_conversation(cid, max_recent_turns=4)
            self.assertTrue(res["compacted"])
            self.assertEqual(res["compacted_turns"], 6)
            self.assertEqual(res["retained_turns"], 4)
            summary = mem.get_conversation_summary(cid)
            self.assertIn("User command", summary)


if __name__ == "__main__":
    unittest.main()
