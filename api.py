import json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
import agent

HOST='127.0.0.1'; PORT=8000
CHAT_HISTORY_FILE=PROJECT_DIR/'chat_history.json'
_lock=threading.Lock(); _task_running=False; _task_thread=None; _events=[]

def add_event(message):
    message=str(message).strip()
    if message:
        with _lock:
            _events.append({'time':time.strftime('%H:%M:%S'),'message':message})
            del _events[:-300]

def load_chats():
    if not CHAT_HISTORY_FILE.exists(): return []
    try:
        data=json.loads(CHAT_HISTORY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data,list) else []
    except Exception as e:
        add_event(f'Could not read chat history: {e}'); return []

def save_chats(data):
    try:
        tmp=CHAT_HISTORY_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(CHAT_HISTORY_FILE); return True
    except Exception as e:
        add_event(f'Could not save chat history: {e}'); return False

def make_chat_title(command):
    try:
        from ollama import chat
        r=chat(model='qwen3:8b',messages=[{'role':'user','content':f'Create a short 2-6 word title for this conversation. Return only the title.\n\nFirst prompt: {command}'}],think=False)
        title=' '.join(str(r.message.content).strip().strip('"\'`').split())
        if title: return title[:80]
    except Exception as e: add_event(f'Local title generation unavailable: {e}')
    return ' '.join(command.split()[:7])[:80] or 'New Chat'

def run_agent(command):
    global _task_running,_task_thread
    with _lock: _task_running=True
    add_event(f'Starting task: {command}')
    try:
        result=agent.run_task(command)
        if result is not None: add_event(result)
        add_event('Task finished.')
    except Exception as e: add_event(f'Task error: {e}')
    finally:
        with _lock: _task_running=False; _task_thread=None

def start_task(command):
    global _task_thread
    with _lock:
        if _task_running: return False,'A task is already running.'
        _task_thread=threading.Thread(target=run_agent,args=(command,),daemon=True); _task_thread.start()
    return True,'Task started.'

def stop_task():
    try:
        if hasattr(agent,'stop_agent'): agent.stop_agent(); add_event('Stop requested.'); return True,'Stop requested.'
        return False,'agent.py does not expose stop_agent().'
    except Exception as e: return False,str(e)

class Handler(BaseHTTPRequestHandler):
    def send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Access-Control-Allow-Origin','http://localhost:5173'); self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers(); self.wfile.write(body)
    def read_json(self):
        try: return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')) or 0).decode() or '{}')
        except: return {}
    def do_OPTIONS(self): self.send_json(204,{})
    def do_GET(self):
        if self.path=='/api/health': return self.send_json(200,{'ok':True,'service':'NOVA backend'})
        if self.path=='/api/status':
            with _lock: running=_task_running
            return self.send_json(200,{'running':running,'backend':'online'})
        if self.path=='/api/events':
            with _lock: events=list(_events)
            return self.send_json(200,{'events':events})
        if self.path=='/api/chats': return self.send_json(200,{'chats':load_chats()})
        self.send_json(404,{'error':'Not found'})
    def do_POST(self):
        d=self.read_json()
        if self.path=='/api/task':
            c=str(d.get('command','')).strip()
            if not c: return self.send_json(400,{'ok':False,'error':'Command is required.'})
            ok,msg=start_task(c); return self.send_json(200 if ok else 409,{'ok':ok,'message':msg} if ok else {'ok':False,'error':msg})
        if self.path=='/api/stop':
            ok,msg=stop_task(); return self.send_json(200 if ok else 500,{'ok':ok,'message':msg})
        if self.path=='/api/chats':
            c=str(d.get('command','')).strip()
            if not c: return self.send_json(400,{'ok':False,'error':'Command is required.'})
            chats=load_chats(); item={'id':str(int(time.time()*1000)),'title':make_chat_title(c),'created_at':time.strftime('%Y-%m-%dT%H:%M:%S'),'messages':[{'role':'user','content':c}]}; chats.insert(0,item); save_chats(chats); return self.send_json(200,{'ok':True,'chat':item})
        if self.path=='/api/chats/append':
            cid=str(d.get('chat_id','')); c=str(d.get('command','')).strip(); chats=load_chats()
            for item in chats:
                if str(item.get('id'))==cid:
                    item.setdefault('messages',[]).append({'role':'user','content':c}); save_chats(chats); return self.send_json(200,{'ok':True,'chat':item})
            return self.send_json(404,{'ok':False,'error':'Chat not found.'})
        if self.path=='/api/chats/delete':
            cid=str(d.get('chat_id','')); chats=[x for x in load_chats() if str(x.get('id'))!=cid]; save_chats(chats); return self.send_json(200,{'ok':True,'chats':chats})
        self.send_json(404,{'error':'Not found'})
    def log_message(self,*args): pass

if __name__=='__main__':
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'NOVA backend running on http://{HOST}:{PORT}')
    print('Google OAuth is not used by this backend.')
    print('Chat history: '+str(CHAT_HISTORY_FILE))
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nNOVA backend stopped.')
    finally: server.server_close()
