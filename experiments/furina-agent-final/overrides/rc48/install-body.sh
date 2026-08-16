#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc48"
DEPENDENCY_REVISION="2026.08.16-r12"
OPENCONNECTOR_COMMIT="d478400141c33bb5ddf823e09b293e9d7154da97"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
RC47_BODY_URL="$BASE/overrides/rc47/install-body.sh"
RC47_BODY_BLOB="088c75120ed0e757711257587973740c05093859"
RC48_APPLY_URL="$BASE/overrides/rc48/apply.py"
RC48_APPLY_BLOB="9d2a1c6bf1df6bcd464691b8bb1418b80cdf9443"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
mkdir -p "$ROOT"/{cache,logs,run,data,models}
LOG="$ROOT/logs/update-rc48-furinahub.log"
PLUGIN_LOG="$ROOT/logs/openconnector.log"
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
  else
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

ensure_dependencies() {
  progress 8 "Memeriksa runtime Plugin"
  local packages=()
  command -v python >/dev/null 2>&1 || packages+=(python)
  command -v curl >/dev/null 2>&1 || packages+=(curl)
  command -v git >/dev/null 2>&1 || packages+=(git)
  command -v node >/dev/null 2>&1 || packages+=(nodejs-lts)
  if (( ${#packages[@]} )); then
    pkg install -y "${packages[@]}" >>"$LOG" 2>&1
  fi
  if ! node - <<'JS' >/dev/null 2>&1
const [maj,min]=process.versions.node.split('.').map(Number);
if (maj < 22 || (maj === 22 && min < 18)) process.exit(1);
import('node:sqlite').then(m => { if (!m.DatabaseSync) process.exit(1) }).catch(()=>process.exit(1));
JS
  then
    pkg install -y nodejs-lts >>"$LOG" 2>&1
  fi
  node - <<'JS' >/dev/null 2>&1 || { echo "Node.js 22.18+ dengan node:sqlite diperlukan untuk Plugin." >&2; return 1; }
const [maj,min]=process.versions.node.split('.').map(Number);
if (maj < 22 || (maj === 22 && min < 18)) process.exit(1);
import('node:sqlite').then(m => { if (!m.DatabaseSync) process.exit(1) }).catch(()=>process.exit(1));
JS
}

ensure_rc47_base() {
  local current
  current="$(core_version 2>/dev/null || true)"
  if [[ "$current" == "1.0.0-rc47" || "$current" == "$VERSION" ]]; then return 0; fi
  progress 16 "Menyiapkan Core RC47"
  fetch "$RC47_BODY_URL" "$TMP/rc47-install-body.sh"
  verify_blob "$TMP/rc47-install-body.sh" "$RC47_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/rc47-install-body.sh" >>"$LOG" 2>&1
  test "$(core_version)" = "1.0.0-rc47"
}

apply_rc48() {
  if [[ "$(core_version 2>/dev/null || true)" == "$VERSION" ]]; then return 0; fi
  progress 28 "Menerapkan Core RC48"
  fetch "$RC48_APPLY_URL" "$TMP/apply-rc48.py"
  verify_blob "$TMP/apply-rc48.py" "$RC48_APPLY_BLOB"
  python "$TMP/apply-rc48.py" "$ROOT" >>"$LOG" 2>&1
  python -m compileall -q "$ROOT/core/furina_agent"
  test "$(core_version)" = "$VERSION"
}

install_openconnector_runtime() {
  progress 42 "Memeriksa OpenConnector"
  local app="$ROOT/openconnector" marker="$ROOT/data/openconnector_revision" source="$TMP/openconnector" healthy=0
  if [[ -f "$app/package.json" && -f "$app/src/server/index.ts" && -d "$app/node_modules" ]] \
      && [[ "$(cat "$marker" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]]; then
    if (cd "$app" && node scripts/ensure-generated.ts >/dev/null 2>>"$LOG"); then healthy=1; fi
  fi
  if (( healthy == 0 )); then
    progress 48 "Memperbaiki paket Plugin"
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
}

install_openconnector_launcher() {
  progress 68 "Memasang launcher Plugin"
  if command -v furina-openconnector >/dev/null 2>&1; then furina-openconnector stop >/dev/null 2>&1 || true; fi
  cat > "$PREFIX/bin/furina-openconnector" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
APP="$ROOT/openconnector"
PID="$ROOT/run/openconnector.pid"
LOG="$ROOT/logs/openconnector.log"
LOCK="$ROOT/run/openconnector-repair.lock"
URL="http://127.0.0.1:3000/v1/health"
healthy() { curl -fsS --max-time 3 "$URL" >/dev/null 2>&1; }
running_pid() { [[ -f "$PID" ]] || return 1; local v; v="$(cat "$PID" 2>/dev/null || true)"; [[ "$v" =~ ^[0-9]+$ ]] && kill -0 "$v" >/dev/null 2>&1; }
kill_orphans() {
  local p pid cwd cmd
  for p in /proc/[0-9]*; do
    pid="${p##*/}"; [[ "$pid" == "$$" ]] && continue
    cwd="$(readlink "$p/cwd" 2>/dev/null || true)"
    [[ "$cwd" == "$APP" ]] || continue
    cmd="$(tr '\0' ' ' < "$p/cmdline" 2>/dev/null || true)"
    if [[ "$cmd" == *"src/server/index.ts"* ]]; then kill "$pid" >/dev/null 2>&1 || true; fi
  done
  sleep 0.2
}
stop_runtime() {
  if running_pid; then
    kill "$(cat "$PID")" >/dev/null 2>&1 || true
    for _ in $(seq 1 25); do running_pid || break; sleep 0.1; done
  fi
  rm -f "$PID"
  kill_orphans
}
start_once() {
  healthy && return 0
  stop_runtime
  test -f "$APP/src/server/index.ts" || { echo "Runtime Plugin belum terpasang." >&2; return 3; }
  test -s "$ROOT/data/openconnector-encryption.key" || { echo "Kunci Plugin belum tersedia." >&2; return 3; }
  mkdir -p "$ROOT/run" "$ROOT/logs" "$ROOT/data/openconnector"
  : > "$LOG"
  local key; key="$(cat "$ROOT/data/openconnector-encryption.key")"
  (
    cd "$APP"
    exec env NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000 \
      OOMOL_CONNECT_ORIGIN="http://127.0.0.1:3000" \
      OOMOL_CONNECT_DATA_DIR="$ROOT/data/openconnector" \
      OOMOL_CONNECT_ENCRYPTION_KEY="$key" \
      node "$APP/src/server/index.ts"
  ) >>"$LOG" 2>&1 &
  echo "$!" > "$PID"
  for _ in $(seq 1 180); do
    healthy && return 0
    if ! running_pid; then
      rm -f "$PID"
      return 4
    fi
    sleep 0.25
  done
  stop_runtime
  return 4
}
repair_deps() {
  mkdir -p "$ROOT/run"
  if ! mkdir "$LOCK" 2>/dev/null; then
    for _ in $(seq 1 120); do [[ ! -d "$LOCK" ]] && return 0; sleep 0.25; done
    rm -rf "$LOCK"
    mkdir "$LOCK"
  fi
  trap 'rm -rf "$LOCK"' RETURN
  echo "Memperbaiki dependency Plugin…" >>"$LOG"
  (cd "$APP" && npm install --omit=dev --workspaces=false --no-audit --no-fund) >>"$LOG" 2>&1
  (cd "$APP" && node scripts/ensure-generated.ts) >>"$LOG" 2>&1
  rm -rf "$LOCK"
  trap - RETURN
}
start_with_repair() {
  if start_once; then return 0; fi
  echo "Startup Plugin gagal; menjalankan self-repair sekali." >>"$LOG"
  repair_deps || true
  if start_once; then return 0; fi
  echo "Plugin masih gagal setelah self-repair." >>"$LOG"
  tail -n 30 "$LOG" >&2 2>/dev/null || true
  return 4
}
case "${1:-start}" in
  start) start_with_repair ;;
  repair) stop_runtime; repair_deps; start_once ;;
  stop) stop_runtime ;;
  restart) stop_runtime; start_with_repair ;;
  status) healthy && { echo ready; exit 0; }; echo offline; exit 1 ;;
  logs) tail -n 100 "$LOG" 2>/dev/null || true ;;
  *) echo "usage: furina-openconnector {start|repair|stop|restart|status|logs}" >&2; exit 2 ;;
