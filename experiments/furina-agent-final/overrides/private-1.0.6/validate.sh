#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.5/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.6/apply.py" "$ROOT"

python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.0.6"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10064' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.6'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.0.6"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r46"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'furina-2026.08.24-private-1.0.6' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for path in core.glob('*.py'): ast.parse(path.read_text(),filename=str(path))
memory=(core/'memory.py').read_text(); tui=(core/'tui.py').read_text(); hub=(core/'hub.py').read_text(); chat=(core/'chat.py').read_text()
for token in ('def bind_conversation','def create_session_conversation','_conversation_override'):
    assert token in memory,token
for token in ('_TERMUX_CHAT_CONVERSATION_ID = None','def _termux_chat_store','def _ensure_termux_chat_conversation','store = _termux_chat_store()','_ensure_termux_chat_conversation(store)'):
    assert token in tui,token
assert 'create_session_conversation' not in hub
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r46"' in hub
# Existing 1.0.5 quality gates must remain intact.
for token in ('_assistant_history_safe','_recent_context','assistant_history_quarantined'):
    assert token in chat,token
print('FURINA_PRIVATE_1_0_6_STRUCTURE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT

# Short-term message history is session/thread scoped while the persistent
# FurinaHub active conversation is left untouched.
FURINA_HOME="$TMP_HOME/scope" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
hub=MemoryStore()
hub_id=hub.active_conversation_id()
hub.add_message('user','OLD HUB THREAD SENTINEL')
hub.add_message('assistant','Jawaban lama yang hanya milik thread sebelumnya.')

termux=MemoryStore()
termux_id=termux.create_session_conversation('Percakapan baru')
assert termux_id != hub_id,(termux_id,hub_id)
assert termux.active_conversation_id()==termux_id
assert hub.active_conversation_id()==hub_id
assert termux.recent_messages()==[]
termux.add_message('user','halo sesi baru')
termux.add_message('assistant','Halo. Ini sesi Termux yang baru.')
assert [m['content'] for m in termux.recent_messages(4)]==['halo sesi baru','Halo. Ini sesi Termux yang baru.']
assert any(m['content']=='OLD HUB THREAD SENTINEL' for m in hub.recent_messages(6))
assert hub.active_conversation_id()==hub_id
print('FURINA_PRIVATE_1_0_6_THREAD_SCOPE_OK',hub_id,termux_id)
PY

# Long-term personal memory remains shared across conversations/sessions.
FURINA_HOME="$TMP_HOME/memory" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
first=MemoryStore()
first.add_memory('Aku suka membaca novel romance','preference',0.94,confidence=0.97,source='explicit')
second=MemoryStore(); second.create_session_conversation()
texts=[m.text for m in second.search('apa yang kusukai?',8)]
assert texts==['Aku suka membaca novel romance'],texts
print('FURINA_PRIVATE_1_0_6_LONG_TERM_MEMORY_OK')
PY

# A fresh Termux thread receiving "hmm" must not pull assistant history from the
# previous globally active conversation. Within the same new thread, "hmm" can
# still behave as a natural continuation.
FURINA_HOME="$TMP_HOME/continuity" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from types import SimpleNamespace
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
class Dummy: pass
cfg=load_config(); cfg.routing_mode='local'; profile=SimpleNamespace(name='QUICK',instruction='natural',temperature=.7,max_tokens=300)
old=MemoryStore(); old.add_message('user','topik lama'); sentinel='SENTINEL PERCAKAPAN LAMA YANG TIDAK BOLEH MASUK SESI BARU'; old.add_message('assistant',sentinel)
fresh=MemoryStore(); fresh.create_session_conversation(); chat=FurinaChat(cfg,fresh,Dummy())
msgs=chat._messages('hmm',profile); joined='\n'.join(str(m.get('content') or '') for m in msgs)
assert sentinel not in joined,joined
assert all(m['role']!='assistant' for m in msgs),msgs
fresh.add_message('user','aku baru pulang')
fresh.add_message('assistant','Hm, akhirnya pulang juga. Capek?')
msgs2=chat._messages('hmm',profile)
assert any(m['role']=='assistant' and 'akhirnya pulang' in m['content'] for m in msgs2),msgs2
print('FURINA_PRIVATE_1_0_6_FRESH_HMM_OK')
PY

# Instance binding must never mutate the global active-conversation KV, even
# when a second store binds the same Termux process thread again (/back -> Chat).
FURINA_HOME="$TMP_HOME/rebind" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
hub=MemoryStore(); global_id=hub.active_conversation_id()
s1=MemoryStore(); sid=s1.create_session_conversation(); s1.add_message('user','pesan dalam proses yang sama')
s2=MemoryStore(); s2.bind_conversation(sid)
assert s2.active_conversation_id()==sid
assert [m['content'] for m in s2.recent_messages(3)]==['pesan dalam proses yang sama']
assert hub.active_conversation_id()==global_id
s2.bind_conversation(None)
assert s2.active_conversation_id()==global_id
print('FURINA_PRIVATE_1_0_6_REBIND_OK')
PY

echo FURINA_PRIVATE_1_0_6_VALIDATION_OK
