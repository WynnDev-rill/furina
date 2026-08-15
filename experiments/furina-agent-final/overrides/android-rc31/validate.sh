#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/android-rc30/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1])
app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc47"' in version
assert 'RC31: full-width mobile layout + simpler ownership' in html
assert '.view,.chatview{width:100%!important' in html
assert '.content{align-items:stretch}' in html
assert 'class="pluginSafety"' in html
assert 'Skill tambahan (' in html
assert 'Recovery lewat Termux' in html
assert 'Menggunakan jalur yang sama dengan <code>furina update</code>' in html
assert 'id="connectorStatus"' not in html
assert 'checkConnector()' not in html
assert 'versionCode 10031' in gradle
assert "versionName '1.0.0-rc31'" in gradle
scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC31_REGRESSION_OK')
PY
