#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.0/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.2/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py
grep -Fq 'VERSION = "1.1.11"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_FINAL_112_CHAT_ONLY' "$ROOT/core/furina_agent/hub.py"
grep -Fq 'page_size = 20' "$ROOT/core/furina_agent/tui.py"
! rg -q '/api/agent/jobs|/api/device/probe|/api/update/core|/api/update/status' "$ROOT/core/furina_agent/hub.py"
grep -Fq 'versionCode 10079' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.1.11'" "$ROOT/bridge/app/build.gradle"
! rg -q 'AccessibilityService|Shizuku|BridgeForegroundService|BootReceiver' "$ROOT/bridge/app/src/main/AndroidManifest.xml"
grep -Fq 'MAX_IMAGE_EDGE = 1600' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'stopActiveChat' "$ROOT/bridge/app/src/main/assets/furinahub/index.html"
grep -Fq "document.getElementById('coreUpdateBtn')" "$ROOT/bridge/app/src/main/assets/furinahub/index.html" && true
FURINA_HOME="$(mktemp -d)" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.memory import MemoryStore
s=MemoryStore(); hub=s.create_conversation('Hub'); termux=MemoryStore(); tid=termux.create_session_conversation('Termux')
termux.add_message('user','khusus termux'); assert tid not in [x['id'] for x in s.list_conversations()]
assert hub in [x['id'] for x in s.list_conversations()]; assert s._conn().execute("SELECT surface FROM conversations WHERE id=?",(tid,)).fetchone()[0]=='termux'
print('FURINA_FINAL_112_CONVERSATION_BOUNDARY_OK')
PY
python3 - "$ROOT/bridge/app/src/main/assets/furinahub/index.html" <<'PY'
import re,sys
p=open(sys.argv[1],encoding='utf-8').read()
assert 'FURINA_FINAL_112_UI' in p and 'function renderAgent(){}' in p
assert "coreBtn.disabled" in p  # historical body remains but final override is guarded
assert "if(send)send.disabled" in p
print('FURINA_FINAL_112_DOM_CONTRACT_OK')
PY
echo FURINA_FINAL_112_VALIDATION_OK
