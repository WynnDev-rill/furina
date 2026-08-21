#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/android-rc55/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
ARCHIVE=/tmp/furina-core-bridge-rc67-rc55.tar.gz
tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner --exclude='__pycache__' --exclude='*.pyc' --exclude='bridge/.gradle' --exclude='bridge/app/build' -C "$STAGE" -cf - core bridge | gzip -n -9 >"$ARCHIVE"
echo '0f91696d6d9c9f88c33a827d69e2ce492f63e4269ac421777de975afc3e161bc  '"$ARCHIVE" | sha256sum -c -
bash -n "$HERE/install-body.sh"
python3 - "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import sys
t=Path(sys.argv[1]).read_text()
required=('FURINA_RUNTIME_CONTRACT="furina-runtime/v3-full-snapshot"','SNAPSHOT_SHA256="0f91696d','validate_archive','install_launchers','rollback','FURINA_FULL_SNAPSHOT_WRAPPER_V1')
assert all(x in t for x in required)
assert 'runtime-r36' not in t and 'foundation' not in t.lower()
print('FURINA_RUNTIME_R37_FULL_SNAPSHOT_STATIC_OK')
PY
printf '%s\n' FURINA_RUNTIME_R37_VALIDATION_OK
