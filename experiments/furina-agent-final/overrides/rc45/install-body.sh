#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc45"
HUB_VERSION="1.0.0-rc28"
DEPENDENCY_REVISION="2026.08.15-r9"
OPENCONNECTOR_COMMIT="d478400141c33bb5ddf823e09b293e9d7154da97"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PINNED_RC43="44d215a38b336c903d06f04be01f30e60143ba35"
PINNED_RC44="783e443f2bae6cd201c9a08a670caffffc6082ac"
RC43_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC43/experiments/furina-agent-final"
RC44_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC44/experiments/furina-agent-final"
RC43_BODY_URL="$RC43_BASE/overrides/rc43/install-body.sh"
RC43_BODY_BLOB="dcaeee6a1ad8588f76c37138b180b472b8720178"
RC44_APPLY_URL="$RC44_BASE/overrides/rc44/apply.py"
RC44_APPLY_BLOB="1c81b788e0581f363cc166b576feee68ec8b5798"
RC44_AUDIT_URL="$RC44_BASE/overrides/rc44/audit-extra.py"
RC44_AUDIT_BLOB="cec2f8d52454ebc8671ce7596f4140a1dff0d4cd"
RC45_APPLY_URL="$BASE/overrides/rc45/apply.py"
RC45_APPLY_BLOB="b85cacc58d24889e8f600c12f8fc64d3930f27f3"
RELEASE_BASE="https://github.com/WynnDev-rill/furina/releases/download/furinahub-v1.0.0-rc28"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
mkdir -p "$ROOT"/{cache,logs,run,data,models}
LOG="$ROOT/logs/update-rc45-furinahub.log"
: > "$LOG"

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
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 4 "$url" -o "$out"
  elif command -v python >/dev/null 2>&1; then
    python - "$url" "$out" <<'PY'
import sys,urllib.request
urllib.request.urlretrieve(sys.argv[1],sys.argv[2])
PY
  else
    pkg install -y python >/dev/null
    python - "$url" "$out" <<'PY'
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

prepare_rc43_foundation() {
  progress 4 "Merekonstruksi fondasi Core RC43"
  fetch "$RC43_BODY_URL" "$TMP/rc43-install-body.sh"
  verify_blob "$TMP/rc43-install-body.sh" "$RC43_BODY_BLOB"
  python - "$TMP/rc43-install-body.sh" "$RC43_BASE" <<'PY'
from pathlib import Path
import re,sys
path=Path(sys.argv[1]); pinned=sys.argv[2]
text=path.read_text(encoding='utf-8')
text,count=re.subn(r'^BASE="[^"]+"$', f'BASE="{pinned}"', text, count=1, flags=re.M)
if count != 1:
    raise SystemExit('RC43 BASE assignment tidak ditemukan')
old_install='run_quiet "Menyiapkan runtime Plugin" 18 install_openconnector'
old_start='run_quiet "Menyalakan layanan Plugin (dapat memerlukan 45 detik)" 96 start_openconnector'
if old_install not in text or old_start not in text:
    raise SystemExit('RC43 Plugin marker berubah')
text=text.replace(old_install, 'mark 18 "Runtime Plugin ditangani RC45"', 1)
text=text.replace(old_start, 'mark 96 "Startup Plugin ditangani RC45"', 1)
path.write_text(text,encoding='utf-8')
PY
  mkdir -p "$TMP/fake-bin"
  cat > "$TMP/fake-bin/termux-open" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
exit 0
SH
  chmod 755 "$TMP/fake-bin/termux-open"
  PATH="$TMP/fake-bin:$PATH" bash "$TMP/rc43-install-body.sh" "$@" >>"$LOG" 2>&1
  test "$(core_version)" = "1.0.0-rc43"
}

apply_rc44_foundation() {
  progress 45 "Menerapkan perbaikan Core RC44"
  fetch "$RC44_APPLY_URL" "$TMP/apply-rc44.py"
  verify_blob "$TMP/apply-rc44.py" "$RC44_APPLY_BLOB"
  fetch "$RC44_AUDIT_URL" "$TMP/audit-rc44.py"
  verify_blob "$TMP/audit-rc44.py" "$RC44_AUDIT_BLOB"
  rm -rf "$TMP/stage44"; mkdir -p "$TMP/stage44"
  cp -R "$ROOT/core" "$TMP/stage44/core"
  python "$TMP/apply-rc44.py" "$TMP/stage44"
  python "$TMP/audit-rc44.py" "$TMP/stage44"
  FURINA_HOME="$TMP/test44" PYTHONPATH="$TMP/stage44/core" python -m compileall -q "$TMP/stage44/core/furina_agent"
  FURINA_HOME="$TMP/test44" PYTHONPATH="$TMP/stage44/core" python - <<'PY'
from furina_agent.version import VERSION
assert VERSION == '1.0.0-rc44'
print('FURINAHUB_RC44_FOUNDATION_OK')
PY
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage44/core" "$ROOT/core"
}

