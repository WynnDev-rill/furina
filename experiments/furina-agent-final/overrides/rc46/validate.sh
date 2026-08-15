#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc45/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m compileall -q "$STAGE/core/furina_agent"
bash -n "$HERE/install-body.sh"
python3 -m py_compile "$HERE/apply.py"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc46"' in version
assert 'time.monotonic() - self._connector_wake_at < 12' in hub
assert 'repairable=True' in hub
assert '"repairable": bool(status.get("repairable")' in hub
assert '"bridge_target": "1.0.0-rc28"' in hub
print('FURINAHUB_CORE_RC46_REGRESSION_OK')
PY

python3 - "$HERE/install-body.sh" "$ROOT/overrides/rc43/install-body.sh" <<'PY'
from pathlib import Path
import re,sys
installer=Path(sys.argv[1]).read_text(encoding='utf-8')
rc43=Path(sys.argv[2]).read_text(encoding='utf-8')
for marker in (
    'PINNED_RC45="0a321668549beeb7271b01e1c42ccc27124c3467"',
    'RC46_APPLY_BLOB="6e772b638424286140f717623e3eef0e829fbe49"',
    'node --experimental-transform-types "$APP/src/server/index.ts"',
    'kill_orphans()',
    'if ! start_openconnector_with_repair; then PLUGIN_OK=0; fi',
    'Core is upgraded first. Plugin failure must never strand Core',
    'furinahub-v1.0.0-rc29',
):
    assert marker in installer, marker
core_apply=installer.index('if [[ "$CURRENT" == "1.0.0-rc45" ]]; then apply_overlay rc45 rc46')
deps=installer.index('ensure_runtime_dependencies', core_apply)
plugin_start=installer.index('if ! start_openconnector_with_repair', deps)
assert core_apply < deps < plugin_start
pinned='https://raw.githubusercontent.com/WynnDev-rill/furina/44d215a38b336c903d06f04be01f30e60143ba35/experiments/furina-agent-final'
patched,count=re.subn(r'^BASE="[^"]+"$', f'BASE="{pinned}"', rc43, count=1, flags=re.M)
assert count == 1
for old in (
    'run_quiet "Menyiapkan runtime Plugin" 18 install_openconnector',
    'run_quiet "Menyalakan layanan Plugin (dapat memerlukan 45 detik)" 96 start_openconnector',
    'run_quiet "Memeriksa / menyiapkan APK FurinaHub RC27" 98 download_hub_apk',
):
    assert old in patched
print('FURINAHUB_RC46_INSTALLER_ORDER_OK')
PY
