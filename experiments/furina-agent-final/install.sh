#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc38"
HUB_VERSION="1.0.0-rc22"
DEPENDENCY_REVISION="2026.08.15-r3"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc38/install-body.sh"
BODY_BLOB="ffbc3fc38c5046a5aa154175aee9bc01030c9f81"

# Hashes are duplicated intentionally so the public bootstrap authenticates
# the exact RC38 payloads before executing anything fetched from the branch.
RC38_APPLY_BLOB="66780ad6106cacedde11e37154df65737bd7d10b"
RC38_HUB_BLOB="971e401f246fc43882bac1c0215241da458c7714"
RC38_DIRECT_BLOB="7ef20de18a1a2ad858b803d27fd86c1247ce82d6"

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
python - "$TMP" "$BODY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
PY

python - "$TMP" "$RC38_APPLY_BLOB" "$RC38_HUB_BLOB" "$RC38_DIRECT_BLOB" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); values=sys.argv[2:]
text=path.read_text(encoding='utf-8')
for key,value in zip(("RC38_APPLY_BLOB","RC38_HUB_BLOB","RC38_DIRECT_BLOB"),values):
    if f'{key}="{value}"' not in text:
        raise SystemExit(f'Binding installer body tidak cocok: {key}')
PY

bash "$TMP" "$@"
