from __future__ import annotations

import os
os.environ.setdefault("NOVA_TEST_MODE", "1")
os.environ.setdefault("NOVA_SANDBOX_MODE", "1")
os.environ.setdefault("NOVA_HEADLESS", "1")

"""Master Upgrade Audit & Stabilization Regression Test Suite for NOVA AI Agent.

Covers:
- Application name extraction & normalization
- Topic extraction with natural prepositions decoupled
- Conversational prefix stripping
- Compound instructions & 8 required test cases
- Natural language variations & negative cases
- Application allowlist validation
- Argument separation (preventing CLI argument pollution)
- Task context preservation across pipeline handoffs
- Exactly 100 non-empty paragraphs content generation
- OpenXML DOCX creation, saving, and content verification
"""
import os
import shutil
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

import agent
from nova_agents.contracts import TaskRequest
from nova_agents.instruction_parser import (
    is_probable_application_name,
    parse_instruction,
    resolve_known_app,
    strip_conversational_prefixes,
)
from nova_agents.planner import TaskPlanner
from nova_agents.specialists.computer_agent import (
    ALLOWLISTED_APPS,
    ActionExecutor,
    ComputerAgent,
    _save_and_verify_document,
    _synthesize_fallback_essay,
    create_docx,
    read_docx,
)


class FakeAgentModule:
    """Mock agent module for testing."""
    def __init__(self):
        self.MODEL = "qwen3:8b"
        self.FAST_CHAT_MODEL = "qwen3:1.7b"
        self.stop_event = threading.Event()

    def is_explicit_task_command(self, command: str) -> bool:
        return False

    def handle_conversation(self, command: str, stream_callback=None):
        return True, "Mock chat answer"


