#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc49"
DEPENDENCY_REVISION="2026.08.16-r15"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
RC48_R14_URL="$BASE/overrides/rc48-r14/install-body.sh"
RC48_R14_BLOB="b51620af1dc2b90bfebd7d0c8fcbb470563a1a61"
RC49_APPLY_URL="$BASE/overrides/rc49/apply.py"
RC49_APPLY_BLOB="c16461e87230f8560f7e6093b90a7cc4e8aab909"
RC49_HARDEN_URL="$BASE/overrides/rc49/harden.py"
RC49_HARDEN_BLOB="b8667a60727f0285521981c2543e704d9d41b276"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
umask 077
mkdir -p "$ROOT"/{cache,logs,run,data,models}
LOG="$ROOT/logs/update-rc49-furinahub.log"
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

ensure_rc48_r14() {
  local current revision
  current="$(core_version 2>/dev/null || true)"
  revision="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
  # A partially completed RC49 update must never be downgraded through the legacy chain.
  if [[ "$current" == "$VERSION" ]]; then return 0; fi
  if [[ "$current" == "1.0.0-rc48" && "$revision" == "2026.08.16-r14" ]] \
      && command -v furina-openconnector >/dev/null 2>&1 \
      && furina-openconnector status >/dev/null 2>&1; then
    return 0
  fi
  progress 8 "Menyiapkan fondasi Plugin"
  fetch "$RC48_R14_URL" "$TMP/rc48-r14.sh"
  verify_blob "$TMP/rc48-r14.sh" "$RC48_R14_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/rc48-r14.sh" >>"$LOG" 2>&1
  test "$(core_version)" = "1.0.0-rc48"
}

apply_rc49() {
  progress 36 "Menyederhanakan sistem Plugin"
  fetch "$RC49_APPLY_URL" "$TMP/apply-rc49.py"
  verify_blob "$TMP/apply-rc49.py" "$RC49_APPLY_BLOB"
  fetch "$RC49_HARDEN_URL" "$TMP/harden-rc49.py"
  verify_blob "$TMP/harden-rc49.py" "$RC49_HARDEN_BLOB"
  if [[ "$(core_version 2>/dev/null || true)" != "$VERSION" ]]; then
    python "$TMP/apply-rc49.py" "$ROOT" >>"$LOG" 2>&1
  fi
  python "$TMP/harden-rc49.py" "$ROOT" >>"$LOG" 2>&1
  python -m compileall -q "$ROOT/core/furina_agent"
  test "$(core_version)" = "$VERSION"
}

ensure_connector_tokens() {
  progress 52 "Mengamankan runtime lokal"
  local token_file="$ROOT/data/openconnector.token"
  local encryption_file="$ROOT/data/openconnector-encryption.key"
  if [[ ! -s "$token_file" ]]; then
    python - <<'PY' > "$token_file"
import secrets
print('oct_' + secrets.token_urlsafe(48))
PY
  fi
  if [[ ! -s "$encryption_file" ]]; then
    python - <<'PY' > "$encryption_file"
import secrets
print(secrets.token_urlsafe(48))
PY
  fi
  chmod 600 "$token_file" "$encryption_file"
  test "$(wc -c < "$token_file")" -ge 48
  test "$(wc -c < "$encryption_file")" -ge 48
}

install_secure_launcher() {
  progress 66 "Memasang launcher Plugin aman"
  if command -v furina-openconnector >/dev/null 2>&1; then furina-openconnector stop >/dev/null 2>&1 || true; fi
  cat > "$PREFIX/bin/furina-openconnector" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
umask 077
ROOT="$HOME/.furina-agent"
APP="$ROOT/openconnector"
PID="$ROOT/run/openconnector.pid"
LOG="$ROOT/logs/openconnector.log"
LOCK="$ROOT/run/openconnector-repair.lock"
TOKEN_FILE="$ROOT/data/openconnector.token"
KEY_FILE="$ROOT/data/openconnector-encryption.key"
URL="http://127.0.0.1:3000/v1/health"
read_token() { [[ -s "$TOKEN_FILE" ]] && tr -d '\r\n' < "$TOKEN_FILE"; }
healthy() { local t; t="$(read_token 2>/dev/null || true)"; [[ -n "$t" ]] && curl -fsS --max-time 3 -H "Authorization: Bearer $t" "$URL" >/dev/null 2>&1; }
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
  test -s "$TOKEN_FILE" || { echo "Token runtime Plugin belum tersedia." >&2; return 3; }
  test -s "$KEY_FILE" || { echo "Kunci enkripsi Plugin belum tersedia." >&2; return 3; }
  mkdir -p "$ROOT/run" "$ROOT/logs" "$ROOT/data/openconnector"
  : > "$LOG"
  local token key
  token="$(read_token)"
  key="$(tr -d '\r\n' < "$KEY_FILE")"
  (
    cd "$APP"
    exec env NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000 \
      OOMOL_CONNECT_ORIGIN="http://127.0.0.1:3000" \
      OOMOL_CONNECT_DATA_DIR="$ROOT/data/openconnector" \
      OOMOL_CONNECT_ENCRYPTION_KEY="$key" \
      OOMOL_CONNECT_ADMIN_TOKEN="$token" \
      OOMOL_CONNECT_RUNTIME_TOKEN="$token" \
      OOMOL_CONNECT_BLOCKED_PROXIES="*" \
      node "$APP/src/server/index.ts"
  ) >>"$LOG" 2>&1 &
  echo "$!" > "$PID"
  for _ in $(seq 1 180); do
    healthy && return 0
    if ! running_pid; then rm -f "$PID"; return 4; fi
    sleep 0.25
  done
  stop_runtime
  return 4
}
repair_deps() {
  mkdir -p "$ROOT/run"
  if ! mkdir "$LOCK" 2>/dev/null; then
    for _ in $(seq 1 120); do [[ ! -d "$LOCK" ]] && return 0; sleep 0.25; done
    rm -rf "$LOCK"; mkdir "$LOCK"
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
  bash -n "$PREFIX/bin/furina-openconnector"
}

start_runtime() {
  progress 82 "Menyalakan Plugin"
  furina-openconnector restart >>"$LOG" 2>&1
  furina-openconnector status >>"$LOG" 2>&1
}

CURRENT="$(core_version 2>/dev/null || true)"
CURRENT_REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$CURRENT_REVISION" == "$DEPENDENCY_REVISION" ]] \
    && command -v furina-openconnector >/dev/null 2>&1 \
    && furina-openconnector status >/dev/null 2>&1; then
  progress 100 "Core dan Plugin sudah terbaru"
  printf '✓ FurinaHub Core %s · Plugin aman dan siap.\n' "$VERSION"
  exit 0
fi

ensure_rc48_r14
apply_rc49
ensure_connector_tokens
install_secure_launcher
if start_runtime; then
  printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
  progress 100 "Core RC49 dan Plugin siap"
  printf '✓ FurinaHub Core %s aktif · Plugin lokal siap dan terlindungi token.\n' "$VERSION"
else
  progress 100 "Core RC49 aktif; Plugin perlu diperbaiki"
  printf 'Core aktif, tetapi Plugin gagal start. Jalankan `furina-openconnector logs` untuk detail.\n' >&2
  exit 4
fi
printf '  Log: %s\n' "$LOG"
