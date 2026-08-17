#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc50"
DEPENDENCY_REVISION="2026.08.17-r16"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc50/install-body.sh"
BODY_BLOB="37fe2fef1debe5cd04404fd37e16bd710466b2db"
RC50_APPLY_BLOB="7dfe9aab1b7bfa5c70191b00679acc17b17192c0"

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
python - "$TMP" "$BODY_BLOB" "$RC50_APPLY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    'VERSION="1.0.0-rc50"',
    'DEPENDENCY_REVISION="2026.08.17-r16"',
    f'RC50_APPLY_BLOB="{apply_blob}"',
    'RC49_BODY_BLOB="44d4d038b6159f28dd95064eca67239b071b1201"',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding runtime RC50/r16 tidak lengkap: {missing}')
PY
bash "$TMP" "$@"
