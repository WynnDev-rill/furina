#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/android-rc56/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 "$ROOT/overrides/rc69/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 - <<'PY'
from pathlib import Path
root=Path('/tmp/furina-agent-rc54-validate/termux')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
build=(root/'bridge/app/build.gradle').read_text(encoding='utf-8')
main=(root/'bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc69"' in version
assert 'UPDATE_PROTOCOL = "furina-update/1"' in version
assert "versionCode 10057" in build and "versionName '1.0.0-rc57'" in build
assert 'furina-2026.08.23-rc69-rc57' in main
assert 'EXPECTED_CORE_VERSION = "1.0.0-rc69"' in main
assert '"bridge_target": "1.0.0-rc57"' in hub
print('FURINAHUB_ANDROID_RC57_STATIC_OK')
PY
printf '%s\n' FURINAHUB_ANDROID_RC57_VALIDATION_OK
