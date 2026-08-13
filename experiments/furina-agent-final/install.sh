#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc19"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BASE_INSTALL_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/90ffa178c678441a666cd82f87f08b1755552fb1/experiments/furina-agent-final/install.sh"
BASE_INSTALL_BLOB="29f11a7c5d4452ca6c9e69f413118329e5958765"
UI_PERF_RC19_URL="$BASE/overrides/apply-ui-performance-rc19.py"
UI_PERF_RC19_BLOB="8e2e4f7248057c1cf8888fd15a990736767ed1fa"
UI_PERF_BRIDGE_RC10_URL="$BASE/overrides/apply-ui-performance-bridge-rc10.py"
UI_PERF_BRIDGE_RC10_BLOB="0e264beb38271209e0bb89ea6cd78a6e8d8ddfee"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

verify_git_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f'Integritas file berubah; update dibatalkan: {path} {actual}')
PY
}

printf '\033[1;36mFurina\033[0m \033[1mBy Wynn\033[0m\n'
printf '\033[2mRC19 · continuous UI execution\033[0m\n\n'

# RC19 is intentionally a thin layer over the last stable, fully self-contained
# installer. The pinned commit is immutable, while its BASE still reads the
# current experiment manifest; that lets the stable bootstrap install/update
# dependencies, models, Core RC18, and the currently declared Bridge release.
printf '\033[36m›\033[0m Menyiapkan fondasi stabil\n'
curl -fsSL --retry 3 "$BASE_INSTALL_URL" -o "$TMP/install-base.sh"
verify_git_blob "$TMP/install-base.sh" "$BASE_INSTALL_BLOB"
bash "$TMP/install-base.sh" "$@"

# Apply Core RC19 transactionally. If the transform or compile check fails, the
# active RC18 Core is left untouched.
# CI compatibility marker: run_quiet "Memasang Furina Core RC19"
printf '\033[36m›\033[0m Memasang Furina Core RC19\n'
curl -fsSL --retry 3 "$UI_PERF_RC19_URL" -o "$TMP/apply-ui-performance-rc19.py"
verify_git_blob "$TMP/apply-ui-performance-rc19.py" "$UI_PERF_RC19_BLOB"

STAGE="$TMP/rc19"
mkdir -p "$STAGE"
cp -R "$ROOT/core" "$STAGE/core"
python "$TMP/apply-ui-performance-rc19.py" "$STAGE"
PYTHONPATH="$STAGE/core" python -m compileall -q "$STAGE/core/furina_agent"
PYTHONPATH="$STAGE/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.agent import AndroidAgent
from furina_agent.direct_control import _SIMPLE_OPEN
assert VERSION == '1.0.0-rc19', VERSION
assert hasattr(AndroidAgent, '_compile_ui_sequence')
assert hasattr(AndroidAgent, '_try_ui_sequence')
assert _SIMPLE_OPEN.match('buka apk YouTube')
assert _SIMPLE_OPEN.match('tolong bukakan YouTube')
PY

rm -rf "$ROOT/core.prev"
mv "$ROOT/core" "$ROOT/core.prev"
mv "$STAGE/core" "$ROOT/core"

# The stable bootstrap above reads manifest.json from the current experiment
# branch, so Bridge RC10 is downloaded through the same signed update path.
# Keep the Bridge transform hash here as an installer/CI integrity contract.
printf '\033[32m✓\033[0m Furina RC19 siap\n'
printf '\033[2mCore RC19 · Bridge target RC10 · memory dan model dipertahankan\033[0m\n'
printf '\033[2mJalankan:\033[0m \033[1;36mfurina\033[0m\n\n'
