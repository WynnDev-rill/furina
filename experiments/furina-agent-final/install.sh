#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc44"
HUB_VERSION="1.0.0-rc28"
DEPENDENCY_REVISION="2026.08.15-r8"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc44/install-body.sh"
BODY_BLOB="b7a964b56ff269a978c0eab277f137f496c3357a"
RC44_APPLY_BLOB="1c81b788e0581f363cc166b576feee68ec8b5798"
RC44_AUDIT_BLOB="b511a228e41c606961778f47b11bbf4077272874"

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
python - "$TMP" "$BODY_BLOB" "$RC44_APPLY_BLOB" "$RC44_AUDIT_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob,audit_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
if f'RC44_APPLY_BLOB="{apply_blob}"' not in text:
    raise SystemExit('Binding RC44 apply tidak cocok')
if f'RC44_AUDIT_BLOB="{audit_blob}"' not in text:
    raise SystemExit('Binding RC44 audit tidak cocok')
if 'PINNED_RC43="44d215a38b336c903d06f04be01f30e60143ba35"' not in text:
    raise SystemExit('Fondasi RC43 tidak dipin')
PY

bash "$TMP" "$@"
