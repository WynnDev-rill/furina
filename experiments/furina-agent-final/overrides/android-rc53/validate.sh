#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc65-validate/termux; STAGE=/tmp/furina-agent-rc53-validate/termux
HOME="${HOME:-/tmp/furina-validation-home}" FURINA_HOME="${FURINA_HOME:-$HOME}" bash "$ROOT/overrides/rc65/validate.sh"
rm -rf "$STAGE"; mkdir -p "$(dirname "$STAGE")"; cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); app=root/'bridge/app'; java=app/'src/main/java/com/wynndev/furinaagentbridge'
gradle=(app/'build.gradle').read_text(); html=(app/'src/main/assets/furinahub/index.html').read_text(); main=(java/'MainActivity.java').read_text()
assert 'versionCode 10053' in gradle and "versionName '1.0.0-rc53'" in gradle
assert 'EXPECTED_CORE_VERSION = "1.0.0-rc65"' in main
for marker in ('id="today"','async function loadToday()','captureSelected','Usulkan sebagai memori','/api/capture'):
    assert marker in html, marker
print('FURINAHUB_ANDROID_RC53_STATIC_OK')
PY
printf '%s\n' FURINAHUB_ANDROID_RC53_VALIDATION_OK
