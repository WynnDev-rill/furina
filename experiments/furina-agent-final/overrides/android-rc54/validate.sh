#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc66-validate/termux
STAGE=/tmp/furina-agent-rc54-validate/termux

HOME="${HOME:-/tmp/furina-validation-home}" FURINA_HOME="${FURINA_HOME:-$HOME}" bash "$ROOT/overrides/rc66/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
app = root / "bridge" / "app"
java = app / "src" / "main" / "java" / "com" / "wynndev" / "furinaagentbridge"
gradle = (app / "build.gradle").read_text(encoding="utf-8")
html = (app / "src" / "main" / "assets" / "furinahub" / "index.html").read_text(encoding="utf-8")
main = (java / "MainActivity.java").read_text(encoding="utf-8")

assert "versionCode 10054" in gradle and "versionName '1.0.0-rc54'" in gradle
assert 'EXPECTED_CORE_VERSION = "1.0.0-rc66"' in main
for marker in (
    'id="relationship"', 'data-view="relationship"', "async function loadRelationship()",
    "/api/relationship/preferences", "/api/relationship/moments",
    "Simpan sebagai Momen kita", "Cara kita berbicara", "tanpa skor, streak",
):
    assert marker in html, marker
assert 'data-view="focus"' not in html
assert "Jadikan Fokus" not in html
assert "Ada yang ingin kamu bicarakan atau kerjakan?" not in html
assert html.count("async function captureSelected(action)") == 1
print("FURINAHUB_ANDROID_RC54_STATIC_OK")
PY

awk '/<script>/{inside=1;next}/<\/script>/{inside=0}inside' "$STAGE/bridge/app/src/main/assets/furinahub/index.html" | node --check
printf '%s\n' FURINAHUB_ANDROID_RC54_VALIDATION_OK
