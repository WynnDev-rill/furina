#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc45"
HUB_VERSION="1.0.0-rc28"
DEPENDENCY_REVISION="2026.08.15-r9"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc45/install-body.sh"
BODY_BLOB="e336012ec7308f9143f114fe81e1b23851c51fa4"
RC45_APPLY_BLOB="b85cacc58d24889e8f600c12f8fc64d3930f27f3"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  pkg install -y python >/dev/null
fi

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
python - "$TMP" "$BODY_BLOB" "$RC45_APPLY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
if f'RC45_APPLY_BLOB="{apply_blob}"' not in text:
    raise SystemExit('Binding RC45 apply tidak cocok')
if 'PINNED_RC43="44d215a38b336c903d06f04be01f30e60143ba35"' not in text:
    raise SystemExit('Fondasi RC43 tidak dipin')
if 'PINNED_RC44="783e443f2bae6cd201c9a08a670caffffc6082ac"' not in text:
    raise SystemExit('Fondasi RC44 tidak dipin')
PY

bash "$TMP" "$@"
