import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from nova_agents.contracts import TaskRequest
from nova_agents.router import TaskRouter
from nova_agents.planner import TaskPlanner
from nova_agents.orchestrator import Orchestrator
from nova_agents.memory import SharedMemory
from nova_agents.specialists.browser_agent import BrowserAgent
from nova_agents.specialists.research_agent import ResearchAgent


class FakeAgent:
    MODEL = "qwen3:8b"
    QWEN_CONTEXT = 2048

    def __init__(self, explicit=False, root=None):
        self.explicit = explicit
        self.__file__ = str(Path(root or tempfile.gettempdir()) / "agent.py")
        self.stop_event = SimpleNamespace(is_set=lambda: False)
        self.saved_history = []
        self.handled = []
        self.chat_response = None
        self.chat_response_queue = []
        self.chat_error = None
        self.chat_calls = []

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        if self.chat_error:
            raise self.chat_error
        if self.chat_response_queue:
            content = self.chat_response_queue.pop(0)
        else:
            content = self.chat_response or ""
        return SimpleNamespace(message=SimpleNamespace(content=content))

    def is_explicit_task_command(self, command):
        if self.explicit:
            return True
        lower = command.lower().strip()
        return lower.startswith(("open ", "go to ", "visit ", "click ", "search google for "))

    def handle_conversation(self, command):
        self.handled.append(command)
        return True, f"Echo: {command}"

    def add_history(self, command, reply):
        self.saved_history.append((command, reply))

    def run_task(self, command):
        print("🎉 Task complete.")


