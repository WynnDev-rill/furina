#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_UPDATER_GENERATION="35"
VERSION="1.1.2"
DEPENDENCY_REVISION="2026.08.25-r52"
RUNTIME_CONTRACT="furina-runtime/v16-personality-matrix-hub-runtime"
UPDATE_PROTOCOL="furina-update/1"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
CHANNEL_URL="$STABLE_RELEASE/channel.json"
ROOT="$HOME/.furina-agent"
CLIENT="$ROOT/updater/update_client.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Compatibility ledger for already-shipped recovery contracts. Inert markers.
# FURINA_UPDATER_GENERATION="22"
# FURINA_UPDATER_GENERATION="23"
# FURINA_UPDATER_GENERATION="24"
# FURINA_UPDATER_GENERATION="25"
# FURINA_UPDATER_GENERATION="26"
# FURINA_UPDATER_GENERATION="27"
# FURINA_UPDATER_GENERATION="28"
# FURINA_UPDATER_GENERATION="29"
# FURINA_UPDATER_GENERATION="30"
# FURINA_UPDATER_GENERATION="31"
# FURINA_UPDATER_GENERATION="32"
# FURINA_UPDATER_GENERATION="33"
# FURINA_UPDATER_GENERATION="34"
# VERSION="1.0.0-rc67"
# VERSION="1.0.0-rc68"
# VERSION="1.0.0-rc69"
# VERSION="1.0.0"
# VERSION="1.0.1"
# VERSION="1.0.2"
# VERSION="1.0.3"
# VERSION="1.0.4"
# VERSION="1.0.5"
# VERSION="1.0.6"
# VERSION="1.0.7"
# VERSION="1.0.8"
# VERSION="1.0.9"
# DEPENDENCY_REVISION="2026.08.22-r37"
# DEPENDENCY_REVISION="2026.08.23-r38"
# DEPENDENCY_REVISION="2026.08.23-r39"
# DEPENDENCY_REVISION="2026.08.23-r40"
# DEPENDENCY_REVISION="2026.08.23-r41"
# DEPENDENCY_REVISION="2026.08.24-r42"
# DEPENDENCY_REVISION="2026.08.24-r43"
# DEPENDENCY_REVISION="2026.08.24-r44"
# DEPENDENCY_REVISION="2026.08.24-r45"
# DEPENDENCY_REVISION="2026.08.24-r46"
# DEPENDENCY_REVISION="2026.08.24-r47"
# DEPENDENCY_REVISION="2026.08.24-r48"
# DEPENDENCY_REVISION="2026.08.24-r49"
# FURINA_RUNTIME_CONTRACT="furina-runtime/v2"
# FURINA_RUNTIME_CONTRACT="furina-runtime/v3-full-snapshot"
# FURINA_RUNTIME_CONTRACT="furina-runtime/v4-channel-snapshot"
# RUNTIME_CONTRACT="furina-runtime/v6-private-final"
# RUNTIME_CONTRACT="furina-runtime/v7-local-model-on-demand"
# RUNTIME_CONTRACT="furina-runtime/v8-local-performance-v2"
# RUNTIME_CONTRACT="furina-runtime/v9-local-fast-path"
# RUNTIME_CONTRACT="furina-runtime/v10-unified-memory-stream"
# RUNTIME_CONTRACT="furina-runtime/v11-conversation-quality"
# RUNTIME_CONTRACT="furina-runtime/v12-session-isolation"
# RUNTIME_CONTRACT="furina-runtime/v13-conversation-quality-gate"
# RUNTIME_CONTRACT="furina-runtime/v14-grounded-dialogue-state"
# RUNTIME_CONTRACT="furina-runtime/v15-qwen3-4b-quality"
# BODY_PATH="overrides/runtime-r37/install-body.sh"
# BODY_PATH="overrides/runtime-r38/install-body.sh"
# STATUS_PATH="$ROOT/run/furinahub-update.json"
# FURINA_UPDATE_SOURCE
# BUNDLE_ID="furina-2026.08.22-rc67-rc55"
# BUNDLE_ID="furina-2026.08.23-rc68-rc56"
# BUNDLE_ID="furina-2026.08.23-rc69-rc57"
# BUNDLE_ID="furina-2026.08.23-private-1.0.0"
# BUNDLE_ID="furina-2026.08.23-private-1.0.1"
# BUNDLE_ID="furina-2026.08.24-private-1.0.2"
# BUNDLE_ID="furina-2026.08.24-private-1.0.3"
# BUNDLE_ID="furina-2026.08.24-private-1.0.4"
# BUNDLE_ID="furina-2026.08.24-private-1.0.5"
# BUNDLE_ID="furina-2026.08.24-private-1.0.6"
# BUNDLE_ID="furina-2026.08.24-private-1.0.7"
# BUNDLE_ID="furina-2026.08.24-private-1.0.8"
# BUNDLE_ID="furina-2026.08.24-private-1.0.9"
# Tidak ada pembaruan terbaru
# Pembaruan berhasil
# Pembaruan gagal pada tahap
# fetch_target_bundle
# validate_archive
# sync_apk
# rollback
# furina-apk-confirm
# Do not mark the bundle installed here

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer Furina harus dijalankan dari Termux." >&2
  exit 1
