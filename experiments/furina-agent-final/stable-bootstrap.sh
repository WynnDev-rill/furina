#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# This asset is intentionally version-agnostic. The mutable release channel only
# needs to deliver this bootstrap once; every run resolves the current installer
# from the source branch before execution.
FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_STABLE_BOOTSTRAP="1"
API_URL="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/install.sh?ref=experiment/furina-agent-termux"
RAW_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh"
WEB_URL="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh"
BOOTSTRAP_URL="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final/install.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FETCH_CODE="000"

fetch_script() {
  local url="$1" api="${2:-0}" out="$TMP/current-install.sh" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 90
              --retry 2 --retry-delay 1 --retry-all-errors
              -o "$out" -w '%{http_code}'
              -H 'User-Agent: Furina-Stable-Bootstrap/1'
              -H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  if [[ "$api" == "1" ]]; then
    args+=(-H 'Accept: application/vnd.github.raw+json')
  fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]] &&
     grep -Fq 'FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"' "$out" &&
     ! grep -Fq 'FURINA_STABLE_BOOTSTRAP="1"' "$out"; then
    return 0
  fi
  rm -f "$out"
  return 1
}

command -v curl >/dev/null 2>&1 || {
  if [[ -d /data/data/com.termux/files/usr ]]; then
    pkg install -y curl >/dev/null
  else
    echo "curl tidak tersedia untuk bootstrap update." >&2
    exit 1
  fi
}

if fetch_script "$API_URL" 1 ||
   fetch_script "$RAW_URL" ||
   fetch_script "$WEB_URL" ||
   fetch_script "$BOOTSTRAP_URL"; then
  if [[ "${FURINA_BOOTSTRAP_VALIDATE_ONLY:-0}" == "1" ]]; then
    grep -E '^(FURINA_UPDATER_GENERATION|VERSION|DEPENDENCY_REVISION)=' "$TMP/current-install.sh" || true
    echo "FURINA_STABLE_BOOTSTRAP_RESOLVED"
    exit 0
  fi
  exec bash "$TMP/current-install.sh" "$@"
fi

echo "Channel update dapat dijangkau, tetapi installer terbaru belum dapat diambil. Coba ulang 'furina update'." >&2
exit 75