class MasterUpgradeAuditTests(unittest.TestCase):
    def setUp(self):
        self.agent_module = FakeAgentModule()
        self.planner = TaskPlanner(self.agent_module)
        self.computer_agent = ComputerAgent(self.agent_module)
        self.temp_dir = tempfile.mkdtemp()
        os.environ["NOVA_TEST_MODE"] = "1"
        os.environ["NOVA_TEST_DOCS_DIR"] = self.temp_dir

    def tearDown(self):
        os.environ.pop("NOVA_TEST_DOCS_DIR", None)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Parsing and Planning: The 8 Required Test Cases
    def test_case_1_open_word_essay_pune_100_lines(self):
        cmd = "Open Word and write an essay on Pune of 100 lines."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Pune")
        self.assertEqual(p.length_constraints, {"lines": 100})
        self.assertTrue(p.is_computer_action)
        self.assertTrue(p.is_creative_generation)

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertIn("100 non-empty paragraphs", plan.steps[0].objective)
        self.assertEqual(plan.steps[1].agent, "computer")
        self.assertEqual(plan.steps[1].input_data.get("application"), "word")

    def test_case_2_conversational_prefix_okay_now(self):
        cmd = "Okay, now open Word and write an essay about Pune."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Pune")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.steps[1].agent, "computer")

    def test_case_3_conversational_prefix_could_you_please(self):
        cmd = "Could you please open Word and write about artificial intelligence?"
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_topic, "artificial intelligence")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.steps[1].agent, "computer")

    def test_case_4_paragraph_climate_change_in_notepad(self):
        cmd = "Write a paragraph on climate change in Notepad."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "notepad")
        self.assertEqual(p.content_type, "paragraph")
        self.assertEqual(p.content_topic, "climate change")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.steps[1].agent, "computer")
        self.assertEqual(plan.steps[1].input_data.get("application"), "notepad")

    def test_case_5_open_notepad_write_notes_india(self):
        cmd = "Open Notepad and write notes about India."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "notepad")
        self.assertEqual(p.content_topic, "India")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.steps[1].agent, "computer")

    def test_case_6_open_word_create_document_pune(self):
        cmd = "Open Word and create a document about Pune."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "document")
        self.assertEqual(p.content_topic, "Pune")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.steps[1].agent, "computer")

    def test_case_7_write_essay_save_in_word(self):
        cmd = "Write an essay on Pune and save it in Word."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "word")
        self.assertEqual(p.content_type, "essay")
        self.assertEqual(p.content_topic, "Pune")
        self.assertTrue(p.save_required)
        self.assertEqual(p.save_path, "Essay on Pune.docx")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "compose-and-paste-pipeline")
        self.assertEqual(plan.steps[0].agent, "chat")
        self.assertEqual(plan.steps[1].agent, "computer")
        self.assertTrue(plan.steps[1].input_data.get("save_required"))
        self.assertEqual(plan.steps[1].input_data.get("save_path"), "Essay on Pune.docx")

    def test_case_8_open_browser_search_history_pune(self):
        cmd = "Open the browser and search for the history of Pune."
        p = parse_instruction(cmd)
        self.assertEqual(p.application, "browser")
        self.assertTrue(p.is_browser_action)
        self.assertFalse(p.is_computer_action)
        self.assertEqual(p.content_topic, "the history of Pune")

        plan = self.planner.create_plan(TaskRequest.create(cmd))
        self.assertEqual(plan.source, "fast-search-route")
        self.assertEqual(plan.steps[0].agent, "browser")
        self.assertIn("search the history of Pune", plan.steps[0].objective)

    # 2. Negative Cases: Natural Prepositions
    def test_negative_cases_natural_prepositions(self):
        negatives = [
            "Explain the impact of inflation on economic growth in developing countries",
            "Tell me about the flight to Tokyo",
            "What is happening in the news today?",
            "Search for recipes to cook on weekends",
        ]
        for cmd in negatives:
            p = parse_instruction(cmd)
            self.assertFalse(p.is_computer_action, f"Should not be desktop action: {cmd}")
            self.assertNotIn(p.application, ("tokyo", "economic growth", "developing countries", "weekends"))

    # 3. Application Allowlist Enforcement & Security Validation
    def test_application_allowlist_enforcement(self):
        executor = ActionExecutor()
        blocked_apps = ["powershell.exe", "cmd", "malicious_app", "pune of 100 lines", "wscript"]
        for bad_app in blocked_apps:
            with self.assertRaises(PermissionError):
                executor.launch_app(bad_app)

    # 4. Argument Separation: Preventing Task Injection into Executable Arguments
    def test_argument_separation_in_launcher(self):
        executor = ActionExecutor()
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.pid = 1234
            mock_popen.return_value = mock_proc

            # Natural language command tail must NEVER be appended to CLI executable command
            info = executor.launch_app("word", argument="and write an essay on pune of 100 lines")
            self.assertEqual(info["app"], "word")
            cmd_called = mock_popen.call_args[0][0]
            # Verify the command is just the WINWORD executable and does NOT have the natural language tail
            self.assertEqual(len(cmd_called), 1)
            self.assertIn("winword", cmd_called[0].lower())

    # 5. Task Context Preservation across Multi-Step Pipelines
    def test_task_context_preservation_anaphora_resolution(self):
        context = {
            "previous_results": [
                {
                    "agent": "chat",
                    "status": "completed",
                    "data": {"reply": "This is synthesized content from step 1 about Pune."},
                }
            ]
        }
        resolved, was_anaphoric = self.computer_agent._resolve_anaphoric_content("it", context=context)
        self.assertTrue(was_anaphoric)
        self.assertEqual(resolved, "This is synthesized content from step 1 about Pune.")

    # 6. Pune 100-Line Essay Generation: Exactly 100 Non-Empty Paragraphs
    def test_pune_100_lines_content_generation(self):
        essay = _synthesize_fallback_essay("pune", target_lines=100)
        paras = [p.strip() for p in essay.split("\n") if p.strip()]
        self.assertEqual(len(paras), 100, f"Expected exactly 100 paragraphs, got {len(paras)}")
        self.assertIn("Pune", paras[0])
        self.assertIn("Chhatrapati Shivaji Maharaj", essay)
        self.assertIn("Oxford of the East", essay)
        self.assertIn("Hinjawadi", essay)

    # 7. OpenXML DOCX Creation, Saving, and Verification
    def test_docx_creation_and_verification(self):
        test_file = os.path.join(self.temp_dir, "Essay on Pune.docx")
        paragraphs = [f"Paragraph {i+1}: Detailed historical line about Pune city." for i in range(100)]
        created_path = create_docx(test_file, paragraphs)
        self.assertTrue(os.path.isfile(created_path))

        read_paras = read_docx(created_path)
        self.assertEqual(len(read_paras), 100)
        self.assertEqual(read_paras[0], "Paragraph 1: Detailed historical line about Pune city.")
        self.assertEqual(read_paras[99], "Paragraph 100: Detailed historical line about Pune city.")

    # 8. Save and Verify Document Pipeline
    def test_save_and_verify_document_pipeline(self):
        test_file = os.path.join(self.temp_dir, "Essay on Pune.docx")
        paragraphs = [f"Paragraph {i+1}: Content about Pune." for i in range(100)]
        text_content = "\n".join(paragraphs)

        success, msg, data = _save_and_verify_document(
            app_name="word",
            hwnd=0,
            file_name=test_file,
            text_content=text_content,
            expected_paragraphs=100,
        )
        self.assertTrue(success)
        self.assertTrue(data.get("verified"))
        self.assertEqual(data.get("paragraph_count"), 100)
        self.assertTrue(os.path.isfile(test_file))

    # 9. Closed-Loop Execution of Compound Command in ComputerAgent
    def test_computer_agent_execute_compound_command(self):
        with patch.object(self.computer_agent.inspector, "find_window", return_value={"hwnd": 12345, "title": "Document1 - Word"}):
            with patch.object(self.computer_agent, "_cancelled", return_value=False):
                with patch("nova_agents.specialists.computer_agent.ActionExecutor.launch_app") as mock_launch:
                    with patch("nova_agents.specialists.computer_agent.ActionExecutor.type_text", return_value=True):
                        mock_launch.return_value = {"app": "word", "pid": 9999}
                        req = TaskRequest.create("open Word and write an essay on Pune of 100 lines")
                        res = self.computer_agent.execute(req)
                        self.assertEqual(res.status, "completed")
                        self.assertIn("Word", res.message)
                        self.assertTrue(res.data.get("verified"))


if __name__ == "__main__":
    unittest.main()
