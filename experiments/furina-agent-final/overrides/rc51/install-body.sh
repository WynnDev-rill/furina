#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc51"
DEPENDENCY_REVISION="2026.08.17-r19"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
LATEST_RELEASE="https://github.com/WynnDev-rill/furina/releases/latest/download"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
RC50_BODY_PATH="overrides/rc50/install-body.sh"
RC50_BODY_BLOB="37fe2fef1debe5cd04404fd37e16bd710466b2db"
RC51_APPLY_PATH="overrides/rc51/apply.py"
RC51_APPLY_BLOB="736555772589d692a165ad60fac8c8c4d458e23b"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

progress() {
  local pct="$1"; shift
  if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then
    printf 'PROGRESS %d %s\n' "$pct" "$*"
  else
    printf '[%3d%%] %s\n' "$pct" "$*"
  fi
}

FETCH_CODE="000"
fetch_url() {
  local url="$1" out="$2" api="${3:-0}" headers code
  headers="$(mktemp "$TMP/headers.XXXXXX")"
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 90
              -D "$headers" -o "$out" -w '%{http_code}'
              -H 'User-Agent: Furina-Core-Updater/3')
  if [[ "$api" == "1" ]]; then
    args+=(-H 'Accept: application/vnd.github.raw+json')
  fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]]; then
    rm -f "$headers"
    return 0
  fi
  rm -f "$out" "$headers"
  return 1
}

fetch_rel() {
  local rel="$1" out="$2" asset github_blocked=0
  command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null

  case "$rel" in
    overrides/rc50/install-body.sh) asset="core-rc50-install-body.sh" ;;
    overrides/rc51/apply.py) asset="core-rc51-apply.py" ;;
    *) asset="" ;;
  esac

  if [[ -n "$asset" ]]; then
    if fetch_url "$LATEST_RELEASE/$asset" "$out"; then return 0; fi
    [[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1

    if [[ "$github_blocked" == "0" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; then
      return 0
    fi
  fi

  if fetch_url "$BOOTSTRAP_CDN/$rel" "$out"; then return 0; fi

  if [[ "$github_blocked" == "0" ]]; then
    if fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1; then return 0; fi
    [[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1
  fi
  if [[ "$github_blocked" == "0" ]] && fetch_url "$RAW_BASE/$rel" "$out"; then return 0; fi
  if [[ "$github_blocked" == "0" ]] && fetch_url "$WEB_BASE/$rel" "$out"; then return 0; fi

  echo "Tidak dapat mengambil $rel dari jalur update stabil maupun mirror." >&2
  return 1
}

verify_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas file berubah: {actual} != {expected}")
PY
}

core_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try: text=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text)
print(m.group(1) if m else 'unknown')
PY
}

install_update_transport() {
  mkdir -p "$PREFIX/bin"
  cat > "$PREFIX/bin/furina-update" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
LATEST="https://github.com/WynnDev-rill/furina/releases/latest/download/furina-install.sh"
STABLE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh"
BOOTSTRAP="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final/install.sh"
API="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final/install.sh?ref=experiment/furina-agent-termux"
RAW="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh"
WEB="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
FETCH_CODE="000"

fetch_script() {
  local url="$1" api="${2:-0}" out="$TMP/installer.sh" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 90
              -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/3')
  if [[ "$api" == "1" ]]; then
    args+=(-H 'Accept: application/vnd.github.raw+json')
  fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]] &&
     grep -Fq 'FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"' "$out"; then
    return 0
  fi
  rm -f "$out"
  return 1
}

github_blocked=0
if fetch_script "$LATEST"; then exec bash "$TMP/installer.sh" "$@"; fi
[[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1
if [[ "$github_blocked" == "0" ]] && fetch_script "$STABLE"; then exec bash "$TMP/installer.sh" "$@"; fi
if fetch_script "$BOOTSTRAP"; then exec bash "$TMP/installer.sh" "$@"; fi
if [[ "$github_blocked" == "0" ]] && fetch_script "$API" 1; then exec bash "$TMP/installer.sh" "$@"; fi
[[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1
if [[ "$github_blocked" == "0" ]] && fetch_script "$RAW"; then exec bash "$TMP/installer.sh" "$@"; fi
if [[ "$github_blocked" == "0" ]] && fetch_script "$WEB"; then exec bash "$TMP/installer.sh" "$@"; fi

echo "Update belum dapat dijangkau. Cukup jalankan ulang perintah yang sama: furina update" >&2
exit 75
SH
  chmod 755 "$PREFIX/bin/furina-update"

  local launcher="$PREFIX/bin/furina" real="$PREFIX/bin/furina-real"
  if [[ -e "$launcher" ]] && ! grep -Fq 'FURINA_RESILIENT_UPDATE_WRAPPER_V3' "$launcher" 2>/dev/null; then
    if grep -Eq 'FURINA_RESILIENT_UPDATE_WRAPPER_V[12]' "$launcher" 2>/dev/null && [[ -x "$real" ]]; then
      :
    else
      rm -f "$real"
      mv "$launcher" "$real"
    fi
  fi
  if [[ -x "$real" ]]; then
    cat > "$launcher" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
# FURINA_RESILIENT_UPDATE_WRAPPER_V3
set -euo pipefail
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
if [[ "${1:-}" == "update" ]]; then
  shift
  exec "$PREFIX/bin/furina-update" "$@"
fi
exec "$PREFIX/bin/furina-real" "$@"
SH
    chmod 755 "$launcher"
  fi
}

ensure_bridge_target() {
  local hub="$ROOT/core/furina_agent/hub.py"
  [[ -f "$hub" ]] || return 0
  python - "$hub" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
for old in ('"bridge_target": "1.0.0-rc35"','"bridge_target": "1.0.0-rc36"','"bridge_target": "1.0.0-rc37"'):
    if old in s:
        s=s.replace(old,'"bridge_target": "1.0.0-rc38"')
if '"bridge_target": "1.0.0-rc38"' not in s:
    raise SystemExit("Bridge target Core tidak dikenali")
p.write_text(s,encoding='utf-8')
PY
}

mkdir -p "$ROOT/logs" "$ROOT/data"
install_update_transport
CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then
  ensure_bridge_target
  progress 100 "Furina Core sudah terbaru"
  printf '✓ FurinaHub Core %s · runtime %s · updater V3 aktif.\n' "$VERSION" "$DEPENDENCY_REVISION"
  exit 0
fi

if [[ "$CURRENT" != "1.0.0-rc50" && "$CURRENT" != "$VERSION" ]]; then
  progress 8 "Menyiapkan fondasi Core"
  fetch_rel "$RC50_BODY_PATH" "$TMP/rc50-body.sh"
  verify_blob "$TMP/rc50-body.sh" "$RC50_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/rc50-body.sh" >>"$ROOT/logs/update-rc51-furinahub.log" 2>&1
fi

progress 56 "Memperbarui pipeline companion"
fetch_rel "$RC51_APPLY_PATH" "$TMP/apply-rc51.py"
verify_blob "$TMP/apply-rc51.py" "$RC51_APPLY_BLOB"
if [[ "$(core_version 2>/dev/null || true)" != "$VERSION" ]]; then
  python "$TMP/apply-rc51.py" "$ROOT" >>"$ROOT/logs/update-rc51-furinahub.log" 2>&1
fi
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"
ensure_bridge_target

progress 88 "Memeriksa runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Core dan dependency siap"
printf '✓ FurinaHub Core %s aktif · runtime %s · updater V3 aktif.\n' "$VERSION" "$DEPENDENCY_REVISION"
