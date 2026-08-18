#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc42-validate/termux
STAGE=/tmp/furina-agent-rc43-validate/termux

bash "$ROOT/overrides/android-rc42/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1])
app=root/'bridge/app'
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
assert 'versionCode 10043' in gradle
assert "versionName '1.0.0-rc43'" in gradle
assert '"bridge_target": "1.0.0-rc43"' in hub
assert '"bridge_target": "1.0.0-rc42"' not in hub
assert 'FurinaHub-Updater/9' in updater
assert 'RC42: deterministic mobile crop geometry' in html
assert 'RC43: decoded IMG preview' in html
assert 'async function decodeEditorImage(source)' in html
assert 'await img.decode()' in html
assert 'new Blob([bytes]' in html
assert 'editorMimeFromBytes' in html
assert "preview.id='editorPreviewImage'" in html
assert "ctx.drawImage(img,0,0,c.width,c.height)" in html
assert "preview.style.width=cr.width+'px'" in html
assert 'Math.floor(r.x)' in html and 'Math.ceil(r.x+r.w)' in html
scripts=[]
for m in re.finditer(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S):
    scripts.append(m.group(1))
Path('/tmp/furinahub-rc43-inline.js').write_text('\n'.join(scripts),encoding='utf-8')
print('FURINAHUB_RC43_IMAGE_PREVIEW_STATIC_OK')
PY
node --check /tmp/furinahub-rc43-inline.js
printf '%s\n' FURINAHUB_RC43_IMAGE_PREVIEW_VALIDATION_OK