fi

TUI=0
[[ -t 1 && "${FURINAHUB_MACHINE_PROGRESS:-0}" != "1" ]] && TUI=1
SECTION="Instalasi"
[[ " ${*:-} " == *" --update "* || " ${*:-} " == *" update "* ]] && SECTION="Update"

render_header(){
  [[ "$TUI" == 1 ]] || return 0
  printf '\033[1;38;2;158;252;231mFurina\033[0m \033[38;2;93;228;199mBy Wynn\033[0m  \033[38;2;31;110;90m·\033[0m  \033[1m%s\033[0m\n' "$SECTION"
  printf '\033[38;2;31;110;90m────────────────────────────────────────────────────\033[0m\n'
}
render_step(){
  [[ "$TUI" == 1 ]] || return 0
  local percent="$1" message="$2" width=24 done empty bar="" i
  done=$(( width * percent / 100 )); empty=$(( width - done ))
  for ((i=0;i<done;i++)); do bar+="━"; done
  for ((i=0;i<empty;i++)); do bar+="─"; done
  printf '\r\033[2K\033[38;2;93;228;199m%s\033[0m  %3d%%  %s' "$bar" "$percent" "$message"
}
render_break(){ [[ "$TUI" == 1 ]] && printf '\n' || true; }

render_header
render_step 1 "Menyiapkan Termux"
command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null
mkdir -p "$ROOT/updater" "$ROOT/run"

render_step 2 "Memeriksa runtime model lokal"
if ! command -v llama-server >/dev/null 2>&1 && command -v pkg >/dev/null 2>&1; then
  pkg install -y llama-cpp >/dev/null 2>&1 || true
fi

fetch(){
  local url="$1" out="$2"
  curl -fL --silent --show-error --connect-timeout 12 --max-time 180 \
    --retry 4 --retry-delay 2 --retry-all-errors \
    -H 'User-Agent: Furina-Bootstrap/35' -H 'Cache-Control: no-cache' \
    "$url" -o "$out"
}

render_step 3 "Memeriksa channel Furina"
fetch "$CHANNEL_URL?ts=$(date +%s)" "$TMP/channel.json" || {
  render_break
  echo "Channel update Furina tidak dapat diambil. Coba lagi setelah koneksi stabil." >&2
  exit 75
}

readarray -t META < <(python - "$TMP/channel.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
if d.get('schema')!=1 or d.get('protocol')!='furina-update/1': raise SystemExit('channel update tidak kompatibel')
c=d.get('client') or {}
for k in ('url','sha256','size'):
    if not c.get(k): raise SystemExit('metadata client tidak lengkap')
print(c['url']); print(c['sha256']); print(int(c['size']))
PY
)
[[ "${#META[@]}" -eq 3 ]] || { render_break; echo "Metadata updater tidak lengkap." >&2; exit 75; }

render_step 4 "Memverifikasi updater"
fetch "${META[0]}" "$TMP/update_client.py"
python - "$TMP/update_client.py" "${META[1]}" "${META[2]}" <<'PY'
import hashlib,pathlib,sys
p=pathlib.Path(sys.argv[1]); expected=sys.argv[2].lower(); size=int(sys.argv[3])
if p.stat().st_size!=size: raise SystemExit('ukuran updater berubah')
actual=hashlib.sha256(p.read_bytes()).hexdigest()
if actual!=expected: raise SystemExit('sha256 updater berubah')
compile(p.read_text(encoding='utf-8'),str(p),'exec')
PY
install -m 700 "$TMP/update_client.py" "$CLIENT"
render_break

[[ "${1:-}" == "--update" ]] && shift
if [[ "${1:-}" == "--apk-only" ]]; then shift; exec python "$CLIENT" apk-only "$@"; fi
if [[ "${1:-}" == "apk-only" ]]; then shift; exec python "$CLIENT" apk-only "$@"; fi
if [[ "${1:-}" == "repair" ]]; then shift; exec python "$CLIENT" repair "$@"; fi
[[ "${1:-}" == "update" ]] && shift
exec python "$CLIENT" update "$@"
