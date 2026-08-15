#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc46"
HUB_VERSION="1.0.0-rc29"
DEPENDENCY_REVISION="2026.08.15-r10"
OPENCONNECTOR_COMMIT="d478400141c33bb5ddf823e09b293e9d7154da97"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PINNED_RC43="44d215a38b336c903d06f04be01f30e60143ba35"
PINNED_RC44="783e443f2bae6cd201c9a08a670caffffc6082ac"
PINNED_RC45="0a321668549beeb7271b01e1c42ccc27124c3467"
RC43_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC43/experiments/furina-agent-final"
RC44_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC44/experiments/furina-agent-final"
RC45_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC45/experiments/furina-agent-final"
RC43_BODY_URL="$RC43_BASE/overrides/rc43/install-body.sh"
RC43_BODY_BLOB="dcaeee6a1ad8588f76c37138b180b472b8720178"
RC44_APPLY_URL="$RC44_BASE/overrides/rc44/apply.py"
RC44_APPLY_BLOB="1c81b788e0581f363cc166b576feee68ec8b5798"
RC44_AUDIT_URL="$RC44_BASE/overrides/rc44/audit-extra.py"
RC44_AUDIT_BLOB="cec2f8d52454ebc8671ce7596f4140a1dff0d4cd"
RC45_APPLY_URL="$RC45_BASE/overrides/rc45/apply.py"
RC45_APPLY_BLOB="b85cacc58d24889e8f600c12f8fc64d3930f27f3"
RC46_APPLY_URL="$BASE/overrides/rc46/apply.py"
RC46_APPLY_BLOB="6e772b638424286140f717623e3eef0e829fbe49"
RELEASE_BASE="https://github.com/WynnDev-rill/furina/releases/download/furinahub-v1.0.0-rc29"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
mkdir -p "$ROOT"/{cache,logs,run,data,models}
LOG="$ROOT/logs/update-rc46-furinahub.log"
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

fail_tail() {
  local rc=$?
  printf 'Updater RC46 berhenti (kode %s).\n' "$rc" >&2
  tail -n 18 "$LOG" >&2 2>/dev/null || true
  if [[ -s "$PLUGIN_LOG" ]]; then
    printf '%s\n' '--- Plugin log ---' >&2
    tail -n 18 "$PLUGIN_LOG" >&2 2>/dev/null || true
  fi
  exit "$rc"
}
trap fail_tail ERR

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
  progress 4 "Merekonstruksi fondasi Core"
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
for old,new in (
    ('run_quiet "Menyiapkan runtime Plugin" 18 install_openconnector','mark 18 "Runtime Plugin ditangani RC46"'),
    ('run_quiet "Menyalakan layanan Plugin (dapat memerlukan 45 detik)" 96 start_openconnector','mark 96 "Startup Plugin ditangani RC46"'),
):
    if old not in text:
        raise SystemExit('RC43 Plugin marker berubah')
    text=text.replace(old,new,1)
old_apk='''APK_BEFORE="$(cat "$ROOT/data/furinahub_apk_revision" 2>/dev/null || true)"
run_quiet "Memeriksa / menyiapkan APK FurinaHub RC27" 98 download_hub_apk
APK_AFTER="$(cat "$ROOT/data/furinahub_apk_revision" 2>/dev/null || true)"
if [[ "$APK_BEFORE" != "$APK_AFTER" ]]; then
  open_hub_apk
fi
mark 100 "FurinaHub siap"'''
if old_apk not in text:
    raise SystemExit('RC43 APK marker berubah')
text=text.replace(old_apk,'mark 100 "APK ditangani RC46"',1)
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
  progress 28 "Menerapkan fondasi Core RC44"
  fetch "$RC44_APPLY_URL" "$TMP/apply-rc44.py"; verify_blob "$TMP/apply-rc44.py" "$RC44_APPLY_BLOB"
  fetch "$RC44_AUDIT_URL" "$TMP/audit-rc44.py"; verify_blob "$TMP/audit-rc44.py" "$RC44_AUDIT_BLOB"
  rm -rf "$TMP/stage44"; mkdir -p "$TMP/stage44"; cp -R "$ROOT/core" "$TMP/stage44/core"
  python "$TMP/apply-rc44.py" "$TMP/stage44" >>"$LOG" 2>&1
  python "$TMP/audit-rc44.py" "$TMP/stage44" >>"$LOG" 2>&1
  FURINA_HOME="$TMP/test44" PYTHONPATH="$TMP/stage44/core" python -m compileall -q "$TMP/stage44/core/furina_agent"
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"; mv "$ROOT/core" "$ROOT/core.prev"; mv "$TMP/stage44/core" "$ROOT/core"
}

