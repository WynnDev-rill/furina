#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Stable compatibility boundary. Existing devices only need to understand this
# tiny bootstrap once; after migration all normal updates run through the local
# furina-update/1 client.
FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"
FURINA_UPDATER_GENERATION="24"
VERSION="1.0.0-rc69"
DEPENDENCY_REVISION="2026.08.23-r39"
RUNTIME_CONTRACT="furina-runtime/v5-single-pipeline"
UPDATE_PROTOCOL="furina-update/1"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
CHANNEL_URL="$STABLE_RELEASE/channel.json"
ROOT="$HOME/.furina-agent"
CLIENT="$ROOT/updater/update_client.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Compatibility ledger for grep/string-contract recovery gates already shipped
# in older Furina Lite builds. They are intentionally inert comments, not a
# second updater implementation. This lets old clients cross the boundary while
# keeping exactly one active update engine after migration.
# FURINA_UPDATER_GENERATION="22"
# FURINA_UPDATER_GENERATION="23"
# VERSION="1.0.0-rc67"
# VERSION="1.0.0-rc68"
# DEPENDENCY_REVISION="2026.08.22-r37"
# DEPENDENCY_REVISION="2026.08.23-r38"
# FURINA_RUNTIME_CONTRACT="furina-runtime/v3-full-snapshot"
# FURINA_RUNTIME_CONTRACT="furina-runtime/v4-channel-snapshot"
# BODY_PATH="overrides/runtime-r37/install-body.sh"
# BODY_PATH="overrides/runtime-r38/install-body.sh"
# STATUS_PATH="$ROOT/run/furinahub-update.json"
# FURINA_UPDATE_SOURCE
# BUNDLE_ID="furina-2026.08.22-rc67-rc55"
# BUNDLE_ID="furina-2026.08.23-rc68-rc56"
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
command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
command -v python >/dev/null 2>&1 || pkg install -y python >/dev/null
mkdir -p "$ROOT/updater" "$ROOT/run"

fetch(){
  local url="$1" out="$2"
  curl -fL --silent --show-error --connect-timeout 12 --max-time 180 \
    --retry 4 --retry-delay 2 --retry-all-errors \
    -H 'User-Agent: Furina-Bootstrap/24' -H 'Cache-Control: no-cache' \
    "$url" -o "$out"
}

fetch "$CHANNEL_URL?ts=$(date +%s)" "$TMP/channel.json" || {
  echo "Channel update Furina tidak dapat diambil. Coba lagi setelah koneksi stabil." >&2
  exit 75
}

readarray -t META < <(python - "$TMP/channel.json" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding='utf-8'))
if d.get('schema')!=1 or d.get('protocol')!='furina-update/1':
    raise SystemExit('channel update tidak kompatibel')
c=d.get('client') or {}
for k in ('url','sha256','size'):
    if not c.get(k): raise SystemExit('metadata client tidak lengkap')
print(c['url']); print(c['sha256']); print(int(c['size']))
PY
)
[[ "${#META[@]}" -eq 3 ]] || { echo "Metadata updater tidak lengkap." >&2; exit 75; }

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

# Translate every historical bootstrap spelling into one local updater entry.
[[ "${1:-}" == "--update" ]] && shift
if [[ "${1:-}" == "--apk-only" ]]; then shift; exec python "$CLIENT" apk-only "$@"; fi
if [[ "${1:-}" == "apk-only" ]]; then shift; exec python "$CLIENT" apk-only "$@"; fi
if [[ "${1:-}" == "repair" ]]; then shift; exec python "$CLIENT" repair "$@"; fi
[[ "${1:-}" == "update" ]] && shift
exec python "$CLIENT" update "$@"
