#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc36"
HUB_VERSION="1.0.0-rc21"
DEPENDENCY_REVISION="2026.08.14-r1"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc36/install-body.sh"
BODY_BLOB="a46c699aa95eaa0b9fde3919b994ae7a0930eff7"

# Hashes are duplicated here intentionally so CI binds the public bootstrap to
# the exact RC36 Core payloads used by the verified installer body.
RC36_APPLY_BLOB="23e6cea5e60bbd9f6d0dbcba2f834118ebe9459f"
RC36_SETTINGS_BLOB="08c82b36c9a52c91ee6995625885166b74618a53"
RC36_HUB_BLOB="72f9e38e727378d206d1a969f9b46daf4c6e82c6"

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

# Authenticate the body first, then verify that it binds the same RC36 payloads.
python - "$TMP" "$RC36_APPLY_BLOB" "$RC36_SETTINGS_BLOB" "$RC36_HUB_BLOB" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); values=sys.argv[2:]
text=path.read_text(encoding='utf-8')
for key,value in zip(("RC36_APPLY_BLOB","RC36_SETTINGS_BLOB","RC36_HUB_BLOB"),values):
    if f'{key}="{value}"' not in text:
        raise SystemExit(f'Binding installer body tidak cocok: {key}')
PY

bash "$TMP" "$@"
