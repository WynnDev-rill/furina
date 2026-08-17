#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc36-validate/termux
STAGE=/tmp/furina-agent-rc37-validate/termux

bash "$ROOT/overrides/android-rc36/validate.sh"
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
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
assert 'releases/download/furina-update-stable/manifest.json' in updater
assert 'api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/manifest.json' in updater
assert 'application/vnd.github.raw+json' in updater
assert 'FurinaHub-Updater/3' in updater
assert 'versionCode 10037' in gradle
assert "versionName '1.0.0-rc37'" in gradle
assert '"bridge_target": "1.0.0-rc37"' in hub
assert 'id="allUpdateBtn"' in html
scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC37_UPDATE_CHECK_OK')
PY
