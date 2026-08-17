#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc34-validate/termux
STAGE=/tmp/furina-agent-rc35-validate/termux

# First reconstruct and validate the exact currently released RC34 + Core RC50 tree.
bash "$ROOT/overrides/android-rc34/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"

# Then advance that known-good staged tree to Core RC51 + Android RC35.
python3 "$ROOT/overrides/rc51/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$ROOT/overrides/rc51/apply.py" "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1])
app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')

assert 'VERSION = "1.0.0-rc51"' in version
assert '"bridge_target": "1.0.0-rc35"' in hub
for marker in (
    'CATATAN VISUAL INTERNAL',
    'Berikan SATU jawaban final sebagai companion',
    'RC35: persistent response activity',
    'Berpikir selama',
    'function archiveThinking(',
    'function restoreThinkingArchive(',
    'function finishThinking(',
    'function reconnectCoreAfterUpdate(',
    'function nativeCoreRecoveryFlow(',
    'Core & dependency terbaru dan sudah terhubung.',
    'id="toolCrop"',
    'id="toolDraw"',
    'id="cropOverlay"',
    'function wireCropOverlay(',
):
    assert marker in html or marker in hub, marker

editor=html[html.index('<div id="imageEditor"'):html.index('<script>')]
for old in ('Asli','>1:1<','>4:3<','>16:9<','>Putar<','>Balik<','>Reset<','Rasio diterapkan'):
    assert old not in editor, old
send=html[html.index('async function sendMessage('):html.index('function renderPluginConfirmation(')]
assert 'thinking.remove()' not in send.split('catch(e){',1)[0]
assert updater.count('for (int attempt = 1; attempt <= 3; attempt++)') >= 2
assert 'versionCode 10035' in gradle
assert "versionName '1.0.0-rc35'" in gradle

scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC35_REGRESSION_OK')
PY
