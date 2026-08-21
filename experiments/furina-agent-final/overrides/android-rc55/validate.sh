#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc67/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 "$HERE/apply.py" "$STAGE"
python3 - <<'PY'
from pathlib import Path
root=Path('/tmp/furina-agent-rc54-validate/termux')
page=(root/'bridge/app/src/main/assets/furinahub/index.html').read_text()
build=(root/'bridge/app/build.gradle').read_text()
assert "versionCode 10055" in build and "versionName '1.0.0-rc55'" in build
assert 'id="relationshipBaseline"' in page and 'Pasangan' in page
assert 'setRelationshipMode(' not in page and 'id="relationshipMode"' not in page
print('FURINAHUB_ANDROID_RC55_STATIC_OK')
PY
printf '%s\n' FURINAHUB_ANDROID_RC55_VALIDATION_OK
