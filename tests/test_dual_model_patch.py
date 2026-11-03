from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DualModelPatchTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_agent_declares_separate_models(self):
        source = self.read("agent.py")
        self.assertIn('os.environ.get("NOVA_MODEL", "qwen3:8b")', source)
        self.assertIn('os.environ.get("NOVA_FAST_CHAT_MODEL", "qwen3:1.7b")', source)

    def test_ask_qwen_defaults_to_main_and_chat_passes_fast_model(self):
        tree = ast.parse(self.read("agent.py"))
        funcs = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        ask = funcs["ask_qwen"]
        self.assertIn("model", [arg.arg for arg in ask.args.args])
        fast = ast.get_source_segment(self.read("agent.py"), funcs["fast_conversation_reply"])
        self.assertIn("model=FAST_CHAT_MODEL", fast)

    def test_planner_keeps_main_model_and_has_fast_route(self):
        source = self.read("nova_agents/planner.py")
        self.assertIn('source="fast-chat-route"', source)
        self.assertIn('getattr(self.agent, "MODEL", "qwen3:8b")', source)
        self.assertIn("keep_alive=-1", source)

    def test_chat_specialist_separates_clarification_and_synthesis_models(self):
        source = self.read("nova_agents/specialists/chat_agent.py")
        self.assertIn('getattr(self.agent, "FAST_CHAT_MODEL", "qwen3:1.7b")', source)
        self.assertIn('getattr(self.agent, "MODEL", "qwen3:8b")', source)
        self.assertIn("keep_alive=-1", source)

    def test_ollama_settings_and_preloader_are_included(self):
        settings = self.read("scripts/configure_ollama_residency.ps1")
        preload = self.read("scripts/preload_nova_models.ps1")
        self.assertIn('OLLAMA_MAX_LOADED_MODELS", "2"', settings)
        self.assertIn('OLLAMA_NUM_PARALLEL", "1"', settings)
        self.assertIn('qwen3:8b', preload)
        self.assertIn('qwen3:1.7b', preload)
        self.assertIn('keep_alive = -1', preload)

if __name__ == "__main__":
    unittest.main(verbosity=2)
