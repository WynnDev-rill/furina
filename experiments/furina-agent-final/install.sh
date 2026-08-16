#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc48"
DEPENDENCY_REVISION="2026.08.16-r12"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc48/install-body.sh"
BODY_BLOB="13cc5b168052ed07fe09e78d6ecc2f5a758318be"
RC48_APPLY_BLOB="9d2a1c6bf1df6bcd464691b8bb1418b80cdf9443"
OPENCONNECTOR_COMMIT="d478400141c33bb5ddf823e09b293e9d7154da97"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
if command -v curl >/dev/null 2>&1; then
  curl -fsSL --retry 3 "$BODY_URL" -o "$TMP"
else
  python - "$BODY_URL" "$TMP" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve(sys.argv[1],sys.argv[2])
PY
fi
python - "$TMP" "$BODY_BLOB" "$RC48_APPLY_BLOB" "$OPENCONNECTOR_COMMIT" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob,connector_commit=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    f'RC48_APPLY_BLOB="{apply_blob}"',
    f'OPENCONNECTOR_COMMIT="{connector_commit}"',
    'URL="http://127.0.0.1:3000/v1/health"',
    'node "$APP/src/server/index.ts"',
    'Do not stamp the revision on failure',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding RC48 tidak lengkap: {missing}')
PY

bash "$TMP" "$@"
