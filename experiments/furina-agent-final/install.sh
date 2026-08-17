#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
VERSION="1.0.0-rc51"
DEPENDENCY_REVISION="2026.08.17-r17"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
CDN_BASE="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_PATH="overrides/rc51/install-body.sh"
BODY_BLOB="2809d9968087dd9d2cd0507102eacd31c77b52d0"
RC51_APPLY_BLOB="736555772589d692a165ad60fac8c8c4d458e23b"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

fetch_rel() {
  local rel="$1" out="$2" base
  local bases=("$RAW_BASE" "$CDN_BASE" "$WEB_BASE")
  for base in "${bases[@]}"; do
    rm -f "$out"
    if curl -fL --silent --show-error \
        --connect-timeout 10 --max-time 90 \
        --retry 2 --retry-delay 1 --retry-all-errors \
        -H 'Cache-Control: no-cache' "$base/$rel" -o "$out"; then
      [[ -s "$out" ]] && return 0
    fi
  done
  echo "Tidak dapat mengambil updater dari GitHub maupun mirror cadangan." >&2
  return 1
}

fetch_rel "$BODY_PATH" "$TMP"
python - "$TMP" "$BODY_BLOB" "$RC51_APPLY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    'VERSION="1.0.0-rc51"',
    'DEPENDENCY_REVISION="2026.08.17-r17"',
    f'RC51_APPLY_BLOB="{apply_blob}"',
    'RC50_BODY_BLOB="37fe2fef1debe5cd04404fd37e16bd710466b2db"',
    'FURINA_RESILIENT_UPDATE_WRAPPER_V1',
    'cdn.jsdelivr.net/gh/WynnDev-rill/furina@experiment/furina-agent-termux',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding runtime RC51/r17 tidak lengkap: {missing}')
PY
bash "$TMP" "$@"
