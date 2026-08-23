#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_UPDATER_GENERATION="23"
VERSION="1.0.0-rc68"
DEPENDENCY_REVISION="2026.08.23-r38"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BODY_PATH="overrides/runtime-r38/install-body.sh"
BODY_BLOB="c1365faed0d7d9e193ad01d852e57b229e833de0"
RUNTIME_CONTRACT="furina-runtime/v4-channel-snapshot"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

fetch_url(){
  local url="$1" out="$2" api="${3:-0}" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 180 --retry 4 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Bootstrap/23' -H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  [[ "$api" == 1 ]] && args+=(-H 'Accept: application/vnd.github.raw+json')
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  [[ "$code" == 200 && -s "$out" ]]
}
verify_body(){
  python - "$1" "$BODY_BLOB" "$RUNTIME_CONTRACT" <<'PY'
import hashlib,pathlib,sys
p,expected,contract=sys.argv[1:]
d=pathlib.Path(p).read_bytes(); actual=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if actual!=expected: raise SystemExit(1)
t=d.decode()
checks=(
  'VERSION="1.0.0-rc68"',
  'DEPENDENCY_REVISION="2026.08.23-r38"',
  f'FURINA_RUNTIME_CONTRACT="{contract}"',
  'BUNDLE_ID="furina-2026.08.23-rc68-rc56"',
  'fetch_target_bundle',
  'furina-apk-confirm',
  'Do not mark the bundle installed here',
)
missing=[x for x in checks if x not in t]
if missing: raise SystemExit(1)
PY
}
fetch_verified_body(){
  local out="$1"
  local -a urls=(
    "$STABLE_RELEASE/furina-runtime-r38.sh?ts=$(date +%s)"
    "$API_BASE/$BODY_PATH?ref=experiment/furina-agent-termux"
    "$RAW_BASE/$BODY_PATH"
    "$WEB_BASE/$BODY_PATH"
    "$BOOTSTRAP_CDN/$BODY_PATH"
  )
  local i api
  for i in "${!urls[@]}"; do
    api=0; [[ "${urls[$i]}" == "$API_BASE/"* ]] && api=1
    if fetch_url "${urls[$i]}" "$out" "$api" && verify_body "$out"; then return 0; fi
  done
  return 1
}

fetch_verified_body "$TMP/install-body.sh" || { echo "Tidak dapat mengambil updater RC68/r38 yang terverifikasi." >&2; exit 75; }
bash "$TMP/install-body.sh" "$@"
