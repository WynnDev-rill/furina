#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc44-validate/termux
STAGE=/tmp/furina-agent-rc45-validate/termux

bash "$ROOT/overrides/android-rc44/validate.sh"
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
assert 'versionCode 10045' in gradle
assert "versionName '1.0.0-rc45'" in gradle
assert '"bridge_target": "1.0.0-rc45"' in hub
assert 'FurinaHub-Updater/11' in updater
for marker in (
    'let unifiedCoreUpdate=null',
    'async function syncUnifiedUpdateStatus',
    "core('GET','/api/update/status')",
    "window.setInterval(()=>{if(!document.hidden&&connection.connected)syncUnifiedUpdateStatus(true)},4000)",
    "s.result==='updated'",
    'Tidak ada pembaruan terbaru.',
    'Pembaruan berhasil.',
    'Pembaruan gagal pada tahap Core',
):
    assert marker in html, marker
# When connected, stale native updater state must not win over shared Core state.
segment=html[html.index('function refreshNativeCoreUpdate'):html.index('function paintCoreUpdate')]
assert 'if(connection.connected){syncUnifiedUpdateStatus(true);return}' in segment
# Keep RC44 image editor regression coverage.
for marker in ('async function decodeEditorBitmap(source)','createImageBitmap(packed.blob)','async function applyImageEdit()'):
    assert marker in html, marker
scripts=[]
for m in re.finditer(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.I|re.S): scripts.append(m.group(1))
Path('/tmp/furinahub-rc45-inline.js').write_text('\n'.join(scripts),encoding='utf-8')
print('FURINAHUB_RC45_UNIFIED_UPDATE_STATIC_OK')
PY
node --check /tmp/furinahub-rc45-inline.js
printf '%s\n' FURINAHUB_RC45_UNIFIED_UPDATE_VALIDATION_OK
