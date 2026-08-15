#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc43/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$ROOT/overrides/android-rc20/apply.py" "$STAGE" "$ROOT/overrides/android-rc20"
python3 "$ROOT/overrides/android-rc21/apply.py" "$STAGE" "$ROOT/overrides/android-rc21"
python3 "$ROOT/overrides/android-rc22/apply.py" "$STAGE" "$ROOT/overrides/android-rc22"
python3 "$ROOT/overrides/android-rc23/apply.py" "$STAGE" "$ROOT/overrides/android-rc23"
python3 "$ROOT/overrides/android-rc24/apply.py" "$STAGE" "$ROOT/overrides/android-rc24"
python3 "$ROOT/overrides/android-rc25/apply.py" "$STAGE" "$ROOT/overrides/android-rc25"
python3 "$ROOT/overrides/android-rc26/apply.py" "$STAGE" "$ROOT/overrides/android-rc26"
python3 "$HERE/apply.py" "$STAGE" "$HERE"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re, sys
root = Path(sys.argv[1])
html = (root / "bridge/app/src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
body = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text(encoding="utf-8")
gradle = (root / "bridge/app/build.gradle").read_text(encoding="utf-8")
for marker in ('Riwayat chat', 'onMediaPicked', 'imageEditor', 'pluginPicker',
               'id="plugins" class="view"', 'modelCatalog', 'themeChoices',
               'coreUpdateProgress', 'Menyiapkan Plugin', 'checkConnector', 'function go(id){closeSheets();'):
    assert marker in html, marker
assert not re.search(r'\b(prompt|confirm)\s*\(', html)
assert "visibility:hidden" in html and "calc(100% + 120px)" in html
assert ".sheet.show{opacity:1;visibility:visible;transform:translate3d(0,0,0)" in html
assert "__ICON_" not in html
for marker in ("setSupportZoom(false)", "setOnApplyWindowInsetsListener", "WindowInsets.Type.navigationBars()", "REQ_PICK_IMAGE", "pickImage"):
    assert marker in body, marker
assert "versionCode 10027" in gradle
assert "versionName '1.0.0-rc27'" in gradle
print("FURINAHUB_ANDROID_RC27_VALIDATED")
PY

python3 - "$HERE/hub_shell.html" <<'PY'
from pathlib import Path
import re, subprocess, sys, tempfile
html = Path(sys.argv[1]).read_text(encoding="utf-8")
scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
assert len(scripts) == 1
path = Path(tempfile.mkdtemp()) / "hub.js"
path.write_text(scripts[0], encoding="utf-8")
subprocess.run(["node", "--check", str(path)], check=True)
PY