apply_overlay() {
  local from="$1" to="$2" url="$3" blob="$4" label="$5" file="$TMP/apply-$to.py" stage="$TMP/stage-$to"
  progress "$label" "Menerapkan Core $to"
  fetch "$url" "$file"; verify_blob "$file" "$blob"
  rm -rf "$stage"; mkdir -p "$stage"; cp -R "$ROOT/core" "$stage/core"
  python "$file" "$stage" >>"$LOG" 2>&1
  FURINA_HOME="$TMP/test-$to" PYTHONPATH="$stage/core" python -m compileall -q "$stage/core/furina_agent"
  grep -q "VERSION = \"1.0.0-$to\"" "$stage/core/furina_agent/version.py"
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"; mv "$ROOT/core" "$ROOT/core.prev"; mv "$stage/core" "$ROOT/core"
}

ensure_runtime_dependencies() {
  progress 58 "Memeriksa dependency Plugin"
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
  node --experimental-transform-types -e 'process.exit(0)' >/dev/null 2>&1 || { echo "Node.js tidak mendukung transform TypeScript yang diperlukan Plugin." >&2; return 1; }
}

install_openconnector_runtime() {
  progress 64 "Memeriksa runtime Plugin"
  local app="$ROOT/openconnector" marker="$ROOT/data/openconnector_revision" source="$TMP/openconnector" healthy=0
  if [[ -f "$app/package.json" && -f "$app/src/server/index.ts" && -d "$app/node_modules" ]] \
      && [[ "$(cat "$marker" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]]; then
    if (cd "$app" && node --experimental-transform-types scripts/ensure-generated.ts >/dev/null 2>>"$LOG"); then healthy=1; fi
  fi
  if (( healthy == 0 )); then
    rm -rf "$source"
    git init -q "$source"
    git -C "$source" remote add origin https://github.com/oomol-lab/open-connector.git
    git -C "$source" fetch -q --depth 1 origin "$OPENCONNECTOR_COMMIT"
    git -C "$source" checkout -q --detach FETCH_HEAD
    (cd "$source" && npm install --omit=dev --workspaces=false --no-audit --no-fund) >>"$LOG" 2>&1
    (cd "$source" && node --experimental-transform-types scripts/ensure-generated.ts) >>"$LOG" 2>&1
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
  progress 72 "Memasang launcher Plugin"
  if command -v furina-openconnector >/dev/null 2>&1; then furina-openconnector stop >/dev/null 2>&1 || true; fi
  cat > "$PREFIX/bin/furina-openconnector" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
APP="$ROOT/openconnector"
PID="$ROOT/run/openconnector.pid"
LOG="$ROOT/logs/openconnector.log"
URL="http://127.0.0.1:3000/v1/actions"
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
  sleep 0.25
}
stop_runtime() {
  if running_pid; then kill "$(cat "$PID")" >/dev/null 2>&1 || true; for _ in $(seq 1 25); do running_pid || break; sleep 0.1; done; fi
  rm -f "$PID"
  kill_orphans
}
start_runtime() {
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
      node --experimental-transform-types "$APP/src/server/index.ts"
  ) >>"$LOG" 2>&1 &
  echo "$!" > "$PID"
  for _ in $(seq 1 180); do
    healthy && return 0
    if ! running_pid; then rm -f "$PID"; echo "Runtime Plugin berhenti saat startup." >&2; tail -n 24 "$LOG" >&2 || true; return 4; fi
    sleep 0.25
  done
  echo "Runtime Plugin belum siap setelah 45 detik." >&2
  tail -n 24 "$LOG" >&2 || true
  stop_runtime
  return 4
}
case "${1:-start}" in
  start) start_runtime ;;
  stop) stop_runtime ;;
  restart) stop_runtime; start_runtime ;;
  status) healthy && { echo ready; exit 0; }; echo offline; exit 1 ;;
  logs) tail -n 80 "$LOG" 2>/dev/null || true ;;
  *) echo "usage: furina-openconnector {start|stop|restart|status|logs}" >&2; exit 2 ;;
