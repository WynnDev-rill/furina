#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/android-rc33/validate.sh"
python3 "$ROOT/overrides/rc50/apply.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re,subprocess,sys,tempfile
root=Path(sys.argv[1])
app=root/'bridge/app'
html=(app/'src/main/assets/furinahub/index.html').read_text(encoding='utf-8')
java=(app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java').read_text(encoding='utf-8')
gradle=(app/'build.gradle').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc50"' in version
assert '"bridge_target": "1.0.0-rc34"' in hub
assert 'Executors.newFixedThreadPool(3)' in java
assert 'MediaStore.ACTION_PICK_IMAGES' in java
for marker in (
    'RC34: companion feedback',
    'id="allUpdateBtn"',
    'id="conversationMenu"',
    'function addThinking(',
    '/api/chat/progress/',
    'function openConversationMenu(',
    "action:'rename'",
    "action:'pin'",
    'function rotateEditor(',
    'function flipEditor(',
    'setCropRatio(1.3333',
):
    assert marker in html, marker
assert "if(selectedAttachment.kind==='image')openImageEditor()" not in html
assert 'versionCode 10034' in gradle
assert "versionName '1.0.0-rc34'" in gradle
scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/'hub.js'
path.write_text(scripts[0],encoding='utf-8')
subprocess.run(['node','--check',str(path)],check=True)
print('FURINAHUB_ANDROID_RC34_REGRESSION_OK')
PY
