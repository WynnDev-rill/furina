#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc39"
HUB_VERSION="1.0.0-rc23"
DEPENDENCY_REVISION="2026.08.15-r4"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_URL="$BASE/overrides/rc39/install-body.sh"
BODY_BLOB="439f580f4f717a9b28433dda2789facc78644cf5"

# Hashes are duplicated intentionally so the public bootstrap authenticates
# the exact RC39 payloads before executing anything fetched from the branch.
RC39_APPLY_BLOB="3e824d8d43db7064357b17596184d1a37ae2135d"
RC39_HUB_BLOB="7ea7218bde2e375f75714d821535aa1e4a99369f"
RC39_DIRECT_BLOB="7ef20de18a1a2ad858b803d27fd86c1247ce82d6"
RC39_MEMORY_BLOB="8b23ebea80f5a4a9f7ea102cf742e0514ac39490"
RC39_COMPANION_BLOB="64c9989d25c401aa568ed96d228698c8a9e5dc46"

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

python - "$TMP" "$RC39_APPLY_BLOB" "$RC39_HUB_BLOB" "$RC39_DIRECT_BLOB" "$RC39_MEMORY_BLOB" "$RC39_COMPANION_BLOB" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); values=sys.argv[2:]
text=path.read_text(encoding='utf-8')
for key,value in zip(("RC39_APPLY_BLOB","RC39_HUB_BLOB","RC39_DIRECT_BLOB","RC39_MEMORY_BLOB","RC39_COMPANION_BLOB"),values):
    if f'{key}="{value}"' not in text:
        raise SystemExit(f'Binding installer body tidak cocok: {key}')
PY

bash "$TMP" "$@"
