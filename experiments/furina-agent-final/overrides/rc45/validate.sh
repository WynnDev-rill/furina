#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc44/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m compileall -q "$STAGE/core/furina_agent"
bash -n "$HERE/install-body.sh"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc45"' in version
assert 'def _connector_runtime_error()' in hub
assert 'state="error"' in hub
assert 'time.monotonic() - self._connector_wake_at < 8' in hub
assert '"bridge_target": "1.0.0-rc28"' in hub
print('FURINAHUB_CORE_RC45_REGRESSION_OK')
PY

python3 - "$ROOT/overrides/rc43/install-body.sh" <<'PY'
from pathlib import Path
import re,sys
text=Path(sys.argv[1]).read_text(encoding='utf-8')
pinned='https://raw.githubusercontent.com/WynnDev-rill/furina/44d215a38b336c903d06f04be01f30e60143ba35/experiments/furina-agent-final'
patched,count=re.subn(r'^BASE="[^"]+"$', f'BASE="{pinned}"', text, count=1, flags=re.M)
assert count == 1
old_install='run_quiet "Menyiapkan runtime Plugin" 18 install_openconnector'
old_start='run_quiet "Menyalakan layanan Plugin (dapat memerlukan 45 detik)" 96 start_openconnector'
assert old_install in patched and old_start in patched
patched=patched.replace(old_install, 'mark 18 "Runtime Plugin ditangani RC45"', 1)
patched=patched.replace(old_start, 'mark 96 "Startup Plugin ditangani RC45"', 1)
assert old_install not in patched and old_start not in patched
assert patched.count('BASE="'+pinned+'"') == 1
print('FURINAHUB_RC45_RC43_BOOTSTRAP_PATCH_OK')
PY

python3 - "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(encoding='utf-8')
required=(
    'node src/server/index.ts',
    'OOMOL_CONNECT_ORIGIN="http://127.0.0.1:3000"',
    'npm install --omit=dev --workspaces=false',
    'furina-openconnector restart',
    'RC43_BODY_BLOB="dcaeee6a1ad8588f76c37138b180b472b8720178"',
    'RC44_APPLY_BLOB="1c81b788e0581f363cc166b576feee68ec8b5798"',
    'RC44_AUDIT_BLOB="cec2f8d52454ebc8671ce7596f4140a1dff0d4cd"',
)
for marker in required:
    assert marker in text, marker
print('FURINAHUB_RC45_INSTALLER_STATIC_OK')
PY
