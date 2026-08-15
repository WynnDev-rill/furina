#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc46"
HUB_VERSION="1.0.0-rc29"
DEPENDENCY_REVISION="2026.08.15-r10"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc46/install-body.sh"
BODY_BLOB="de2b7c6acb892ce7a9049558456f418a68f4e880"
RC46_APPLY_BLOB="6e772b638424286140f717623e3eef0e829fbe49"

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
python - "$TMP" "$BODY_BLOB" "$RC46_APPLY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
if f'RC46_APPLY_BLOB="{apply_blob}"' not in text:
    raise SystemExit('Binding RC46 apply tidak cocok')
for marker in (
    'PINNED_RC43="44d215a38b336c903d06f04be01f30e60143ba35"',
    'PINNED_RC44="783e443f2bae6cd201c9a08a670caffffc6082ac"',
    'PINNED_RC45="0a321668549beeb7271b01e1c42ccc27124c3467"',
):
    if marker not in text:
        raise SystemExit('Fondasi Core tidak dipin: '+marker)
if 'HUB_VERSION="1.0.0-rc29"' not in text:
    raise SystemExit('Binding FurinaHub RC29 tidak cocok')
PY

bash "$TMP" "$@"
