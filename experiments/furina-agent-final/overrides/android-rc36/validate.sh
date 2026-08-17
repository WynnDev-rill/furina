#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE_STAGE=/tmp/furina-agent-rc35-validate/termux
STAGE=/tmp/furina-agent-rc36-validate/termux

bash "$ROOT/overrides/android-rc35/validate.sh"
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
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
updater=(app/'src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')

assert 'VERSION = "1.0.0-rc51"' in version
assert '"bridge_target": "1.0.0-rc36"' in hub
assert 'private static final String[] MANIFEST_URLS' in updater
assert 'raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux' in updater
assert 'cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux' in updater
assert 'github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux' in updater
assert 'readTextAny(MANIFEST_URLS' in updater
assert 'FurinaHub-Updater/2' in updater
assert updater.count('for (int attempt = 1; attempt <= 3; attempt++)') >= 2
assert 'versionCode 10036' in gradle
assert "versionName '1.0.0-rc36'" in gradle
assert 'Berpikir selama' in html
assert 'id="toolCrop"' in html and 'id="toolDraw"' in html

scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC36_MIRROR_FALLBACK_OK')
PY
