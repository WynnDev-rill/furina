#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc47-validate/termux
STAGE=/tmp/furina-agent-rc48-validate/termux

bash "$ROOT/overrides/android-rc47/validate.sh"
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
assert 'versionCode 10048' in gradle
assert "versionName '1.0.0-rc48'" in gradle
assert '"bridge_target": "1.0.0-rc48"' in hub
assert 'FurinaHub-Updater/14' in updater
assert '.editorStage{position:relative;' in html
assert '.editorPreviewImage{position:absolute!important;' in html
assert 'img.src=editorDataUrl(editorSource)' in html
assert 'stage.insertBefore(img,c.nextSibling)' in html
assert 'createImageBitmap(packed.blob)' not in html
assert 'URL.createObjectURL(blob)' not in html

# Offline/online must not affect editing. The editor must consume the local
# Base64 attachment directly and must not make a Core or network request.
def block(name,next_name):
    starts=[html.find(p+name+'(') for p in ('function ','async function ')]
    starts=[x for x in starts if x>=0]; assert starts,name
    a=min(starts)
    ends=[html.find(p+next_name+'(',a+1) for p in ('function ','async function ')]
    ends=[x for x in ends if x>=0]; assert ends,next_name
    return html[a:min(ends)]
open_block=block('openImageEditor','closeImageEditor')
assert 'editorDataUrl(editorSource)' in open_block
for forbidden in ('core(', 'fetch(', 'http://', 'https://'):
    assert forbidden not in open_block, forbidden

# Geometry contract: syncEditorLayers computes offsets from editorStage, so
# editorStage must establish the containing block for the absolute preview.
sync_block=block('syncEditorLayers','syncCropOverlay')
assert 'sr=stage.getBoundingClientRect()' in sync_block
assert "preview.style.left=left+'px'" in sync_block
assert "preview.style.top=top+'px'" in sync_block

scripts=[]
for m in re.finditer(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S): scripts.append(m.group(1))
Path('/tmp/furinahub-rc48-inline.js').write_text('\n'.join(scripts),encoding='utf-8')
print('FURINAHUB_RC48_EDITOR_POSITION_STATIC_OK')
PY
node --check /tmp/furinahub-rc48-inline.js
printf '%s\n' FURINAHUB_RC48_EDITOR_POSITION_VALIDATION_OK
