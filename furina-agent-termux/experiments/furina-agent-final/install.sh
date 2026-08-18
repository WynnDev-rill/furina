#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_UPDATER_GENERATION="7"
VERSION="1.0.0-rc54"
DEPENDENCY_REVISION="2026.08.18-r24"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_PATH="overrides/runtime-r24/install-body.sh"
BODY_BLOB="251b6cac5a57a6ca8411d7e3930843b5e12d6243"
RC54_APPLY_BLOB="0b7e0449de01fe40746230e79d93740078fc785c"
STATE_BLOB="27fdb2a785bfdf28d7514ca35db1d5e73cfd5584"
MIND_BLOB="05f5a5a6d5700c449f03535ec658363351e3c560"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FETCH_CODE="000"

fetch_url() {
  local url="$1" out="$2" api="${3:-0}" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 90
              --retry 2 --retry-delay 1 --retry-all-errors
              -o "$out" -w '%{http_code}'
              -H 'User-Agent: Furina-Core-Bootstrap/7'
              -H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  if [[ "$api" == "1" ]]; then args+=(-H 'Accept: application/vnd.github.raw+json'); fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]]; then return 0; fi
  rm -f "$out"; return 1
}

fetch_body() {
  local out="$1"
  if fetch_url "$API_BASE/$BODY_PATH?ref=experiment/furina-agent-termux" "$out" 1; then return 0; fi
  if fetch_url "$RAW_BASE/$BODY_PATH" "$out"; then return 0; fi
  if fetch_url "$STABLE_RELEASE/furina-install-body.sh" "$out"; then return 0; fi
  if fetch_url "$WEB_BASE/$BODY_PATH" "$out"; then return 0; fi
  if fetch_url "$BOOTSTRAP_CDN/$BODY_PATH" "$out"; then return 0; fi
  echo "Tidak dapat mengambil updater dari source maupun channel fallback." >&2
  return 1
}

fetch_body "$TMP/install-body.sh"
python - "$TMP/install-body.sh" "$BODY_BLOB" "$RC54_APPLY_BLOB" "$STATE_BLOB" "$MIND_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob,state_blob,mind_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    'VERSION="1.0.0-rc54"',
    'DEPENDENCY_REVISION="2026.08.18-r24"',
    f'RC54_APPLY_BLOB="{apply_blob}"',
    f'STATE_BLOB="{state_blob}"',
    f'MIND_BLOB="{mind_blob}"',
    'R22_BODY_BLOB="3e892305bad6ddc880cff610d87c37ca814e9351"',
    'recovery otomatis',
    'api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding runtime RC54/r24 tidak lengkap: {missing}')
if 'releases/latest/download' in text:
    raise SystemExit('Updater RC54/r24 masih bergantung pada repository-wide latest release')
PY
bash "$TMP/install-body.sh" "$@"
