#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc46/validate.sh"
bash "$ROOT/overrides/android-rc28/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
app=root/'bridge/app'
main=(app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
menu=(app/'src/main/res/drawable/ic_furinahub_menu.xml').read_text(encoding='utf-8')
for marker in (
    'R.drawable.ic_furinahub_menu',
    'Typeface.create("sans-serif", android.graphics.Typeface.BOLD)',
    'lines.length - 14',
    'value.length() > 900',
):
    assert marker in main, marker
for marker in (
    'RC29: mobile-native visual polish',
    'font-family:Roboto,"Noto Sans",Arial,sans-serif',
    'width:min(82vw,304px)',
    'prettyConversationTitle',
    'async function repairPlugin()',
    'Plugin gagal dimulai',
    'statusError',
    'updateError',
):
    assert marker in html, marker
assert 'M4,7 L20,7 M4,12 L20,12 M4,17 L20,17' in menu
assert 'versionCode 10029' in gradle
assert "versionName '1.0.0-rc29'" in gradle
assert 'versionCode 10028' not in gradle
print('FURINAHUB_ANDROID_RC29_REGRESSION_OK')
PY
