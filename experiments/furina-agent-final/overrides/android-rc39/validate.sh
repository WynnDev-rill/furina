#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc38-validate/termux
STAGE=/tmp/furina-agent-rc39-validate/termux

bash "$ROOT/overrides/android-rc38/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"

# RC38 carries the bridge target in two generated Core locations. Normalize one
# before the strict RC39 transform so both locations finish on the same target.
python3 - "$STAGE/core/furina_agent/hub.py" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
old='"bridge_target": "1.0.0-rc38"'
new='"bridge_target": "1.0.0-rc39"'
if s.count(old)==2:
    s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
PY

python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1])
app=root/'bridge/app'
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
manifest=(app/'src/main/AndroidManifest.xml').read_text(encoding='utf-8')

assert 'releases/download/furina-update-stable/manifest.json' in updater
assert 'releases/latest/download/manifest.json' not in updater
assert updater.index('releases/download/furina-update-stable/manifest.json') < updater.index('furina-bootstrap-v1.0.0')
assert 'FurinaHub-Updater/5' in updater
assert 'versionCode 10039' in gradle
assert "versionName '1.0.0-rc39'" in gradle
assert hub.count('"bridge_target": "1.0.0-rc39"') >= 1
assert '"bridge_target": "1.0.0-rc38"' not in hub

for marker in (
    'RC39: WhatsApp-inspired crop/draw editor',
    'id="toolCrop"',
    'id="toolDraw"',
    'id="drawCanvas"',
    'id="colorRail"',
    'class="waBrushBar"',
    'function undoDraw(',
    'function setBrushWidth(',
    'function railColorAt(',
): assert marker in html, marker
assert 'Rasio diterapkan saat selesai' not in html
assert '>Putar<' not in html
assert '>Balik<' not in html

assert 'android:icon="@mipmap/ic_launcher"' in manifest
assert 'android:roundIcon="@mipmap/ic_launcher_round"' in manifest
for p in (
    app/'src/main/res/drawable-nodpi/furinahub_launcher_foreground.webp',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher.webp',
    app/'src/main/res/mipmap-anydpi-v26/ic_launcher.xml',
    app/'src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml',
):
    assert p.is_file(), p
assert (app/'src/main/res/drawable-nodpi/furinahub_launcher_foreground.webp').stat().st_size > 4096

scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC39_VALIDATION_OK')
PY
