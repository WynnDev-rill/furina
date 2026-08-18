#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_UPDATER_GENERATION="12"
VERSION="1.0.0-rc59"
DEPENDENCY_REVISION="2026.08.18-r29"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_PATH="overrides/runtime-r29/install-body.sh"
BODY_BLOB="5de4329590f09226618aa102adb3f19936636608"
APPLY_BLOB="2be10d3d060ba7d09e12dddde172a337d943d996"
BRIDGE_BLOB="3cf0f0e516231e729bb789a0d13481426030de6f"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

BOOT_TTY=0
if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" != "1" && -t 1 && "${TERM:-dumb}" != "dumb" ]]; then
  BOOT_TTY=1
  printf '\r\033[38;5;244mSedang berjalan… Menghubungi channel update\033[0m'
fi
boot_clear(){ [[ "$BOOT_TTY" == "1" ]] && printf '\r\033[2K'; }

fetch_url(){
  local url="$1" out="$2" api="${3:-0}" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 150
              --retry 3 --retry-delay 2 --retry-all-errors
              -o "$out" -w '%{http_code}'
              -H 'User-Agent: Furina-Core-Bootstrap/12'
              -H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  [[ "$api" == "1" ]] && args+=(-H 'Accept: application/vnd.github.raw+json')
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  [[ "$code" == "200" && -s "$out" ]]
}
fetch_body(){
  local out="$1"
  fetch_url "$API_BASE/$BODY_PATH?ref=experiment/furina-agent-termux" "$out" 1 ||
  fetch_url "$RAW_BASE/$BODY_PATH" "$out" ||
  fetch_url "$STABLE_RELEASE/furina-install-body.sh" "$out" ||
  fetch_url "$WEB_BASE/$BODY_PATH" "$out" ||
  fetch_url "$BOOTSTRAP_CDN/$BODY_PATH" "$out"
}

fetch_body "$TMP/install-body.sh" || {
  boot_clear
  echo "Tidak dapat mengambil updater terbaru." >&2
  exit 75
}
python - "$TMP/install-body.sh" "$BODY_BLOB" "$APPLY_BLOB" "$BRIDGE_BLOB" <<'PY'
import hashlib,pathlib,sys
p,expected,apply_blob,bridge_blob=sys.argv[1:]
d=pathlib.Path(p).read_bytes()
actual=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if actual!=expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
t=d.decode()
checks=(
    'VERSION="1.0.0-rc59"',
    'DEPENDENCY_REVISION="2026.08.18-r29"',
    'TYPESCRIPT_VERSION="5.9.3"',
    f'APPLY_BLOB="{apply_blob}"',
    f'BRIDGE_BLOB="{bridge_blob}"',
    'return 0',
    'tail -n 24 "$LOG"',
    'FURINA_RC59_RUNTIME_REGRESSION_OK',
)
missing=[x for x in checks if x not in t]
if missing:
    raise SystemExit(f'Binding runtime RC59/r29 tidak lengkap: {missing}')
PY
boot_clear
bash "$TMP/install-body.sh" "$@"
