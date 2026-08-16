#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc48"
DEPENDENCY_REVISION="2026.08.16-r13"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc48-r13/install-body.sh"
BODY_BLOB="628cf0186f79f9d66fcbe2026d96cb65246417fd"
RC48_BODY_BLOB="13cc5b168052ed07fe09e78d6ecc2f5a758318be"

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
python - "$TMP" "$BODY_BLOB" "$RC48_BODY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,foundation_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    'DEPENDENCY_REVISION="2026.08.16-r13"',
    f'RC48_BODY_BLOB="{foundation_blob}"',
    'NODE_ENV=production NODE_NO_WARNINGS=1',
    'npm install --omit=dev --workspaces=false --no-audit --no-fund',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding runtime r13 tidak lengkap: {missing}')
PY

bash "$TMP" "$@"
