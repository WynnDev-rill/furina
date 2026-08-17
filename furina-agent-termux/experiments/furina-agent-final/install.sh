#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_UPDATER_GENERATION="3"
VERSION="1.0.0-rc51"
DEPENDENCY_REVISION="2026.08.17-r19"
LATEST_RELEASE="https://github.com/WynnDev-rill/furina/releases/latest/download"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_PATH="overrides/rc51/install-body.sh"
BODY_BLOB="373d016876d3def4aaee0469009d956c7a3ff853"
RC51_APPLY_BLOB="736555772589d692a165ad60fac8c8c4d458e23b"

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
              -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Bootstrap/3')
  if [[ "$api" == "1" ]]; then
    args+=(-H 'Accept: application/vnd.github.raw+json')
  fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]]; then
    return 0
  fi
  rm -f "$out"
  return 1
}

fetch_body() {
  local out="$1" github_blocked=0
  if fetch_url "$LATEST_RELEASE/furina-install-body.sh" "$out"; then return 0; fi
  [[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1

  if [[ "$github_blocked" == "0" ]] && fetch_url "$STABLE_RELEASE/furina-install-body.sh" "$out"; then
    return 0
  fi
  if fetch_url "$BOOTSTRAP_CDN/$BODY_PATH" "$out"; then return 0; fi
  if [[ "$github_blocked" == "0" ]] && fetch_url "$API_BASE/$BODY_PATH?ref=experiment/furina-agent-termux" "$out" 1; then
    return 0
  fi
  [[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1
  if [[ "$github_blocked" == "0" ]] && fetch_url "$RAW_BASE/$BODY_PATH" "$out"; then return 0; fi
  if [[ "$github_blocked" == "0" ]] && fetch_url "$WEB_BASE/$BODY_PATH" "$out"; then return 0; fi

  echo "Tidak dapat mengambil updater dari jalur stabil maupun mirror." >&2
  return 1
}

fetch_body "$TMP/install-body.sh"
python - "$TMP/install-body.sh" "$BODY_BLOB" "$RC51_APPLY_BLOB" <<'PY'
import hashlib,pathlib,sys
path,expected,apply_blob=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas bootstrap FurinaHub berubah: {actual} != {expected}")
text=data.decode('utf-8')
checks=(
    'VERSION="1.0.0-rc51"',
    'DEPENDENCY_REVISION="2026.08.17-r19"',
    f'RC51_APPLY_BLOB="{apply_blob}"',
    'RC50_BODY_BLOB="37fe2fef1debe5cd04404fd37e16bd710466b2db"',
    'FURINA_RESILIENT_UPDATE_WRAPPER_V3',
    'releases/latest/download',
    'furina-bootstrap-v1.0.0',
)
missing=[item for item in checks if item not in text]
if missing:
    raise SystemExit(f'Binding runtime RC51/r19 tidak lengkap: {missing}')
PY
bash "$TMP/install-body.sh" "$@"
