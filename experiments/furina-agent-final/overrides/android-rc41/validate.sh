#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc40-validate/termux
STAGE=/tmp/furina-agent-rc41-validate/termux

bash "$ROOT/overrides/android-rc40/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE_STAGE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"

python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
app=root/'bridge/app'
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')

assert 'versionCode 10041' in gradle
assert "versionName '1.0.0-rc41'" in gradle
assert '"bridge_target": "1.0.0-rc41"' in hub
assert '"bridge_target": "1.0.0-rc40"' not in hub
assert 'FurinaHub-Updater/7' in updater
api=updater.index('api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json')
raw=updater.index('raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/manifest.json')
stable=updater.index('releases/download/furina-update-stable/manifest.json')
bootstrap=updater.index('furina-bootstrap-v1.0.0/experiments/furina-agent-final/manifest.json')
assert api < raw < stable < bootstrap
assert 'RC40: crop overlay must never darken' in html
assert "preserveAlpha=sourceMime==='image/png'||sourceMime==='image/webp'" in html
for p in (
    app/'src/main/res/drawable-nodpi/furinahub_launcher_foreground.jpg',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher.jpg',
    app/'src/main/res/mipmap-xxxhdpi/ic_launcher_round.jpg',
): assert p.is_file(), p
print('FURINAHUB_RC52_R22_ANDROID_RC41_VALIDATION_OK')
PY
