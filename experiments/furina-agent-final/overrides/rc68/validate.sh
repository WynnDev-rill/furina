#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc67/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 "$HERE/apply.py" "$STAGE"
python3 - <<'PY'
from pathlib import Path
root=Path('/tmp/furina-agent-rc54-validate/termux/core/furina_agent')
tui=(root/'tui.py').read_text(encoding='utf-8')
version=(root/'version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc68"' in version
menu=[line for line in tui.splitlines() if 'choice = _choose("", ["Chat"' in line][-1]
assert '"Kita"' not in menu
assert 'choice == "Kita"' not in tui
assert (root/'relationship_v4.py').is_file()
print('FURINA_RC68_STATIC_OK')
PY
printf '%s\n' FURINA_RC68_VALIDATION_OK
