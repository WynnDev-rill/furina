#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc35"
HUB_VERSION="1.0.0-rc20"
DEPENDENCY_REVISION="2026.08.14-r1"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc35/install-body.sh"
BODY_BLOB="4b3b6c48b22c21b4dc31d55afb14025286b964f0"

# Hashes are duplicated here intentionally so CI binds the public bootstrap to
# the exact RC35 Core payloads used by the verified installer body.
APPLY_BLOB="386f092c94c1d6d0d45e215772e8320dc127271d"
SETTINGS_BLOB="d6bb11623353a3ff26a9000fb4b3a419c1919392"
HUB_BLOB="0d36622263bee864baa4a43477852bac7edc7f5a"
WEB_BLOB="e78482e18887cebaf8c4d2f4ec51c3c246d5b36a"
MAIN_ACTIVITY_BLOB="0999791565430cce8034d75e79bbb8c4beec12d8"

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

# RC35 apply.py received a later bytecode-cache hardening fix. Authenticate the
# installer body first, then replace only that pinned Core transform hash.
python - "$TMP" "$APPLY_BLOB" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); new=sys.argv[2]
text=path.read_text(encoding='utf-8')
old='APPLY_BLOB="42446503423986177fb31a73d879441616059953"'
replacement=f'APPLY_BLOB="{new}"'
if text.count(old) != 1:
    raise SystemExit('Installer body RC35 tidak sesuai bootstrap yang diharapkan')
path.write_text(text.replace(old,replacement,1),encoding='utf-8')
PY

bash "$TMP" "$@"