ensure_runtime_dependencies() {
  progress 57 "Memeriksa dependency Plugin"
  local packages=()
  command -v python >/dev/null 2>&1 || packages+=(python)
  command -v curl >/dev/null 2>&1 || packages+=(curl)
  command -v git >/dev/null 2>&1 || packages+=(git)
  command -v node >/dev/null 2>&1 || packages+=(nodejs-lts)
  if (( ${#packages[@]} )); then pkg install -y "${packages[@]}" >>"$LOG" 2>&1; fi
  if ! node - <<'JS' >/dev/null 2>&1
const [maj,min]=process.versions.node.split('.').map(Number);
if (maj<22 || (maj===22 && min<13)) process.exit(1);
import('node:sqlite').catch(()=>process.exit(1));
JS
  then
    pkg install -y nodejs-lts >>"$LOG" 2>&1
  fi
  node - <<'JS' >/dev/null 2>&1 || { echo "Node.js 22.13+ dengan node:sqlite diperlukan untuk Plugin." >&2; return 1; }
const [maj,min]=process.versions.node.split('.').map(Number);
if (maj<22 || (maj===22 && min<13)) process.exit(1);
import('node:sqlite').catch(()=>process.exit(1));
JS
}

install_openconnector_runtime() {
  progress 64 "Memperbaiki runtime Plugin"
  local app="$ROOT/openconnector" marker="$ROOT/data/openconnector_revision" source="$TMP/openconnector" healthy=0
  if [[ -f "$app/package.json" && -f "$app/src/server/index.ts" && -d "$app/node_modules" ]] \
      && [[ "$(cat "$marker" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]]; then
    if (cd "$app" && node scripts/ensure-generated.ts >/dev/null 2>>"$LOG"); then healthy=1; fi
  fi
  if (( healthy == 0 )); then
    rm -rf "$source"
    git init -q "$source"
    git -C "$source" remote add origin https://github.com/oomol-lab/open-connector.git
    git -C "$source" fetch -q --depth 1 origin "$OPENCONNECTOR_COMMIT"
    git -C "$source" checkout -q --detach FETCH_HEAD
    (cd "$source" && npm install --omit=dev --workspaces=false --no-audit --no-fund) >>"$LOG" 2>&1
    (cd "$source" && node scripts/ensure-generated.ts) >>"$LOG" 2>&1
    test -f "$source/src/server/index.ts"
    test -f "$source/src/providers/registry.generated.ts"
    rm -rf "$source/.git"
    rm -rf "$ROOT/openconnector.prev"
    if [[ -d "$app" ]]; then mv "$app" "$ROOT/openconnector.prev"; fi
    mv "$source" "$app"
  fi
  if [[ ! -s "$ROOT/data/openconnector-encryption.key" ]]; then
    python - <<'PY' > "$ROOT/data/openconnector-encryption.key"
import secrets
print(secrets.token_urlsafe(48))
PY
    chmod 600 "$ROOT/data/openconnector-encryption.key"
  fi
  printf '%s\n' "$OPENCONNECTOR_COMMIT" > "$marker"
  printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
}

install_openconnector_launcher() {
  progress 73 "Memasang launcher Plugin"
  if command -v furina-openconnector >/dev/null 2>&1; then furina-openconnector stop >/dev/null 2>&1 || true; fi
  cat > "$PREFIX/bin/furina-openconnector" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
APP="$ROOT/openconnector"
PID="$ROOT/run/openconnector.pid"
LOG="$ROOT/logs/openconnector.log"
URL="http://127.0.0.1:3000/v1/actions"
healthy() { curl -fsS --max-time 2 "$URL" >/dev/null 2>&1; }
running_pid() { [[ -f "$PID" ]] || return 1; local v; v="$(cat "$PID" 2>/dev/null || true)"; [[ "$v" =~ ^[0-9]+$ ]] && kill -0 "$v" >/dev/null 2>&1; }
stop_runtime() { if running_pid; then kill "$(cat "$PID")" >/dev/null 2>&1 || true; for _ in $(seq 1 20); do running_pid || break; sleep 0.1; done; fi; rm -f "$PID"; }
start_runtime() {
  healthy && return 0
  running_pid && stop_runtime
  test -f "$APP/src/server/index.ts" || { echo "Runtime Plugin belum terpasang." >&2; return 3; }
  test -s "$ROOT/data/openconnector-encryption.key" || { echo "Kunci Plugin belum tersedia." >&2; return 3; }
  mkdir -p "$ROOT/run" "$ROOT/logs" "$ROOT/data/openconnector"
  : > "$LOG"
  local key; key="$(cat "$ROOT/data/openconnector-encryption.key")"
  (cd "$APP" && exec env HOST=127.0.0.1 PORT=3000 OOMOL_CONNECT_ORIGIN="http://127.0.0.1:3000" OOMOL_CONNECT_DATA_DIR="$ROOT/data/openconnector" OOMOL_CONNECT_ENCRYPTION_KEY="$key" node src/server/index.ts) >>"$LOG" 2>&1 &
  echo "$!" > "$PID"
  for _ in $(seq 1 120); do
    healthy && return 0
    if ! running_pid; then rm -f "$PID"; echo "Runtime Plugin berhenti saat startup." >&2; tail -n 20 "$LOG" >&2 || true; return 4; fi
    sleep 0.25
  done
  echo "Runtime Plugin belum siap setelah 30 detik." >&2
  tail -n 20 "$LOG" >&2 || true
  stop_runtime
  return 4
}
case "${1:-start}" in
  start) start_runtime ;;
  stop) stop_runtime ;;
  restart) stop_runtime; start_runtime ;;
  status) healthy && { echo ready; exit 0; }; echo offline; exit 1 ;;
  logs) tail -n 60 "$LOG" 2>/dev/null || true ;;
  *) echo "usage: furina-openconnector {start|stop|restart|status|logs}" >&2; exit 2 ;;
