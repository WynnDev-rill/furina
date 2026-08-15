#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

# RC47 validation reconstructs a deterministic RC46 foundation and then applies
# the Core RC47 skill layer. From that same stage, layer only the Android
# bridge transforms so neither validator silently rolls the Core backward.
bash "$ROOT/overrides/rc47/validate.sh"
python3 "$ROOT/overrides/android-rc29/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$ROOT/overrides/android-rc29/apply.py" "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
settings=(root/'core/furina_agent/hub_settings.py').read_text(encoding='utf-8')
direct=(root/'core/furina_agent/direct_control.py').read_text(encoding='utf-8')
assert 'RC30: single-owner WindowInsets' in html
assert '.chatview{height:100%' in html
assert '.composer{padding:7px 12px 7px}' in html
assert '.drawer{padding:14px 10px 14px}' in html
assert 'M9 4v5M15 4v5' in html
assert 'versionCode 10030' in gradle
assert "versionName '1.0.0-rc30'" in gradle
assert 'VERSION = "1.0.0-rc47"' in version
assert '"bridge_target": "1.0.0-rc30"' in hub
for marker in ('"app_launcher": True', '"screen_reader": True', '"workflow_macros": True'):
    assert marker in settings, marker
for marker in ('def _screen_summary(', 'def _try_macro(', 'self._skill("form_fill")'):
    assert marker in direct, marker
print('FURINAHUB_ANDROID_RC30_REGRESSION_OK')
PY