esac
SH
  chmod 755 "$PREFIX/bin/furina-openconnector"
}

start_openconnector_with_repair() {
  progress 82 "Menyalakan layanan Plugin"
  if furina-openconnector start >>"$LOG" 2>&1; then return 0; fi
  printf '%s\n' "Startup Plugin pertama gagal; memperbaiki dependency sekali." >>"$LOG"
  (cd "$ROOT/openconnector" && npm install --omit=dev --workspaces=false --no-audit --no-fund) >>"$LOG" 2>&1 || true
  (cd "$ROOT/openconnector" && node --experimental-transform-types scripts/ensure-generated.ts) >>"$LOG" 2>&1 || true
  if furina-openconnector restart >>"$LOG" 2>&1; then return 0; fi
  printf '%s\n' "Plugin masih gagal setelah repair." >>"$LOG"
  tail -n 30 "$PLUGIN_LOG" >>"$LOG" 2>/dev/null || true
  return 4
}

ensure_rc29_apk_file() {
  progress 94 "Memeriksa APK FurinaHub RC29"
  local marker="$ROOT/data/furinahub_apk_revision" out="$HOME/FurinaHub.apk" before
  before="$(cat "$marker" 2>/dev/null || true)"
  if [[ "$before" == "$HUB_VERSION" && -s "$out" ]]; then return 0; fi
  fetch "$RELEASE_BASE/bridge.json" "$TMP/bridge.json"
  read -r apk_url apk_sha < <(python - "$TMP/bridge.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['package_name']=='com.wynndev.furinaagentbridge'
assert int(m['version_code'])==10029 and m['version']=='1.0.0-rc29'
print(m['apk_url'],m['sha256'])
PY
)
  fetch "$apk_url" "$TMP/FurinaHub.apk"
  echo "$apk_sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null
  cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"; printf '%s\n' "$HUB_VERSION" > "$marker"
  if [[ "$before" != "$HUB_VERSION" ]] && command -v termux-open >/dev/null 2>&1; then
    termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1 || true
  fi
}

CURRENT="$(core_version 2>/dev/null || true)"
if [[ "$CURRENT" != "1.0.0-rc43" && "$CURRENT" != "1.0.0-rc44" && "$CURRENT" != "1.0.0-rc45" && "$CURRENT" != "1.0.0-rc46" ]]; then
  prepare_rc43_foundation "$@"; CURRENT="1.0.0-rc43"
fi
if [[ "$CURRENT" == "1.0.0-rc43" ]]; then apply_rc44_foundation; CURRENT="1.0.0-rc44"; fi
if [[ "$CURRENT" == "1.0.0-rc44" ]]; then apply_overlay rc44 rc45 "$RC45_APPLY_URL" "$RC45_APPLY_BLOB" 40; CURRENT="1.0.0-rc45"; fi
if [[ "$CURRENT" == "1.0.0-rc45" ]]; then apply_overlay rc45 rc46 "$RC46_APPLY_URL" "$RC46_APPLY_BLOB" 50; CURRENT="1.0.0-rc46"; fi
test "$CURRENT" = "1.0.0-rc46"

# Core is upgraded first. Plugin failure must never strand Core on an older version again.
ensure_runtime_dependencies
install_openconnector_runtime
install_openconnector_launcher
PLUGIN_OK=1
if ! start_openconnector_with_repair; then PLUGIN_OK=0; fi
ensure_rc29_apk_file
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"

if (( PLUGIN_OK == 1 )); then
  progress 100 "Core, Plugin, dan APK siap"
  printf '\n✓ FurinaHub Core RC46 aktif.\n  Plugin: siap di http://127.0.0.1:3000\n  APK: FurinaHub RC29.\n'
else
  progress 100 "Core & APK siap; Plugin perlu perhatian"
  printf '\n✓ FurinaHub Core RC46 aktif. Plugin belum berhasil start, tetapi Core tidak dibatalkan.\n' >&2
  tail -n 24 "$PLUGIN_LOG" >&2 2>/dev/null || true
fi
printf '  Log: %s\n' "$LOG"
