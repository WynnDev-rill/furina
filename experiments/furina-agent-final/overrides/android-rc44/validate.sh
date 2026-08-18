#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc43-validate/termux
STAGE=/tmp/furina-agent-rc44-validate/termux

bash "$ROOT/overrides/android-rc43/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,sys
root=Path(sys.argv[1]); app=root/'bridge/app'
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
assert 'versionCode 10044' in gradle
assert "versionName '1.0.0-rc44'" in gradle
assert '"bridge_target": "1.0.0-rc44"' in hub
assert 'FurinaHub-Updater/10' in updater
assert 'RC44: one visible canvas is the source of truth' in html
assert 'opacity:1!important' in html
assert 'async function decodeEditorBitmap(source)' in html
assert 'createImageBitmap(packed.blob)' in html
assert "img.src='data:'+packed.blob.type+';base64,'+packed.base64" in html
assert 'function waitEditorImageLoad(img,timeoutMs=8000)' in html
assert "if(img.complete){if(img.naturalWidth>0)resolve();else reject" in html
assert 'Decode gambar melewati batas waktu' in html
assert "ctx.drawImage(decoded.image,0,0,c.width,c.height)" in html
assert "editorSetStatus('Menyiapkan gambar…')" in html
assert 'async function applyImageEdit()' in html
assert 'function canvasBlob(c,mime,quality)' in html
assert 'o.drawImage(src,sx,sy,sw,sh,0,0,sw,sh)' in html
assert 'o.drawImage(draw,sx,sy,sw,sh,0,0,sw,sh)' in html
for forbidden in ('URL.createObjectURL','revokeEditorPreview',"preview.id='editorPreviewImage'",'.editorStage #editorCanvas{opacity:0'):
    assert forbidden not in html, forbidden
scripts=[]
for m in re.finditer(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S):
    scripts.append(m.group(1))
Path('/tmp/furinahub-rc44-inline.js').write_text('\n'.join(scripts),encoding='utf-8')
print('FURINAHUB_RC44_SINGLE_CANVAS_STATIC_OK')
PY
node --check /tmp/furinahub-rc44-inline.js
printf '%s\n' FURINAHUB_RC44_IMAGE_EDITOR_VALIDATION_OK
