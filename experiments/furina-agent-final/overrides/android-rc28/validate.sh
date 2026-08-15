#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux
bash "$ROOT/overrides/android-rc27/validate.sh"
python3 "$ROOT/overrides/rc44/apply.py" "$STAGE" "$ROOT/overrides/rc44"
python3 "$ROOT/overrides/rc44/audit-extra.py" "$STAGE"
python3 "$HERE/apply.py" "$STAGE" "$HERE"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re, sys
root=Path(sys.argv[1])
html=(root/"bridge/app/src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
body=(root/"bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text(encoding="utf-8")
gradle=(root/"bridge/app/build.gradle").read_text(encoding="utf-8")
hub=(root/"core/furina_agent/hub.py").read_text(encoding="utf-8")
routing=(root/"core/furina_agent/routing.py").read_text(encoding="utf-8")
assert "data.length > 9_000_000" in body
assert "data.length > 2_000_000" not in body
assert "web = null;" in body
assert "if (web != null) web.evaluateJavascript(js, null);" in body
assert "if (appUpdateBusy) return;" in body
assert "REQ_SAVE_IMAGE && resultCode != RESULT_OK) pendingImageSave = null;" in body
assert "result.mode==='device'&&result.job" in html
assert "const pendingUser=addMsg" in html
assert "pendingUser.remove();if(forcedText===undefined)" in html
assert "(bootData.jobs||[]).forEach(renderJob)" in html
assert "for(let i=0;i<750;i++" in html
assert "semantic_steps=semantic_steps" in hub
assert 'shutil.which("furina")' in routing
assert "versionCode 10028" in gradle
assert "versionName '1.0.0-rc28'" in gradle
assert not re.search(r'\b(prompt|confirm)\s*\(', html)
print("FURINAHUB_ANDROID_RC28_REGRESSION_OK")
PY

python3 - "$STAGE/bridge/app/src/main/assets/furinahub/index.html" <<'PY'
from pathlib import Path
import re, subprocess, sys, tempfile
html=Path(sys.argv[1]).read_text(encoding="utf-8")
scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
assert len(scripts)==1
path=Path(tempfile.mkdtemp())/"hub.js"
path.write_text(scripts[0],encoding="utf-8")
subprocess.run(["node","--check",str(path)],check=True)
print("FURINAHUB_ANDROID_RC28_JS_OK")
PY
