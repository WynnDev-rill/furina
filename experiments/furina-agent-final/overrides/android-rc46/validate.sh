#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc45-validate/termux
STAGE=/tmp/furina-agent-rc46-validate/termux

bash "$ROOT/overrides/android-rc45/validate.sh"
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
gradle=(app/'build.gradle').read_text(); hub=(root/'core/furina_agent/hub.py').read_text(); updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(); html=(app/'src/main/assets/furinahub/index.html').read_text()
assert 'versionCode 10046' in gradle
assert "versionName '1.0.0-rc46'" in gradle
assert '"bridge_target": "1.0.0-rc46"' in hub
assert 'FurinaHub-Updater/12' in updater
for marker in ('function editorDataUrl(source)','img.src=editorDataUrl(editorSource)','waitEditorImageLoad(img)','editorPreviewImage','o.drawImage(preview,sx*nx','RC46: direct decoded IMG preview','async function applyImageEdit()'):
    assert marker in html,marker
for forbidden in ('createImageBitmap(packed.blob)','URL.createObjectURL(blob)','ctx.drawImage(decoded.image'):
    assert forbidden not in html,forbidden
# Direct preview must override RC44's hidden preview rule later in CSS.
assert html.rfind('.editorPreviewImage{') > html.find('RC44: one visible canvas')
scripts=[]
for m in re.finditer(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S): scripts.append(m.group(1))
Path('/tmp/furinahub-rc46-inline.js').write_text('\n'.join(scripts))
print('FURINAHUB_RC46_DIRECT_IMAGE_STATIC_OK')
PY
node --check /tmp/furinahub-rc46-inline.js
printf '%s\n' FURINAHUB_RC46_DIRECT_IMAGE_VALIDATION_OK
