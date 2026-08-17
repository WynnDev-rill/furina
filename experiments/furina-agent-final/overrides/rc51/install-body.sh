#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc51"
DEPENDENCY_REVISION="2026.08.17-r16"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
RC50_BODY_URL="$BASE/overrides/rc50/install-body.sh"
RC50_BODY_BLOB="37fe2fef1debe5cd04404fd37e16bd710466b2db"
RC51_APPLY_URL="$BASE/overrides/rc51/apply.py"
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
fetch() {
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 4 "$url" -o "$out"
  else python - "$url" "$out" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve(sys.argv[1],sys.argv[2])
PY
  fi
}
verify_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected: raise SystemExit(f"Integritas file berubah: {actual} != {expected}")
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

mkdir -p "$ROOT/logs" "$ROOT/data"
CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then
  progress 100 "Furina Core sudah terbaru"
  printf '✓ FurinaHub Core %s · runtime %s.\n' "$VERSION" "$DEPENDENCY_REVISION"
  exit 0
fi

if [[ "$CURRENT" != "1.0.0-rc50" && "$CURRENT" != "$VERSION" ]]; then
  progress 8 "Menyiapkan fondasi Core"
  fetch "$RC50_BODY_URL" "$TMP/rc50-body.sh"
  verify_blob "$TMP/rc50-body.sh" "$RC50_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/rc50-body.sh" >>"$ROOT/logs/update-rc51-furinahub.log" 2>&1
fi

progress 56 "Memperbarui pipeline companion"
fetch "$RC51_APPLY_URL" "$TMP/apply-rc51.py"
verify_blob "$TMP/apply-rc51.py" "$RC51_APPLY_BLOB"
if [[ "$(core_version 2>/dev/null || true)" != "$VERSION" ]]; then
  python "$TMP/apply-rc51.py" "$ROOT" >>"$ROOT/logs/update-rc51-furinahub.log" 2>&1
fi
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"

progress 88 "Memeriksa runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Core dan dependency siap"
printf '✓ FurinaHub Core %s aktif · runtime %s.\n' "$VERSION" "$DEPENDENCY_REVISION"
