#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc37"
HUB_VERSION="1.0.0-rc21"
DEPENDENCY_REVISION="2026.08.15-r2"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc37/install-body.sh"
BODY_BLOB="17a60c2fb7bd730b242a62d92054f2d238171952"

# Hashes are duplicated here intentionally so CI binds the public bootstrap to
# the exact RC37 Core payloads used by the verified installer body.
RC37_APPLY_BLOB="43f0d3087b083cefaece6504ea7e8653c93563b6"
RC37_HUB_BLOB="ce0ec08ee2d6b3b4044d94c28f24ea7e3ba1b97b"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
curl -fsSL --retry 3 "$BODY_URL" -o "$TMP"
python - "$TMP" "$BODY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
PY

# Authenticate the body first, then verify that it binds the same RC37 payloads.
python - "$TMP" "$RC37_APPLY_BLOB" "$RC37_HUB_BLOB" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); values=sys.argv[2:]
text=path.read_text(encoding='utf-8')
for key,value in zip(("RC37_APPLY_BLOB","RC37_HUB_BLOB"),values):
    if f'{key}="{value}"' not in text:
        raise SystemExit(f'Binding installer body tidak cocok: {key}')
PY

bash "$TMP" "$@"
