#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc49"
DEPENDENCY_REVISION="2026.08.16-r15"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc49/install-body.sh"
BODY_BLOB="f5a852aae4d0aa57c19c724aef8d3a9752f1a098"
RC49_APPLY_BLOB="c16461e87230f8560f7e6093b90a7cc4e8aab909"
RC49_HARDEN_BLOB="5b8d67a938774652f4169a1733b8cd3fbab32b5f"

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
python - "$TMP" "$BODY_BLOB" "$RC49_APPLY_BLOB" "$RC49_HARDEN_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob,harden_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    'VERSION="1.0.0-rc49"',
    'DEPENDENCY_REVISION="2026.08.16-r15"',
    f'RC49_APPLY_BLOB="{apply_blob}"',
    f'RC49_HARDEN_BLOB="{harden_blob}"',
    'OOMOL_CONNECT_ENCRYPTION_KEY="$key"',
    'OOMOL_CONNECT_ADMIN_TOKEN="$token"',
    'OOMOL_CONNECT_RUNTIME_TOKEN="$token"',
    'OOMOL_CONNECT_BLOCKED_PROXIES="*"',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding runtime RC49/r15 tidak lengkap: {missing}')
PY

bash "$TMP" "$@"
