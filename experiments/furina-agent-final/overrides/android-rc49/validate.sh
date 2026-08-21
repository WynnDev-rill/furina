#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc48-validate/termux
STAGE=/tmp/furina-agent-rc49-validate/termux

bash "$ROOT/overrides/android-rc48/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1]); app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
main=(app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
assert 'versionCode 10049' in gradle and "versionName '1.0.0-rc49'" in gradle
assert 'opacity:1!important' in html
assert "ctx.drawImage(img,0,0,c.width,c.height)" in html
assert "o.drawImage(src,sx,sy,sw,sh" in html
assert "if(!el.isConnected)return" in html
assert "if(!el.isConnected&&!document.getElementById('messages'))return" not in html
assert 'MediaStore.EXTRA_OUTPUT' in main and 'readCameraImage(Uri uri)' in main
assert 'data.getExtras().get("data")' not in main
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S)
Path('/tmp/furinahub-rc49-inline.js').write_text('\n'.join(scripts),encoding='utf-8')
print('FURINAHUB_RC49_STATIC_REGRESSION_OK')
PY
node --check /tmp/furinahub-rc49-inline.js
printf '%s\n' FURINAHUB_RC49_VALIDATION_OK
