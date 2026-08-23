#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
# RC55 already reconstructs Core RC67 + Android RC55. Apply Core RC68 on that
# exact stage before the final Android RC56 patch; do not validate RC68 against
# an RC54 Android tree and then skip RC55.
bash "$ROOT/overrides/android-rc55/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 "$ROOT/overrides/rc68/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 - <<'PY'
from pathlib import Path
root=Path('/tmp/furina-agent-rc54-validate/termux')
page=(root/'bridge/app/src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
build=(root/'bridge/app/build.gradle').read_text(encoding='utf-8')
main=(root/'bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java').read_text(encoding='utf-8')
runtime=(root/'bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgeRuntime.java').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc68"' in version
assert "versionCode 10056" in build and "versionName '1.0.0-rc56'" in build
assert 'data-view="relationship"' not in page
assert '<section id="relationship" class="view hidden" aria-hidden="true">' in page
assert 'furina-apk-confirm' in main
assert 'furina-2026.08.23-rc68-rc56' in main+runtime
assert 'EXPECTED_CORE_VERSION = "1.0.0-rc68"' in main
print('FURINAHUB_ANDROID_RC56_STATIC_OK')
PY
printf '%s\n' FURINAHUB_ANDROID_RC56_VALIDATION_OK
