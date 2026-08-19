#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc46-validate/termux
STAGE=/tmp/furina-agent-rc47-validate/termux

bash "$ROOT/overrides/android-rc46/validate.sh"
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
assert 'versionCode 10047' in gradle
assert "versionName '1.0.0-rc47'" in gradle
assert '"bridge_target": "1.0.0-rc47"' in hub
assert 'FurinaHub-Updater/13' in updater
assert html.count('function editorSetStatus(')==1
assert "editorSetStatus('Menyiapkan gambar…')" in html
assert 'img.src=editorDataUrl(editorSource)' in html
assert 'createImageBitmap(packed.blob)' not in html
assert 'URL.createObjectURL(blob)' not in html

# Regression for RC46: every named editor helper called by openImageEditor
# must actually exist in the final JS. This catches the exact click failure.
def block(name,next_name):
    starts=[html.find(p+name+'(') for p in ('function ','async function ')]
    starts=[x for x in starts if x>=0]
    assert starts,name
    a=min(starts)
    ends=[html.find(p+next_name+'(',a+1) for p in ('function ','async function ')]
    ends=[x for x in ends if x>=0]
    assert ends,next_name
    return html[a:min(ends)]
open_block=block('openImageEditor','closeImageEditor')
for helper in ('editorDataUrl','waitEditorImageLoad','removeEditorPreview','editorSetStatus','wireEditorCanvas','wireCropOverlay','wireColorRail','setEditorTool','syncEditorLayers'):
    assert re.search(r'(?:async\s+)?function\s+'+re.escape(helper)+r'\s*\(',html),helper
    assert helper+'(' in open_block,helper

scripts=[]
for m in re.finditer(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S): scripts.append(m.group(1))
Path('/tmp/furinahub-rc47-inline.js').write_text('\n'.join(scripts),encoding='utf-8')
print('FURINAHUB_RC47_EDITOR_CLICK_STATIC_OK')
PY
node --check /tmp/furinahub-rc47-inline.js
printf '%s\n' FURINAHUB_RC47_EDITOR_CLICK_VALIDATION_OK