esac
SH
  chmod 755 "$PREFIX/bin/furina-openconnector"
}

start_plugin() {
  progress 78 "Menyalakan Plugin"
  if furina-openconnector start >>"$LOG" 2>&1; then return 0; fi
  printf '%s\n' "OpenConnector gagal sehat setelah self-repair." >>"$LOG"
  tail -n 40 "$PLUGIN_LOG" >>"$LOG" 2>/dev/null || true
  return 4
}

# Fast path is valid only when the Plugin runtime is healthy too. The previous
# updater considered Core/runtime current even while OpenConnector was broken.
CURRENT="$(core_version 2>/dev/null || true)"
CURRENT_REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$CURRENT_REVISION" == "$DEPENDENCY_REVISION" ]] \
    && command -v furina-openconnector >/dev/null 2>&1 \
    && furina-openconnector status >/dev/null 2>&1; then
  progress 100 "Core dan Plugin sudah terbaru"
  printf '✓ FurinaHub Core %s · Plugin siap.\n' "$VERSION"
  exit 0
fi

ensure_dependencies
ensure_rc47_base
apply_rc48
install_openconnector_runtime
install_openconnector_launcher
if start_plugin; then
  printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
  progress 100 "Core RC48 dan Plugin siap"
  printf '✓ FurinaHub Core %s aktif · OpenConnector siap di http://127.0.0.1:3000\n' "$VERSION"
else
  # Do not stamp the revision on failure; the next `furina update` must retry.
  progress 100 "Core RC48 aktif; Plugin perlu diperbaiki"
  printf 'Core aktif, tetapi Plugin gagal start. Jalankan `furina-openconnector logs` untuk detail.\n' >&2
  exit 4
fi
printf '  Log: %s\n' "$LOG"
