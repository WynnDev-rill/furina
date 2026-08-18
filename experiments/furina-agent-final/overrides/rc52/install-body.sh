#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc52"
DEPENDENCY_REVISION="2026.08.18-r21"
ROOT="$HOME/.furina-agent"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
RC51_BODY_PATH="overrides/rc51/install-body.sh"
RC51_BODY_BLOB="5e5396a488a0c7a69038a38eaa85d826a31c0045"
RC52_APPLY_PATH="overrides/rc52/apply.py"
RC52_APPLY_BLOB="b601bc4ad0b9c77bb6cdfeb64029e7046a624310"
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
  local url="$1" out="$2" api="${3:-0}" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 90
              -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/4')
  if [[ "$api" == "1" ]]; then
    args+=(-H 'Accept: application/vnd.github.raw+json')
  fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]]; then return 0; fi
  rm -f "$out"
  return 1
}

fetch_rel() {
  local rel="$1" out="$2" asset github_blocked=0
  command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
  case "$rel" in
    overrides/rc51/install-body.sh) asset="core-rc51-install-body.sh" ;;
    overrides/rc52/apply.py) asset="core-rc52-apply.py" ;;
    *) asset="" ;;
  esac
  if [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; then return 0; fi
  [[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1
  if fetch_url "$BOOTSTRAP_CDN/$rel" "$out"; then return 0; fi
  if [[ "$github_blocked" == "0" ]] && fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1; then return 0; fi
  [[ "$FETCH_CODE" == "429" || "$FETCH_CODE" == "403" ]] && github_blocked=1
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

ensure_bridge_target() {
  local hub="$ROOT/core/furina_agent/hub.py"
  [[ -f "$hub" ]] || return 0
  python - "$hub" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')
for old in ('"bridge_target": "1.0.0-rc35"','"bridge_target": "1.0.0-rc36"','"bridge_target": "1.0.0-rc37"','"bridge_target": "1.0.0-rc38"','"bridge_target": "1.0.0-rc39"'):
    s=s.replace(old,'"bridge_target": "1.0.0-rc40"')
if '"bridge_target": "1.0.0-rc40"' not in s:
    raise SystemExit("Bridge target Core tidak dikenali")
p.write_text(s,encoding='utf-8')
PY
}

mkdir -p "$ROOT/logs" "$ROOT/data"
CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then
  ensure_bridge_target
  progress 100 "Furina Core sudah terbaru"
  printf '✓ FurinaHub Core %s · runtime %s.\n' "$VERSION" "$DEPENDENCY_REVISION"
  exit 0
fi

if [[ "$CURRENT" != "1.0.0-rc51" && "$CURRENT" != "$VERSION" ]]; then
  progress 8 "Menyiapkan Core RC51"
  fetch_rel "$RC51_BODY_PATH" "$TMP/rc51-body.sh"
  verify_blob "$TMP/rc51-body.sh" "$RC51_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/rc51-body.sh" >>"$ROOT/logs/update-rc52-furinahub.log" 2>&1
fi

progress 62 "Memperbaiki runtime model lokal"
fetch_rel "$RC52_APPLY_PATH" "$TMP/apply-rc52.py"
verify_blob "$TMP/apply-rc52.py" "$RC52_APPLY_BLOB"
if [[ "$(core_version 2>/dev/null || true)" != "$VERSION" ]]; then
  python "$TMP/apply-rc52.py" "$ROOT" >>"$ROOT/logs/update-rc52-furinahub.log" 2>&1
fi
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"
ensure_bridge_target

progress 92 "Memeriksa runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Core dan dependency siap"
printf '✓ FurinaHub Core %s aktif · runtime %s.\n' "$VERSION" "$DEPENDENCY_REVISION"
