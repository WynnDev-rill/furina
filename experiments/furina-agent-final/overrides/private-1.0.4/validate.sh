#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.3/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.4/apply.py" "$ROOT"

python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.0.4"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10062' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.4'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.0.4"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r44"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'furina-2026.08.24-private-1.0.4' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

# Exact structural integrity: historical transforms had left callers for
# _consolidate/_reflect/_relationship_context while dropping their definitions.
STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
chat=(core/'chat.py').read_text(); memory=(core/'memory.py').read_text(); hub=(core/'hub.py').read_text(); html=(root/'bridge/app/src/main/assets/furinahub/index.html').read_text(); hub_web=(core/'hub_web.py').read_text()
for path in core.glob('*.py'): ast.parse(path.read_text(),filename=str(path))
tree=ast.parse(chat); cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FurinaChat')
methods=[n.name for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
for name in ('_relationship_context','_shared_context','_consolidate','_reflect','_background_worker_loop'):
    assert methods.count(name)==1,(name,methods.count(name))
assert 'relevant_beliefs' in memory and 'no unrelated importance fallback' in memory
assert 'SHARED PERSONAL CONTEXT' in chat
assert 'memory_worker_error' in chat
assert '/api/chat/start' in hub and 'def start_chat(' in hub and 'partial' in hub
start=html.index('async function sendMessage(forcedText)'); end=html.index('\nfunction thinkingArchiveKey()',start); send=html[start:end]
assert '/api/chat/start' in send and 'state.partial' in send
assert 'refreshConversation()' not in send and 'renderBoot()' not in send
assert 'bubble.textContent=partial' in send
assert 'FURINAHUB_STREAM_V3_NO_RERENDER' in html
assert hub_web.startswith('HTML = ') and repr(html) in hub_web
print('FURINA_PRIVATE_1_0_4_STRUCTURE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
s=MemoryStore()
s.add_memory('Aku suka membaca novel romance','preference',0.92,confidence=0.96,source='explicit')
s.add_memory('Aku suka bermain dengan Furina sepanjang hari','preference',0.95,confidence=0.55,source='consolidation')
s.add_memory('Tujuanku tahun ini menyelesaikan proyek pribadi','goal',0.93,confidence=0.96,source='explicit')
s.upsert_belief('pattern','Sering mengembangkan aplikasi Android pribadi',0.84,source='reflection')
s.upsert_belief('pattern','Sering mengembangkan aplikasi Android pribadi',0.84,source='reflection')

def texts(q): return [m.text for m in s.search(q,10)]
assert texts('apa yang kusukai?')==['Aku suka membaca novel romance'],texts('apa yang kusukai?')
assert texts('apakah kamu ingat tujuanku tahun ini?')==['Tujuanku tahun ini menyelesaikan proyek pribadi']
assert texts('apa itu menghakati?')==[]
assert texts('apakah aku suka bermain dengan Furina?')==[]
assert texts('apa yang biasanya aku lakukan?')==[]
b=[x.value for x in s.relevant_beliefs('apa yang biasanya aku lakukan?',10)]
assert b==['Sering mengembangkan aplikasi Android pribadi'],b
all_recall=texts('apa yang kamu ingat tentang aku?')
assert 'Aku suka membaca novel romance' in all_recall and 'Tujuanku tahun ini menyelesaikan proyek pribadi' in all_recall
assert 'Aku suka bermain dengan Furina sepanjang hari' not in all_recall
print('FURINA_PRIVATE_1_0_4_RETRIEVAL_OK')
PY

# Both engines must receive the same persisted personal fact from the same DB.
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from types import SimpleNamespace
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class DummyLLM: pass
cfg=load_config(); store=MemoryStore(); chat=FurinaChat(cfg,store,DummyLLM())
profile=SimpleNamespace(name='QUICK',instruction='Jawab natural.')
query='apa yang kusukai?'
cfg.routing_mode='local'; local=chat._messages(query,profile)[0]['content']
cfg.routing_mode='online'; online=chat._messages(query,profile)[0]['content']
needle='Aku suka membaca novel romance'
assert needle in local and needle in online
assert 'SHARED PERSONAL CONTEXT' in local and 'SHARED PERSONAL CONTEXT' in online
assert 'Aku suka bermain dengan Furina sepanjang hari' not in local+online
assert chat._evidence_supported('Aku suka teh melati','Aku suka teh melati')
assert not chat._evidence_supported('Aku bertanya soal tujuan','Kamu suka bermain sepanjang hari')
print('FURINA_PRIVATE_1_0_4_CROSS_ENGINE_MEMORY_OK')
PY

# Exercise asynchronous progress independently of a real provider/model.
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import time, types
from furina_agent.hub import RUNTIME

def fake_chat(self,text,image=None,plugins=None,request_id='',on_token=None):
    if on_token:
        on_token('Halo'); time.sleep(.03); on_token(', Wynn')
    return {'mode':'chat','answer':'Halo, Wynn','request_id':request_id,'user_message_id':11,'assistant_message_id':12}
RUNTIME.chat=types.MethodType(fake_chat,RUNTIME)
out=RUNTIME.start_chat('hi',request_id='test-stream-104'); assert out['accepted']
seen_partial=False
for _ in range(100):
    state=RUNTIME.get_chat_progress('test-stream-104')
    if state.get('partial'): seen_partial=True
    if state.get('done'): break
    time.sleep(.02)
assert seen_partial,state
assert state['done'] and state['partial']=='Halo, Wynn'
assert state['result']['assistant_message_id']==12
print('FURINA_PRIVATE_1_0_4_ASYNC_STREAM_OK')
PY

echo FURINA_PRIVATE_1_0_4_VALIDATION_OK
