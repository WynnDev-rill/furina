#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.7/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.8/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.0.8"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10066' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.8'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.0.8"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r48"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'furina-2026.08.24-private-1.0.8' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for p in core.glob('*.py'): ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
chat=(core/'chat.py').read_text(); persona=(core/'persona.py').read_text(); llm=(core/'llm.py').read_text(); hub=(core/'hub.py').read_text(); ds=(core/'dialogue_state.py').read_text()
assert 'from .dialogue_state import DialogueStateBuilder' in chat
assert 'DIALOGUE STATE' in ds and 'unverified_character_utterance' in ds and 'rejected_or_corrected_by_user' in ds
assert 'chemistry dua arah' in persona and 'Jika tebakanmu dikoreksi' in persona
for removed in ('def _fresh_social_answer','def _local_answer_suspicious','def _local_repair_messages','def _direct_temporal_answer','def _needs_personal_context','def _needs_temporal_context'):
    assert removed not in chat, removed
assert 'DialogueStateBuilder.build(history, user_text)' in chat
assert 'Every conversational answer comes from the selected model' in chat
assert 'presence_penalty' in llm and 'qwen_heretic' in llm
assert 'top_p = 0.80; top_k = 20' in llm
assert 'top_p = 0.86; top_k = 30' in llm
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r48"' in hub
print('FURINA_PRIVATE_1_0_8_STRUCTURE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT

# Dialogue state must separate user truth from Furina's prior improvisation.
PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.dialogue_state import DialogueStateBuilder
fresh=DialogueStateBuilder.build([], 'p')
assert fresh.fresh_thread and fresh.latest_user_move=='low_information'
assert not fresh.topic_anchor and not fresh.assistant_continuity
history=[{'role':'user','content':'p'},{'role':'assistant','content':'Hai... kamu lagi bosan ya?'}]
rejected=DialogueStateBuilder.build(history,'tidak juga')
assert not rejected.fresh_thread
assert rejected.latest_user_move=='correction_or_rejection'
assert rejected.assistant_continuity[-1][0]=='rejected_or_corrected_by_user'
assert rejected.topic_anchor==''
continued=DialogueStateBuilder.build([
 {'role':'user','content':'aku baru pulang dari kerja dan capek sedikit'},
 {'role':'assistant','content':'Kamu pasti marah padaku.'},
], 'maksud?')
assert continued.latest_user_move=='clarification_request'
assert continued.topic_anchor=='aku baru pulang dari kerja dan capek sedikit'
assert continued.assistant_continuity[-1][0]=='user_requests_clarification'
print('FURINA_108_DIALOGUE_STATE_OK')
PY

# No conversational fast response: even greetings and one-letter messages must
# reach the selected local model. The model decides wording; Core only grounds.
FURINA_HOME="$TMP_HOME/model-call" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
class FakeLLM:
    def __init__(self): self.calls=[]
    def prewarm_local(self): return None
    def cancel(self): return None
    def chat(self,messages,**kwargs):
        self.calls.append((messages,kwargs))
        if kwargs.get('on_token'): kwargs['on_token']('model-output')
        return 'model-output'
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore(); llm=FakeLLM(); chat=FurinaChat(cfg,store,llm)
chat._schedule_background=lambda *a,**k: None
visible=[]
answer=chat.respond('hai',on_token=visible.append)
assert answer=='model-output' and visible==['model-output'] and len(llm.calls)==1
assert llm.calls[0][0][-1]=={'role':'user','content':'hai'}
# A second tiny turn also stays model-generated, not a canned branch.
answer2=chat.respond('p')
assert answer2=='model-output' and len(llm.calls)==2
print('FURINA_108_NO_CANNED_CHAT_OK')
PY

# Local prompt should be a compact composed state, not raw assistant-role replay.
FURINA_HOME="$TMP_HOME/context" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from types import SimpleNamespace
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
class Dummy: pass
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore()
store.add_message('user','p'); store.add_message('assistant','Hai... kamu lagi bosan ya?')
chat=FurinaChat(cfg,store,Dummy())
profile=SimpleNamespace(name='QUICK',instruction='natural',temperature=.7,max_tokens=300)
msgs=chat._messages('tidak juga',profile)
assert len(msgs)==2 and msgs[0]['role']=='system' and msgs[1]=={'role':'user','content':'tidak juga'},msgs
system=msgs[0]['content']
assert 'rejected_or_corrected_by_user' in system
assert 'Hai... kamu lagi bosan ya?' in system
assert 'hanya continuity, bukan fakta tentang user' in system
print('FURINA_108_COMPOSED_CONTEXT_OK',len(system))
PY

# Unrelated trusted memory should not be dumped into a meaningless one-letter
# turn, while an actual recall question must still retrieve the shared store.
FURINA_HOME="$TMP_HOME/memory" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from types import SimpleNamespace
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
class Dummy: pass
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore()
store.add_memory('Aku suka membaca novel romance','preference',0.95,confidence=0.98,source='explicit')
chat=FurinaChat(cfg,store,Dummy()); profile=SimpleNamespace(name='QUICK',instruction='natural',temperature=.7,max_tokens=300)
generic='\n'.join(m['content'] for m in chat._messages('p',profile))
recall='\n'.join(m['content'] for m in chat._messages('apa yang kamu ingat tentang kesukaanku membaca?',profile))
assert 'Aku suka membaca novel romance' not in generic,generic
assert 'Aku suka membaca novel romance' in recall,recall
print('FURINA_108_MEMORY_RELEVANCE_OK')
PY

echo FURINA_PRIVATE_1_0_8_VALIDATION_OK
