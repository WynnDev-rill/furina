#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.6/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

test ! -e "$ROOT/bridge/app/build/outputs/apk/release/app-release.apk"
grep -Fq 'VERSION = "1.1.16"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_116_INDEXED_CONVERSATION_RECALL' "$ROOT/core/furina_agent/memory.py"
grep -Fq 'FURINA_TERMUX_116_ADAPTIVE_RECALL' "$ROOT/core/furina_agent/chat.py"
grep -Fq 'FURINA_TERMUX_116_DELETE_MODEL' "$ROOT/core/furina_agent/local_models.py"
grep -Fq 'for row in range(10)' "$ROOT/core/furina_agent/tui.py"

TMP_HOME="$(mktemp -d)"
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from pathlib import Path
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent import local_models
from furina_agent.personality import TRAITS
from furina_agent.chat import FurinaChat
from furina_agent.response import choose_profile

store=MemoryStore()
old=store.create_session_conversation('lama')
store.add_message('user','Aku lebih suka jawaban ringkas dan langsung ke inti.')
store.add_message('assistant','Baik.')
new=store.create_session_conversation('baru')
assert old != new
hits=store.search_conversation_context('tolong jawab dengan ringkas',4)
assert hits and 'jawaban ringkas' in hits[-1]['content'],hits
assert len(hits)<=4
cfg=load_config(); cfg.routing_mode='local'
chat=FurinaChat(cfg,store,object())
messages=chat._messages('tolong jawab dengan ringkas',choose_profile('tolong jawab dengan ringkas',store))
assert len(messages)==2 and 'PERCAKAPAN LAMA YANG RELEVAN' in messages[0]['content']
assert 'Aku lebih suka jawaban ringkas' in messages[0]['content']

assert len(TRAITS)==20
item=local_models.CATALOG[0]; target=local_models.path_for(item)
target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b'GGUF-test')
local_models._verified_marker(target).write_text('{}')
freed=local_models.delete_model(item['id'])
assert freed==9 and not target.exists() and not local_models._verified_marker(target).exists()
print('FURINA_TERMUX_116_MEMORY_MODEL_TRAITS_OK')
PY

python3 "$PROJECT/overrides/runtime-private-1.1.7/build_client.py" \
  "$PROJECT/overrides/runtime-r39/update_client.py" /tmp/furina-update-1.1.16.py
python3 -m py_compile /tmp/furina-update-1.1.16.py
grep -Fq 'FURINA_TERMUX_ONLY_UPDATER_116' /tmp/furina-update-1.1.16.py
grep -Fq 'Pembaruan Core selesai' /tmp/furina-update-1.1.16.py
if grep -Fq 'changed_apk = sync_apk' /tmp/furina-update-1.1.16.py; then
  echo 'APK sync remains active' >&2; exit 1
fi
echo FURINA_TERMUX_116_VALIDATION_OK
