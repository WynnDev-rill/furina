#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc68/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 "$HERE/apply.py" "$STAGE"
python3 - <<'PY'
from pathlib import Path
p=Path('/tmp/furina-agent-rc54-validate/termux/core/furina_agent/version.py')
t=p.read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc69"' in t
assert 'UPDATE_PROTOCOL = "furina-update/1"' in t
print('FURINA_RC69_STATIC_OK')
PY
printf '%s\n' FURINA_RC69_VALIDATION_OK
