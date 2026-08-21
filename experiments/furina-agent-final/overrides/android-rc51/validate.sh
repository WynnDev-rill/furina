#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc63-validate/termux
STAGE=/tmp/furina-agent-rc51-validate/termux
bash "$ROOT/overrides/rc63/validate.sh"
rm -rf "$STAGE"; mkdir -p "$(dirname "$STAGE")"; cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); app=root/'bridge/app'; java=app/'src/main/java/com/wynndev/furinaagentbridge'
g=(app/'build.gradle').read_text(); main=(java/'MainActivity.java').read_text(); editor=(java/'NativeImageEditorActivity.java').read_text()
assert 'versionCode 10051' in g and "versionName '1.0.0-rc51'" in g
assert 'furina-2026.08.21-rc63-rc51' in main
assert 'EXPECTED_CORE_VERSION = "1.0.0-rc63"' in main
assert 'addTool(bar, doneButton, 96, 10)' in editor
assert 'status.setSingleLine(true)' in editor
assert 'editor.setPadding(dp(16), dp(10), dp(16), bottom + dp(16))' in editor
assert 'roundBackground(mode == EditorView.MODE_CROP' in editor
print('FURINAHUB_ANDROID_RC51_UI_STATIC_OK')
PY
printf '%s\n' FURINAHUB_ANDROID_RC51_VALIDATION_OK
