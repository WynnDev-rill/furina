#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc39/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$ROOT/overrides/android-rc21/apply.py" "$STAGE" "$ROOT/overrides/android-rc21"
python3 "$ROOT/overrides/android-rc22/apply.py" "$STAGE" "$ROOT/overrides/android-rc22"
python3 "$HERE/apply.py" "$STAGE" "$HERE"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import re, sys
root = Path(sys.argv[1])
html = (root / "bridge/app/src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
body = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text(encoding="utf-8")
gradle = (root / "bridge/app/build.gradle").read_text(encoding="utf-8")
for marker in ('Riwayat chat', 'onMediaPicked', 'Kamera', 'Foto', '>File<',
               'Plugin & aplikasi', '/api/conversations', 'dialogLayer',
               'function pickImage', 'function takePhoto', 'function go(id){closeSheets();'):
    assert marker in html, marker
assert not re.search(r'\b(prompt|confirm)\s*\(', html)
assert "pointer-events:none" in html and ".sheet.show{transform:none;pointer-events:auto}" in html
assert "__ICON_" not in html
for marker in ("REQ_PICK_IMAGE", "REQ_CAMERA", "pickImage", "takePhoto", "onMediaPicked", "MAX_IMAGE_BYTES"):
    assert marker in body, marker
assert "versionCode 10023" in gradle
assert "versionName '1.0.0-rc23'" in gradle
print("FURINAHUB_ANDROID_RC23_VALIDATED")
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
