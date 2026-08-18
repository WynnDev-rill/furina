#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc41-validate/termux
STAGE=/tmp/furina-agent-rc42-validate/termux

bash "$ROOT/overrides/android-rc41/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"

python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1])
app=root/'bridge/app'
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')

assert 'versionCode 10042' in gradle
assert "versionName '1.0.0-rc42'" in gradle
assert '"bridge_target": "1.0.0-rc42"' in hub
assert '"bridge_target": "1.0.0-rc41"' not in hub
assert 'FurinaHub-Updater/8' in updater

for marker in (
    'RC42: deterministic mobile crop geometry',
    'touch-action:none!important',
    'function cropCanvasPoint(c,e)',
    'function cropHitMode(c,e,r)',
    "target?.dataset?.handle||cropHitMode(c,e,editorCrop)",
    'o.setPointerCapture(e.pointerId)',
    'o.onlostpointercapture',
    "'ResizeObserver'in window",
    'new ResizeObserver',
    'requestAnimationFrame(()=>requestAnimationFrame(syncEditorLayers))',
    'Math.floor(r.x)',
    'Math.floor(r.y)',
    'Math.ceil(r.x+r.w)',
    'Math.ceil(r.y+r.h)',
    "preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp'",
    "f.fillStyle='#fff'",
):
    assert marker in html, marker

wire=html[html.index('function wireCropOverlay(){'):html.index('function wireEditorCanvas(',html.index('function wireCropOverlay(){'))]
assert 'canvasPoint(c,e)' not in wire
assert 'cropCanvasPoint(c,e)' in wire
assert 'e.pointerId!==drag.pointerId' in wire
assert "e.pointerType==='mouse'&&e.button!==0" in wire

scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_RC52_R22_ANDROID_RC42_CROP_VALIDATION_OK')
PY
