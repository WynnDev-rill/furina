#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc52-validate/termux; STAGE=/tmp/furina-agent-rc65-validate/termux
# RC65 extends the actual RC52 shared bundle, not the Core-only RC64 stage.
HOME="${HOME:-/tmp/furina-validation-home}" FURINA_HOME="${FURINA_HOME:-$HOME}" bash "$ROOT/overrides/android-rc52/validate.sh"
rm -rf "$STAGE"; mkdir -p "$(dirname "$STAGE")"; cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
FURINA_HOME="/tmp/furina-rc65-home" PYTHONPATH="$STAGE/core" python3 - <<'PY'
from furina_agent.lite_full import ProductWorkspace
from furina_agent.memory import MemoryStore
w=ProductWorkspace(MemoryStore())
w.capture({'action':'focus','text':'Tinjau rencana Furina','when':'besok sore'})
w.capture({'action':'memory','text':'Wynn ingin memori yang dapat ditinjau','source_ref':'test'})
b=w.brief()
assert b['focus_count'] >= 1 and b['memory_inbox_count'] >= 1
print('FURINA_RC65_CAPTURE_RUNTIME_OK')
PY
python3 - "$STAGE" <<'PY'
from pathlib import Path
import ast,sys
c=Path(sys.argv[1])/'core/furina_agent'
for p in ('hub.py','tui.py','lite_full.py'): ast.parse((c/p).read_text(encoding='utf-8'))
h=(c/'hub.py').read_text(encoding='utf-8'); t=(c/'tui.py').read_text(encoding='utf-8')
assert '/api/capture' in h and '/api/workspace/brief' in h and 'capture_from_conversation' in h
assert 'Hari ini' in t and '_lite_today' in t
print('FURINA_RC65_STATIC_OK')
PY
printf '%s\n' FURINA_RC65_VALIDATION_OK
