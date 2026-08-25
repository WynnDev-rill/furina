#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.1.0/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.1/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.10"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10078' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.1.10'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.1.10"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r60"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import os
from pathlib import Path

root = Path(os.environ["STAGE_ROOT"])
page = (root / "bridge/app/src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
main = (root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text(encoding="utf-8")

assert "if(coreBtn){coreBtn.disabled" in page
assert "if(id==='relationship'){if(connection.connected)loadRelationship();else renderRelationship(null)}" in page
assert "if(id==='settings')if(id==='relationship')" not in page
assert "personalityTraitGrid110" in page and "defs.map(t=>" in page
assert ".traitChoice110{visibility:visible}" in page
assert "probeSavedCore();\n        if (web != null)" in main
print("FURINAHUB_PRIVATE_1_1_1_STATIC_REPAIR_OK")
PY

echo "FURINA_PRIVATE_1_1_1_VALIDATION_OK"
