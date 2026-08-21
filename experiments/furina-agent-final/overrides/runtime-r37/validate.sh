#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/android-rc55/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
ARCHIVE=/tmp/furina-core-bridge-rc67-rc55.tar
tar --format=ustar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner --exclude='__pycache__' --exclude='*.pyc' --exclude='bridge/.gradle' --exclude='bridge/app/build' -C "$STAGE" -cf "$ARCHIVE" core bridge
echo '502df5c11809b027ec118b3209adb3a4d14ffa441b570b8da02083dc9f2b20f9  '"$ARCHIVE" | sha256sum -c -
bash -n "$HERE/install-body.sh"
python3 - "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import sys
t=Path(sys.argv[1]).read_text()
required=('FURINA_RUNTIME_CONTRACT="furina-runtime/v3-full-snapshot"','SNAPSHOT_SHA256="502df5c1','validate_archive','install_launchers','rollback','FURINA_FULL_SNAPSHOT_WRAPPER_V1')
assert all(x in t for x in required)
assert 'runtime-r36' not in t and 'foundation' not in t.lower()
print('FURINA_RUNTIME_R37_FULL_SNAPSHOT_STATIC_OK')
PY
printf '%s\n' FURINA_RUNTIME_R37_VALIDATION_OK
