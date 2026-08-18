#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc39-validate/termux
STAGE=/tmp/furina-agent-rc40-validate/termux

bash "$ROOT/overrides/android-rc39/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"

python3 "$ROOT/overrides/rc52/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"

python3 -m py_compile "$ROOT/overrides/rc52/apply.py" "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" "$REPO/furinahub.png" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile

root=Path(sys.argv[1])
source_icon=Path(sys.argv[2])
app=root/'bridge/app'
routing=(root/'core/furina_agent/routing.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
manifest=(app/'src/main/AndroidManifest.xml').read_text(encoding='utf-8')

assert 'VERSION = "1.0.0-rc52"' in version
assert 'versionCode 10040' in gradle
assert "versionName '1.0.0-rc40'" in gradle
assert hub.count('"bridge_target": "1.0.0-rc40"') >= 1
assert '"bridge_target": "1.0.0-rc39"' not in hub
assert 'FurinaHub-Updater/6' in updater

local_pos=routing.index('if self.cfg.routing_mode == "local":', routing.index('def chat('))
ensure_pos=routing.index('if not self._ensure_local():', local_pos)
chat_pos=routing.index('answer = self.local.chat(', ensure_pos)
assert local_pos < ensure_pos < chat_pos
assert 'if self.cfg.routing_mode in {"auto", "online"}:' in routing
assert 'if self._ensure_local():' in routing
assert 'deadline = time.monotonic() + 12.0' in routing
assert 'time.sleep(0.25)' in routing

for marker in (
    'RC40: crop overlay must never darken',
    'background-color:transparent!important',
    "preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp'",
    "f.fillStyle='#fff'",
    'function wireCropOverlay(){',
    'o.setPointerCapture(e.pointerId)',
):
    assert marker in html, marker
assert "toDataURL('image/jpeg',.92)" not in html

assert source_icon.read_bytes().startswith(b'\xff\xd8\xff')
for p in (
    app/'src/main/res/drawable-nodpi/furinahub_launcher_foreground.jpg',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher.jpg',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher_round.jpg',
):
    assert p.is_file(), p
    assert p.read_bytes() == source_icon.read_bytes(), p
for stale in (
    app/'src/main/res/drawable-nodpi/furinahub_launcher_foreground.webp',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher.webp',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher_round.webp',
):
    assert not stale.exists(), stale
assert 'android:icon="@mipmap/ic_launcher"' in manifest
assert 'android:roundIcon="@mipmap/ic_launcher_round"' in manifest

scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_RC52_R21_ANDROID_RC40_VALIDATION_OK')
PY
