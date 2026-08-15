#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc47"
DEPENDENCY_REVISION="2026.08.15-r11"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc47/install-body.sh"
BODY_BLOB="eb05c9fa0e618b5beff01fa66a8b27bb28889883"
RC47_APPLY_BLOB="285b1911b580fffdfea1c9484151c1d5ba680559"

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
python - "$TMP" "$BODY_BLOB" "$RC47_APPLY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
if f'RC47_APPLY_BLOB="{apply_blob}"' not in text:
    raise SystemExit('Binding RC47 apply tidak cocok')
if 'PINNED_RC46="5cf4080ac5bc5ae8204c45490825715f63a89627"' not in text:
    raise SystemExit('Fondasi RC46 tidak dipin')
if 'FURINAHUB_CORE_ONLY="$EXISTING_INSTALL"' not in text:
    raise SystemExit('Pemisahan updater Core/APK tidak terikat')
PY

bash "$TMP" "$@"
