#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc51-validate/termux; STAGE=/tmp/furina-agent-rc64-validate/termux
# RC64 must start from the actual shared RC63/RC51 bundle.  Testing only the
# Core would miss Android-version migration errors before the RC52 build.
bash "$ROOT/overrides/android-rc51/validate.sh"
rm -rf "$STAGE"; mkdir -p "$(dirname "$STAGE")"; cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
FURINA_HOME=/tmp/furina-rc64-home python3 - "$STAGE" <<'PY'
import importlib.util,sys
from pathlib import Path
root=Path(sys.argv[1]); sys.path.insert(0,str(root/'core'))
from furina_agent.memory import MemoryStore
from furina_agent.lite_full import ProductWorkspace
w=ProductWorkspace(MemoryStore(Path('/tmp/furina-rc64-home/data/test.db')))
assert w.change_focus({'action':'add','text':'uji Furina Lite','when':'besok sore'})['focus']
proposal=w.propose_memory('Wynn menyukai Furina')
inbox=proposal['memory_inbox']; assert inbox
w.decide_memory(inbox[0]['id'],'accept')
assert w.set_profile('natural')['current']=='natural'
print('FURINA_RC64_WORKSPACE_RUNTIME_OK')
PY
python3 -m compileall -q "$STAGE/core/furina_agent"
grep -Fq 'VERSION = "1.0.0-rc64"' "$STAGE/core/furina_agent/version.py"
grep -Fq 'Furina Lite · Termux' "$STAGE/core/furina_agent/tui.py"
grep -Fq 'path == "/api/focus"' "$STAGE/core/furina_agent/hub.py"
printf '%s\n' FURINA_RC64_VALIDATION_OK
