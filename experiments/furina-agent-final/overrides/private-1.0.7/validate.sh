#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.6/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.7/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.0.7"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10065' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.7'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.0.7"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r47"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'furina-2026.08.24-private-1.0.7' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for path in core.glob('*.py'): ast.parse(path.read_text(),filename=str(path))
chat=(core/'chat.py').read_text(); persona=(core/'persona.py').read_text(); hub=(core/'hub.py').read_text()
for token in ('_needs_personal_context','_fresh_social_answer','_local_answer_suspicious','_local_repair_messages','local_answer_repaired'):
    assert token in chat,token
for token in ('Ini CHAT satu-lawan-satu','Jangan menulis dialog pengguna','saya mohon izin'):
    assert token in persona,token
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r47"' in hub
# Preserve 1.0.6 session isolation and 1.0.5 provenance/anti-loop guards.
for token in ('_assistant_history_safe','_recent_context','assistant_history_quarantined'):
    assert token in chat,token
print('FURINA_PRIVATE_1_0_7_STRUCTURE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT

# Exact regression from the screenshot: a fresh "hai" is a Core social turn,
# cannot be transformed into invented roleplay, and does not call the local LLM.
FURINA_HOME="$TMP_HOME/greeting" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class NeverLLM:
    def __init__(self): self.calls=0
    def prewarm_local(self): pass
    def chat(self,*a,**k): self.calls+=1; raise AssertionError('fresh greeting must not call local LLM')
cfg=load_config(); cfg.routing_mode='local'; cfg.user_nickname='Wynn'
store=MemoryStore(); store.create_session_conversation(); llm=NeverLLM(); chat=FurinaChat(cfg,store,llm)
chat._schedule_background=lambda *a,**k: None
chunks=[]; answer=chat.respond('hai',chunks.append)
assert answer=='Hai, Wynn.',answer
assert ''.join(chunks)=='Hai, Wynn.'
assert llm.calls==0
rows=store.recent_messages(4)
assert [r['content'] for r in rows]==['hai','Hai, Wynn.'],rows
print('FURINA_PRIVATE_1_0_7_FRESH_GREETING_OK')
PY

# Fresh filler should be natural and cannot accidentally resume another thread.
FURINA_HOME="$TMP_HOME/filler" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class NeverLLM:
    def prewarm_local(self): pass
    def chat(self,*a,**k): raise AssertionError('fresh hmm must not call local LLM')
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore(); store.create_session_conversation(); chat=FurinaChat(cfg,store,NeverLLM()); chat._schedule_background=lambda *a,**k:None
assert chat.respond('hmm')=='Hm? Ada apa?'
print('FURINA_PRIVATE_1_0_7_FRESH_FILLER_OK')
PY

# Generic local chat must not receive unrelated durable personal memories, but an
# explicit personal-recall query must still use the same trusted shared store.
FURINA_HOME="$TMP_HOME/context" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from types import SimpleNamespace
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class Dummy: pass
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore(); store.create_session_conversation()
store.add_memory('Aku suka membaca novel romance','preference',.95,confidence=.98,source='explicit')
chat=FurinaChat(cfg,store,Dummy()); p=SimpleNamespace(name='QUICK',instruction='natural',temperature=.7,max_tokens=300)
generic='\n'.join(m['content'] for m in chat._messages('ceritakan sesuatu yang lucu',p))
recall='\n'.join(m['content'] for m in chat._messages('kamu ingat apa yang aku suka?',p))
assert 'Aku suka membaca novel romance' not in generic,generic
assert 'Aku suka membaca novel romance' in recall,recall
assert 'THREAD STATE: ini awal thread baru' in generic
print('FURINA_PRIVATE_1_0_7_CONTEXT_ROUTER_OK')
PY

# Catch the exact roleplay/script pattern from the on-device screenshot.
FURINA_HOME="$TMP_HOME/guard" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class Dummy: pass
cfg=load_config(); store=MemoryStore(); chat=FurinaChat(cfg,store,Dummy())
bad='Saya mohon izin untuk menyampaikan pesan baru... "Kamu bosan, ya?" "Kalau kamu suka, kita bisa main game."'
assert chat._local_answer_suspicious('hai',bad,fresh=True)
assert chat._local_answer_suspicious('apa kabar?','Kamu bosan, ya? Kita tadi sedang bermain.',fresh=True)
assert not chat._local_answer_suspicious('apa kabar?','Aku baik. Kamu sendiri gimana?',fresh=True)
print('FURINA_PRIVATE_1_0_7_ROLEPLAY_GUARD_OK')
PY

# If a local model begins in script mode, the held prefix must not be emitted;
# one compact repair pass becomes the visible answer instead.
FURINA_HOME="$TMP_HOME/repair" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class FakeLLM:
    def __init__(self): self.calls=0
    def prewarm_local(self): pass
    def cancel(self): pass
    def chat(self,messages,max_tokens=0,temperature=0,on_token=None,**kw):
        self.calls+=1
        if self.calls==1:
            out='Saya mohon izin untuk menyampaikan pesan baru... "Kamu bosan, ya?"'
        else:
            out='Aku baik. Kamu sendiri gimana?'
        if on_token:
            for piece in (out[:22],out[22:]): on_token(piece)
        return out
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore(); store.create_session_conversation(); llm=FakeLLM(); chat=FurinaChat(cfg,store,llm); chat._schedule_background=lambda *a,**k:None
seen=[]; answer=chat.respond('apa kabar?',seen.append)
assert answer=='Aku baik. Kamu sendiri gimana?',answer
visible=''.join(seen)
assert 'Saya mohon izin' not in visible,visible
assert visible=='Aku baik. Kamu sendiri gimana?',visible
assert llm.calls==2,llm.calls
print('FURINA_PRIVATE_1_0_7_REPAIR_STREAM_OK')
PY

echo FURINA_PRIVATE_1_0_7_VALIDATION_OK
