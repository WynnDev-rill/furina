#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.2/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.3/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py
grep -Fq 'VERSION = "1.1.12"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_FINAL_113_NO_DEVICE_CONTROL' "$ROOT/core/furina_agent/tui.py"
grep -Fq 'FURINA_FINAL_113_CHAT_ONLY_CLASSIFIER' "$ROOT/core/furina_agent/companion.py"
FURINA_HOME="$(mktemp -d)" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
s=MemoryStore(); s.create_conversation('Hub'); s.add_message('user','pesan dari Hub')
t=MemoryStore(); t.create_session_conversation('Termux'); t.add_message('assistant','jawaban dari Termux')
shared=t.cross_surface_recent_messages(); assert any('Hub' in x['content'] for x in shared),shared
from furina_agent.config import load_config
assert load_config().device_control_mode == 'normal'
from furina_agent.companion import CompanionSession
assert 'FURINA_FINAL_113_CHAT_ONLY_CLASSIFIER'
print('FURINA_FINAL_113_SHARED_CONTEXT_AND_NO_CONTROL_OK')
PY
python3 - "$ROOT/core/furina_agent/tui.py" <<'PY'
import ast,sys
tree=ast.parse(open(sys.argv[1],encoding='utf-8').read())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_settings_113')
strings={n.value for n in ast.walk(fn) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
assert 'Kontrol perangkat' not in strings
assert {'Identitas','Sistem','Backup','Update & Recovery','Kembali'} <= strings
print('FURINA_FINAL_113_TERMUX_SETTINGS_OK')
PY
echo FURINA_FINAL_113_VALIDATION_OK
