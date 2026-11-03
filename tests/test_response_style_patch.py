from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_agent_prompt_has_required_format_and_contextual_emoji_rules():
    source = (ROOT / 'agent.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    style = next(
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'NOVA_RESPONSE_STYLE_INSTRUCTIONS' for target in node.targets)
    )
    assert 'short, meaningful Markdown title' in style
    assert 'concise bullet points' in style
    assert '**Summary:**' in style
    assert '🇪🇺' in style
    assert 'Do not force a generic' in style


def test_fast_greetings_keep_title_points_and_summary():
    source = (ROOT / 'agent.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    greetings_node = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'FAST_GREETING_REPLIES' for target in node.targets)
    )
    greetings = ast.literal_eval(greetings_node)
    assert greetings
    for response in greetings.values():
        assert response.startswith('## ')
        assert '\n\n- ' in response
        assert '**Summary:**' in response


def test_multi_agent_final_synthesis_includes_same_style_contract():
    source = (ROOT / 'nova_agents/specialists/chat_agent.py').read_text(encoding='utf-8')
    assert 'NOVA_RESPONSE_STYLE_INSTRUCTIONS' in source
    assert 'final response specialist' in source
    assert 'Ask exactly one short' in source


def test_frontend_uses_browser_neutral_recognition_and_mutes_browser_capture():
    source = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
    assert "getBrowserSpeechRecognitionConstructor(window)" in source
    assert "recognition.start()" in source
    assert "recognition.start(audioTrack)" not in source
    assert "voiceModeRecognitionRef.current?.abort?.()" in source
    assert "Edge's on-device" not in source
