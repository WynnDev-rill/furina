#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc50-validate/termux
STAGE=/tmp/furina-agent-rc63-validate/termux
bash "$ROOT/overrides/android-rc50/validate.sh"
rm -rf "$STAGE"; mkdir -p "$(dirname "$STAGE")"; cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
python3 -m compileall -q "$STAGE/core/furina_agent"
python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
core=Path(sys.argv[1])/'core/furina_agent'
assert 'VERSION = "1.0.0-rc63"' in (core/'version.py').read_text()
h=(core/'hub.py').read_text()
assert 'furina-2026.08.21-rc63-rc51' in h
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.21-r33"' in h
assert h.count('"bridge_target": "1.0.0-rc51"') >= 2
print('FURINA_RC63_VALIDATION_OK')
PY
