#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.4/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.5/apply.py" "$ROOT"

python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.0.5"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10063' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.5'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.0.5"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r45"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'furina-2026.08.24-private-1.0.5' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for path in core.glob('*.py'): ast.parse(path.read_text(),filename=str(path))
chat=(core/'chat.py').read_text(); memory=(core/'memory.py').read_text(); llm=(core/'llm.py').read_text(); persona=(core/'persona.py').read_text(); hub=(core/'hub.py').read_text(); html=(root/'bridge/app/src/main/assets/furinahub/index.html').read_text()
assert 'config_revision: int = 9' in (core/'config.py').read_text()
for token in ('_assistant_history_safe','_recent_context','_direct_temporal_answer','_local_generation_budget','assistant_history_quarantined'):
    assert token in chat,token
assert 'source="user_evidence"' in chat and 'source="user_evidence_pattern"' in chat
assert 'Legacy model-authored sources are deliberately not trusted as facts' in memory
assert 'repeat_penalty' in llm and 'repeat_last_n' in llm and '1.10 if not json_mode' in llm
assert 'Tsundere adalah warna kepribadian' in persona
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r45"' in hub
start=html.index('async function sendMessage(forcedText)'); end=html.index('\nfunction thinkingArchiveKey()',start); send=html[start:end]
assert '/api/chat/start' in send and 'state.partial' in send
assert 'refreshConversation()' not in send and 'renderBoot()' not in send
print('FURINA_PRIVATE_1_0_5_STRUCTURE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT

FURINA_HOME="$TMP_HOME/memory" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
s=MemoryStore()
s.add_memory('Aku suka membaca novel romance','preference',0.92,confidence=0.96,source='explicit')
s.add_memory('Aku suka bermain dengan Furina sepanjang hari','preference',0.99,confidence=0.99,source='consolidation')
s.add_memory('Targetku menyelesaikan aplikasi pribadi','goal',0.9,confidence=0.92,source='user_evidence')
s.upsert_belief('pattern','Aku sering menghakati orang lain',0.99,source='reflection')
s.upsert_belief('pattern','Aku sering mengembangkan aplikasi',0.88,source='user_evidence_pattern')
s.upsert_belief('pattern','Aku sering mengembangkan aplikasi',0.88,source='user_evidence_pattern')
likes=[m.text for m in s.search('apa yang kusukai?',10)]
assert likes==['Aku suka membaca novel romance'],likes
goals=[m.text for m in s.search('apa tujuanku?',10)]
assert goals==['Targetku menyelesaikan aplikasi pribadi'],goals
assert s.search('apakah aku suka bermain dengan Furina?',10)==[]
patterns=[b.value for b in s.relevant_beliefs('apa yang biasanya aku lakukan?',10)]
assert 'Aku sering menghakati orang lain' not in patterns,patterns
assert 'Aku sering mengembangkan aplikasi' in patterns,patterns
print('FURINA_PRIVATE_1_0_5_PROVENANCE_OK')
PY

FURINA_HOME="$TMP_HOME/history" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from types import SimpleNamespace
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class Dummy: pass
cfg=load_config(); cfg.routing_mode='local'; s=MemoryStore(); c=FurinaChat(cfg,s,Dummy()); p=SimpleNamespace(name='QUICK',instruction='natural',temperature=.8,max_tokens=500)
s.add_message('user','kamu ingat apa yang kusukai?')
bad='Aku suka bermain, dan aku suka ketika kamu menghakati seseorang lain. Aku suka bermain, dan aku suka ketika kamu menghakati seseorang lain. Aku suka bermain, dan aku suka ketika kamu menghakati seseorang lain.'
s.add_message('assistant',bad)
s.add_message('user','oke')
normal=c._messages('hi',p)
assert all(m['role']!='assistant' for m in normal),normal
assert bad not in '\n'.join(m['content'] for m in normal)
cont=c._messages('lanjut',p)
assert bad not in '\n'.join(m['content'] for m in cont)
s.add_message('assistant','Aku tadi cuma bilang bahwa aku senang kamu datang lagi.')
cont2=c._messages('maksudmu?',p)
assert any(m['role']=='assistant' and 'senang kamu datang lagi' in m['content'] for m in cont2),cont2
print('FURINA_PRIVATE_1_0_5_HISTORY_QUARANTINE_OK')
PY

FURINA_HOME="$TMP_HOME/time" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class NoLLM:
    def __init__(self): self.calls=0
    def prewarm_local(self): pass
    def chat(self,*a,**k): self.calls+=1; raise AssertionError('temporal fast path must not call LLM')
cfg=load_config(); cfg.routing_mode='local'; llm=NoLLM(); c=FurinaChat(cfg,MemoryStore(),llm)
a=c.respond('besok hari apa?')
assert a.startswith('Besok ') and len(a)<80,a
assert llm.calls==0
print('FURINA_PRIVATE_1_0_5_TEMPORAL_FAST_PATH_OK',a)
PY

FURINA_HOME="$TMP_HOME/greeting" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class FakeLLM:
    def __init__(self): self.kw=None; self.messages=None
    def prewarm_local(self): pass
    def chat(self,*a,**k):
        self.messages=a[0] if a else k.get('messages',[]); self.kw=k
        return 'Hai, Wynn. Senang lihat kamu lagi.'
cfg=load_config(); cfg.routing_mode='local'; llm=FakeLLM(); c=FurinaChat(cfg,MemoryStore(),llm)
a=c.respond('hi')
assert a.startswith('Hai')
assert llm.kw['max_tokens']<=96,llm.kw
assert llm.kw['temperature']<=.68,llm.kw
sys=llm.messages[0]['content'] if llm.messages else ''
assert 'WAKTU LOKAL TERPERCAYA' in sys and 'SHARED PERSONAL CONTEXT' in sys
print('FURINA_PRIVATE_1_0_5_GREETING_BUDGET_OK')
PY

echo FURINA_PRIVATE_1_0_5_VALIDATION_OK
