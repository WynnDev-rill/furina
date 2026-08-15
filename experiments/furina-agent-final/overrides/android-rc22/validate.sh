#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc38/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$ROOT/overrides/android-rc21/apply.py" "$STAGE" "$ROOT/overrides/android-rc21"
python3 "$HERE/apply.py" "$STAGE" "$HERE"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
html = (root / "bridge/app/src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
body = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text(encoding="utf-8")
gradle = (root / "bridge/app/build.gradle").read_text(encoding="utf-8")
for marker in ('id="plusMenu" class="sheet compact"', "menuIcon", "File teks", "Plugin & aplikasi",
               "data:image/svg+xml;base64,", "startCoreUpdate", "coreUpdateStatus",
               "Perbaiki / update Core & dependency", "statuschip chat-hidden"):
    assert marker in html, marker
assert "__ICON_FILE_TEXT__" not in html and "__ICON_PLUG__" not in html
for marker in ("RUN_COMMAND_PENDING_INTENT", "TERMUX_RESULT_ACTION", "CORE_RECOVERY_COMMAND",
               "startCoreRecoveryUpdate", "stdout", "stderr", "exitCode"):
    assert marker in body, marker
assert "versionCode 10022" in gradle
assert "versionName '1.0.0-rc22'" in gradle
print("FURINAHUB_ANDROID_RC22_VALIDATED")
PY
