#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/android-rc31/validate.sh"
python3 "$ROOT/overrides/rc48/apply.py" "$STAGE"
python3 "$ROOT/overrides/rc49/apply.py" "$STAGE"
python3 "$ROOT/overrides/rc49/harden.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1])
app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc49"' in version
assert 'lowered.get("displayname")' in hub
assert 'RC32: simple, contract-driven Plugin UI' in html
assert 'id="pluginConnectLayer"' in html
assert "p.no_auth)return'Tanpa login'" in html
assert 'p.ready&&' in html
assert "mode:'auto'" in html
assert "result.flow==='oauth_browser'" in html
assert 'pluginCredentialInput' in html
assert 'Menampilkan layanan utama' in html
assert "p.connected?'Terhubung':'Hubungkan'" not in html
assert 'versionCode 10032' in gradle
assert "versionName '1.0.0-rc32'" in gradle
scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC32_REGRESSION_OK')
PY