class FoundationTests(unittest.TestCase):
    def test_router_normalises_and_rejects_empty(self):
        req = TaskRouter().route("  hello   NOVA  ")
        self.assertEqual(req.command, "hello NOVA")
        with self.assertRaises(ValueError):
            TaskRouter().route("  ")

    def test_fast_reactions_skip_qwen(self):
        fake = FakeAgent()
        planner = TaskPlanner(fake)
        for phrase in (
            "Hi NOVA!",
            "Hey NOVA, are you there?",
            "NOVA, can you hear me?",
            "good night NOVA",
            "Thanks a lot!",
            "hi hows ur day going",
        ):
            with self.subTest(phrase=phrase):
                plan = planner.create_plan(TaskRequest.create(phrase))
                self.assertEqual(plan.steps[0].agent, "reaction")
                self.assertEqual(plan.source, "reaction-keyword")
        self.assertEqual(fake.chat_calls, [])

    def test_reaction_keywords_never_swallow_real_commands(self):
        fake = FakeAgent()
        planner = TaskPlanner(fake)
        fake.chat_response = '{"agent":"browser","reason":"Explicit navigation","objective":"Open YouTube","reply":""}'
        for phrase in (
            "Hey NOVA, open YouTube",
            "Thanks, now explain inflation",
            "Great, research this topic",
            "I'm back, let's continue the project",
        ):
            with self.subTest(phrase=phrase):
                plan = planner.create_plan(TaskRequest.create(phrase))
                self.assertNotEqual(plan.steps[0].agent, "reaction")
                if phrase == "Hey NOVA, open YouTube":
                    self.assertEqual(plan.steps[0].agent, "browser")
                    self.assertEqual(plan.source, "qwen")
                elif phrase in {"Thanks, now explain inflation", "I'm back, let's continue the project"}:
                    self.assertEqual(plan.source, "fast-chat-route")
        # Explicit browser and research requests use Qwen; ordinary chat bypasses
        # the separate planning call and goes directly to the Chat specialist.
        self.assertEqual(len(fake.chat_calls), 2)

    def test_ordinary_chat_bypasses_qwen_planner(self):
        fake = FakeAgent()
        planner = TaskPlanner(fake)
        plan = planner.create_plan(TaskRequest.create("What is the square root of 8?"))
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.source, "fast-chat-route")
        self.assertEqual(fake.chat_calls, [])

    def test_low_confidence_qwen_decision_routes_to_chat_for_clarification(self):
        fake = FakeAgent()
        fake.chat_response = (
            '{"confidence":34,"steps":[{"agent":"browser","objective":"Open something",'
            '"reason":"Possibly a browser request"}],'
            '"reply":"Which website would you like me to open?"}'
        )
        plan = TaskPlanner(fake).create_plan(TaskRequest.create("Can you please open that thing?"))
        self.assertEqual(plan.source, "qwen-clarification")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertTrue(plan.steps[0].input_data["needs_clarification"])
        self.assertEqual(plan.steps[0].input_data["planner_confidence"], 34.0)
        self.assertTrue(plan.steps[0].input_data["needs_clarification"])
        self.assertNotIn("precomputed_reply", plan.steps[0].input_data)

    def test_planner_uses_qwen_and_routes_chat_browser_research(self):
        # Force the planner path in this routing-contract test. Ordinary chat
        # bypass is covered separately by test_ordinary_chat_bypasses_qwen_planner.
        fake = FakeAgent(explicit=True)
        planner = TaskPlanner(fake)

        fake.chat_response = '{"confidence":95,"agent":"chat","reason":"General knowledge question","objective":"","reply":"The square root of 8 is 2√2, approximately 2.828."}'
        chat_plan = planner.create_plan(TaskRequest.create("What is the square root of 8?"))
        self.assertEqual(chat_plan.steps[0].agent, "chat")
        self.assertEqual(chat_plan.source, "qwen")
        self.assertEqual(fake.chat_calls[-1]["think"], False)
        self.assertEqual(fake.chat_calls[-1]["options"]["num_predict"], 260)

        fake.chat_response = '{"confidence":98,"agent":"browser","reason":"User requested navigation","objective":"Open YouTube","reply":""}'
        browser_plan = planner.create_plan(TaskRequest.create("Please open YouTube"))
        self.assertEqual(browser_plan.steps[0].agent, "browser")

        fake.chat_response = '{"confidence":96,"agent":"research","reason":"Needs sourced comparison","objective":"Compare recent AI developments","reply":""}'
        research_plan = planner.create_plan(TaskRequest.create("Compare recent AI developments"))
        self.assertEqual(research_plan.steps[0].agent, "research")

    def test_invalid_planner_output_uses_deterministic_fallback(self):
        fake = FakeAgent(explicit=True)
        fake.chat_response = "This is not JSON."
        plan = TaskPlanner(fake).create_plan(TaskRequest.create("open YouTube"))
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertEqual(plan.source, "fallback-rules")

    def test_model_error_fallback_avoids_duplicate_failed_chat_call(self):
        fake = FakeAgent()
        fake.chat_error = ConnectionError("Ollama offline")
        # An explicit browser request enters the planner path. If Qwen is
        # unavailable, deterministic fallback must preserve that browser intent.
        plan = TaskPlanner(fake).create_plan(TaskRequest.create("Please open YouTube"))
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertIn("Ollama offline", plan.steps[0].input_data["planner_error"])

    def test_chat_uses_precomputed_planner_reply_without_second_qwen_call(self):
        fake = FakeAgent()
        request = TaskRequest.create("What is the square root of 8?")
        from dataclasses import replace
        request = replace(request, context={
            "precomputed_reply": "The square root of 8 is 2√2, approximately 2.828.",
            "planner_source": "qwen",
        })
        result = __import__("nova_agents.specialists.chat_agent", fromlist=["ChatAgent"]).ChatAgent(fake).execute(request)
        self.assertEqual(result.status, "completed")
        self.assertIn("2.828", result.message)
        self.assertEqual(fake.handled, [])
        self.assertEqual(len(fake.saved_history), 1)

    def test_browser_adapter_preserves_and_captures_output(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = BrowserAgent(FakeAgent(True)).execute(TaskRequest.create("open youtube"))
        self.assertEqual(result.status, "completed")
        self.assertIn("Task complete", result.data["console_output"])
        self.assertIn("Task complete", output.getvalue())

    def test_research_unwraps_google_result_links(self):
        research = ResearchAgent(FakeAgent())
        found = research._candidate_sources({
            "url": "https://www.google.com/search?q=topic",
            "links": [
                {"text": "Google", "href": "https://google.com/"},
                {"text": "Example source", "href": "/url?q=https%3A%2F%2Fexample.org%2Farticle"},
                {"text": "Example duplicate", "href": "https://example.org/other"},
                {"text": "Second source", "href": "https://second.test/report"},
            ],
        })
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0]["url"], "https://example.org/article")
        self.assertEqual(found[1]["url"], "https://second.test/report")

    def test_sqlite_memory_persists_chat_scoped_tasks_and_source_notes(self):
        with tempfile.TemporaryDirectory() as temp:
            memory = SharedMemory(Path(temp) / "nova.sqlite3")
            memory.record_task(
                task_id="t1", conversation_id="c1", command="Research Finland",
                agent="research", status="completed", result="Finland overview", duration_ms=100,
            )
            memory.record_task(
                task_id="t2", conversation_id="c2", command="Open YouTube",
                agent="browser", status="completed", result="Opened YouTube", duration_ms=200,
            )
            self.assertIn("Research Finland", memory.conversation_context("c1"))
            self.assertNotIn("Open YouTube", memory.conversation_context("c1"))
            memory.save_knowledge(
                category="research", title="Finland policy", content="An excerpt.",
                source_url="https://example.org/finland", confidence=0.55, tags="research",
            )
            hits = memory.search_knowledge("Finland policy")
            self.assertEqual(hits[0]["source_url"], "https://example.org/finland")
            self.assertEqual(memory.stats(), {
                "tasks": 2, "knowledge_items": 1, "preferences": 0,
                "execution_runs": 0, "execution_steps": 0, "interrupted_runs": 0,
                "conversation_summaries": 0,
            })

    def test_orchestrator_hands_browser_result_to_final_chat_step(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = FakeAgent(root=temp)
            fake.chat_response_queue = [
                '{"steps":[{"agent":"browser","objective":"Open YouTube","reason":"The user asked to inspect a site"},{"agent":"chat","objective":"Explain the page result","reason":"The user asked for an explanation after browsing"}],"reply":""}',
                "YouTube opened, but the browser did not return page details in this test. The browser step completed.",
            ]
            memory = SharedMemory(Path(temp) / "nova.sqlite3")
            orchestrator = Orchestrator(fake, memory=memory)
            result = orchestrator.execute("Open YouTube and explain what is on the page", conversation_id="chat-2")
            self.assertEqual(result.agent, "chat")
            self.assertEqual(result.status, "completed")
            self.assertEqual([step["agent"] for step in result.data["execution_steps"]], ["browser", "chat"])
            self.assertEqual(len(fake.chat_calls), 2, "One planner call plus one final synthesis call")
            self.assertEqual(memory.stats()["tasks"], 1)

    def test_orchestrator_runs_planner_and_records_task(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = FakeAgent(root=temp)
            fake.chat_response = '{"agent":"chat","reason":"General question","objective":"","reply":"Inflation is a broad rise in prices."}'
            memory = SharedMemory(Path(temp) / "nova.sqlite3")
            orchestrator = Orchestrator(fake, memory=memory)
            result = orchestrator.execute("Explain inflation", conversation_id="chat-1")
            self.assertEqual(result.agent, "chat")
            self.assertEqual(result.status, "completed")
            self.assertEqual(memory.stats()["tasks"], 1)
            self.assertIn("Explain inflation", memory.conversation_context("chat-1"))


if __name__ == "__main__":
    unittest.main()