esac
SH
  chmod 755 "$PREFIX/bin/furina-openconnector"
}

start_openconnector_with_repair() {
  progress 80 "Menyalakan layanan Plugin"
  if furina-openconnector start >>"$LOG" 2>&1; then return 0; fi
  echo "Startup Plugin pertama gagal; memperbaiki dependency npm sekali." >>"$LOG"
  (cd "$ROOT/openconnector" && npm install --omit=dev --workspaces=false --no-audit --no-fund) >>"$LOG" 2>&1
  (cd "$ROOT/openconnector" && node scripts/ensure-generated.ts) >>"$LOG" 2>&1
  furina-openconnector restart >>"$LOG" 2>&1
}

apply_rc45() {
  progress 87 "Menerapkan Core RC45"
  fetch "$RC45_APPLY_URL" "$TMP/apply-rc45.py"
  verify_blob "$TMP/apply-rc45.py" "$RC45_APPLY_BLOB"
  rm -rf "$TMP/stage45"; mkdir -p "$TMP/stage45"
  cp -R "$ROOT/core" "$TMP/stage45/core"
  python "$TMP/apply-rc45.py" "$TMP/stage45"
  FURINA_HOME="$TMP/test45" PYTHONPATH="$TMP/stage45/core" python -m compileall -q "$TMP/stage45/core/furina_agent"
  FURINA_HOME="$TMP/test45" PYTHONPATH="$TMP/stage45/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.hub import Runtime
assert VERSION == '1.0.0-rc45'
assert hasattr(Runtime, '_connector_runtime_error')
print('FURINAHUB_RC45_CORE_VALIDATED')
PY
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage45/core" "$ROOT/core"
}

ensure_rc28_apk_file() {
  local marker="$ROOT/data/furinahub_apk_revision" out="$HOME/FurinaHub.apk" before
  before="$(cat "$marker" 2>/dev/null || true)"
  if [[ "$before" == "$HUB_VERSION" && -s "$out" ]]; then return 0; fi
  fetch "$RELEASE_BASE/bridge.json" "$TMP/bridge.json"
  read -r apk_url apk_sha < <(python - "$TMP/bridge.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['package_name']=='com.wynndev.furinaagentbridge'
assert int(m['version_code'])==10028 and m['version']=='1.0.0-rc28'
print(m['apk_url'],m['sha256'])
PY
)
  fetch "$apk_url" "$TMP/FurinaHub.apk"
  echo "$apk_sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null
  cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"; printf '%s\n' "$HUB_VERSION" > "$marker"
  if command -v termux-open >/dev/null 2>&1; then termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1 || true; fi
}

CURRENT="$(core_version 2>/dev/null || true)"
if [[ "$CURRENT" != "1.0.0-rc43" && "$CURRENT" != "1.0.0-rc44" && "$CURRENT" != "1.0.0-rc45" ]]; then
  prepare_rc43_foundation "$@"
  CURRENT="$(core_version)"
fi
if [[ "$CURRENT" == "1.0.0-rc43" ]]; then
  apply_rc44_foundation
  CURRENT="1.0.0-rc44"
fi
ensure_runtime_dependencies
install_openconnector_runtime
install_openconnector_launcher
start_openconnector_with_repair
if [[ "$CURRENT" != "1.0.0-rc45" ]]; then
  test "$CURRENT" = "1.0.0-rc44"
  apply_rc45
fi
progress 95 "Memeriksa Plugin setelah upgrade"
furina-openconnector status >>"$LOG" 2>&1
progress 97 "Memeriksa APK FurinaHub"
ensure_rc28_apk_file
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
progress 100 "Core dan Plugin siap"
printf '\n✓ FurinaHub Core RC45 aktif.\n'
printf '  Plugin: siap di http://127.0.0.1:3000\n'
printf '  APK: FurinaHub RC28.\n'
printf '  Log: %s\n' "$LOG"
