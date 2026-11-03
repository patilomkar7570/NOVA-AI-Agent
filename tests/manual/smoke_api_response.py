"""Local smoke test for the API task -> assistant chat response pipeline."""
import importlib.util
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import ModuleType
from urllib.request import Request, urlopen
from urllib.error import HTTPError

fake = ModuleType('agent')
fake.MODEL = 'qwen3:8b'
fake.QWEN_CONTEXT = 2048
fake.exit_event = threading.Event()
fake.stop_event = threading.Event()
fake._page = None
fake.ACTIVE_SITE = ''
fake.start_agent = lambda: True
fake.close_browser = lambda: None
fake.stop_agent = lambda: fake.stop_event.set()
fake.is_explicit_task_command = lambda command: False
fake.handle_conversation = lambda command: (True, f'Test NOVA reply: {command}')
sys.modules['agent'] = fake

api_path = Path(__file__).resolve().parents[2] / 'api.py'
spec = importlib.util.spec_from_file_location('nova_api_response_smoke', api_path)
api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api
spec.loader.exec_module(api)

with tempfile.TemporaryDirectory() as temp:
    api.CHAT_HISTORY_FILE = Path(temp) / 'chat_history.json'
    chat_id = 'smoke-chat-1'
    api.save_chats([{
        'id': chat_id,
        'title': 'Smoke Test',
        'messages': [{'role': 'user', 'content': 'hello', 'time': time.time()}],
        'created_at': time.time(),
        'updated_at': time.time(),
    }])

    server = api.ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        body = json.dumps({'command': 'hello', 'chat_id': chat_id}).encode()
        request = Request(base + '/api/task', data=body, headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=10) as response:
            queued = json.loads(response.read())
        task_id = queued['task_id']

        final = None
        for _ in range(100):
            with urlopen(base + '/api/task-result?task_id=' + task_id, timeout=5) as response:
                payload = json.loads(response.read())
            if payload['task']['status'] in {'completed', 'failed', 'partial', 'stopped'}:
                final = payload['task']
                break
            time.sleep(0.05)

        assert final is not None, 'Task did not reach a terminal state'
        assert final['agent'] == 'chat', final
        assert final['reply'] == 'Test NOVA reply: hello', final

        chats = api.load_chats()
        messages = chats[0]['messages']
        assert messages[-1]['role'] == 'assistant', messages
        assert messages[-1]['content'] == 'Test NOVA reply: hello', messages
        print('API response-pipeline smoke test passed.')
    finally:
        api._worker_shutdown.set()
        api._task_queue.put(None)
        if api.task_thread and api.task_thread.is_alive():
            api.task_thread.join(timeout=5)
        server.shutdown()
        server.server_close()
