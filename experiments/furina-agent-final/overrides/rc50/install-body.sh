#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc50"
DEPENDENCY_REVISION="2026.08.17-r16"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
RC49_BODY_URL="$BASE/overrides/rc49/install-body.sh"
RC49_BODY_BLOB="44d4d038b6159f28dd95064eca67239b071b1201"
RC50_APPLY_URL="$BASE/overrides/rc50/apply.py"
RC50_APPLY_BLOB="7dfe9aab1b7bfa5c70191b00679acc17b17192c0"
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

CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then
  progress 100 "Furina Core sudah terbaru"
  printf '✓ FurinaHub Core %s · runtime %s.\n' "$VERSION" "$DEPENDENCY_REVISION"
  exit 0
fi

if [[ "$CURRENT" != "$VERSION" ]]; then
  progress 8 "Menyiapkan fondasi Core"
  fetch "$RC49_BODY_URL" "$TMP/rc49-body.sh"
  verify_blob "$TMP/rc49-body.sh" "$RC49_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/rc49-body.sh" >>"$ROOT/logs/update-rc50-furinahub.log" 2>&1
fi

progress 58 "Memasang pengalaman companion baru"
fetch "$RC50_APPLY_URL" "$TMP/apply-rc50.py"
verify_blob "$TMP/apply-rc50.py" "$RC50_APPLY_BLOB"
if [[ "$(core_version 2>/dev/null || true)" != "$VERSION" ]]; then
  python "$TMP/apply-rc50.py" "$ROOT" >>"$ROOT/logs/update-rc50-furinahub.log" 2>&1
fi
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"

progress 88 "Menyelesaikan runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Core dan dependency siap"
printf '✓ FurinaHub Core %s aktif · runtime %s.\n' "$VERSION" "$DEPENDENCY_REVISION"
printf '  Muat ulang FurinaHub agar proses Core baru digunakan.\n'
