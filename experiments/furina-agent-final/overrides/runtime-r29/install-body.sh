#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc59"
DEPENDENCY_REVISION="2026.08.18-r29"
TYPESCRIPT_VERSION="5.9.3"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
R28_PATH="overrides/runtime-r28/install-body.sh"
R28_BLOB="3842248101e18012e257b757d16eeeaa6d99884c"
APPLY_PATH="overrides/rc59/apply.py"
APPLY_BLOB="2be10d3d060ba7d09e12dddde172a337d943d996"
BRIDGE_PATH="overrides/rc59/upstream_bridge.py"
BRIDGE_BLOB="3cf0f0e516231e729bb789a0d13481426030de6f"

TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r29-furinahub.log"
TSROOT="$ROOT/upstream-node"
LOCKDIR="$ROOT/run/update-r29.lock"
UI_STARTED=0
FOUNDATION_PID=""
LOCK_OWNED=0

# FurinaHub launches the updater through a pipe, not a terminal. Default that
# case to the machine protocol even if an older bridge forgot to set the env.
if [[ ! -t 1 && -z "${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then
  export FURINAHUB_MACHINE_PROGRESS=1
fi

cleanup(){
  if [[ -n "$FOUNDATION_PID" ]] && kill -0 "$FOUNDATION_PID" 2>/dev/null; then
    kill "$FOUNDATION_PID" 2>/dev/null || true
    wait "$FOUNDATION_PID" 2>/dev/null || true
  fi
  if [[ "$LOCK_OWNED" == "1" && -d "$LOCKDIR" ]]; then
    local owner=""
    owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"
    [[ "$owner" == "$$" ]] && rm -rf "$LOCKDIR"
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

is_tty(){ [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" != "1" && -t 1 && "${TERM:-dumb}" != "dumb" ]]; }
ui_header(){
  [[ "$UI_STARTED" == "1" ]] && return 0
  UI_STARTED=1
  if is_tty; then
    printf '\n\033[38;5;45mFURINA\033[0m \033[38;5;213m// SYSTEM UPDATE\033[0m\n'
    printf '\033[38;5;244mCore %s  ·  runtime r29\033[0m\n\n' "$VERSION"
  fi
  return 0
}
bar(){
  local p="$1" width=18 fill empty i out=""
  fill=$(( p * width / 100 )); empty=$(( width - fill ))
  for ((i=0;i<fill;i++)); do out+="█"; done
  for ((i=0;i<empty;i++)); do out+="·"; done
  printf '%s' "$out"
}
progress(){
  local p="$1"; shift
  if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then
    printf 'PROGRESS %d %s\n' "$p" "$*"
  elif is_tty; then
    ui_header
    printf '\r\033[2K\033[38;5;45m%s\033[0m \033[38;5;250m%3d%%\033[0m  %s' "$(bar "$p")" "$p" "$*"
    if [[ "$p" -ge 100 ]]; then printf '\n'; fi
  else
    printf '[%3d%%] Sedang berjalan… %s\n' "$p" "$*"
  fi
  return 0
}
fail(){
  local code=$?
  trap - ERR
  if is_tty; then printf '\n'; fi
  printf '✗ Update Furina gagal (kode %d).\n' "$code" >&2
  if [[ -r "$LOG" && -s "$LOG" ]]; then
    printf '%s\n' '── detail terakhir ──' >&2
    tail -n 30 "$LOG" >&2 || true
    printf '%s\n' '────────────────────' >&2
  fi
  printf 'Log lengkap: tail -n 80 %q\n' "$LOG" >&2
  exit "$code"
}
trap fail ERR

fetch_url(){
  local u="$1" o="$2" api="${3:-0}" code
  rm -f "$o"
  local a=(-L --silent --show-error --connect-timeout 12 --max-time 150
           --retry 3 --retry-delay 2 --retry-all-errors
           -o "$o" -w '%{http_code}'
           -H 'User-Agent: Furina-Core-Updater/14'
           -H 'Cache-Control: no-cache')
  [[ "$api" == "1" ]] && a+=(-H 'Accept: application/vnd.github.raw+json')
  code="$(curl "${a[@]}" "$u" 2>/dev/null || true)"
  [[ "$code" == "200" && -s "$o" ]]
}
fetch_rel(){
  local r="$1" o="$2" asset=""
  case "$r" in
    overrides/runtime-r28/install-body.sh) asset="furina-runtime-r28.sh" ;;
    overrides/rc59/apply.py) asset="core-rc59-apply.py" ;;
    overrides/rc59/upstream_bridge.py) asset="core-rc59-upstream-bridge.py" ;;
  esac
  fetch_url "$API_BASE/$r?ref=experiment/furina-agent-termux" "$o" 1 ||
  fetch_url "$RAW_BASE/$r" "$o" ||
  { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$o"; } ||
  fetch_url "$WEB_BASE/$r" "$o"
}
verify(){
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
d=pathlib.Path(sys.argv[1]).read_bytes()
a=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if a!=sys.argv[2]:
    raise SystemExit(f"Integritas file berubah: {a} != {sys.argv[2]}")
PY
}
core_version(){
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try:t=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',t)
print(m.group(1) if m else 'unknown')
PY
}

acquire_update_lock(){
  mkdir -p "$ROOT/run"
  local waited=0 owner=""
  while ! mkdir "$LOCKDIR" 2>/dev/null; do
    owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"
    if [[ -z "$owner" || ! "$owner" =~ ^[0-9]+$ || ! -d "/proc/$owner" ]]; then
      rm -rf "$LOCKDIR" 2>/dev/null || true
      continue
    fi
    progress 2 "Update lain sedang berjalan · menunggu"
    sleep 2
    waited=$((waited+2))
    if (( waited >= 600 )); then
      echo "Updater lain masih aktif setelah 10 menit (pid $owner)." >>"$LOG"
      return 75
    fi
  done
  printf '%s\n' "$$" > "$LOCKDIR/pid"
  LOCK_OWNED=1
}

last_child_progress(){
  local file="$1" line=""
  line="$(grep -E '^PROGRESS [0-9]+ ' "$file" 2>/dev/null | tail -n 1 || true)"
  printf '%s' "$line"
}

upstream_pin_count(){
  python - "$ROOT/upstreams/.locks" <<'PY' 2>/dev/null || printf '0'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); n=0
if p.is_dir():
    for f in p.glob('*.json'):
        try:
            if json.loads(f.read_text()).get('complete'): n+=1
        except Exception: pass
print(n)
PY
}

foundation_status_label(){
  local pins="$1" child_msg="$2" r27="$ROOT/logs/update-r27-furinahub.log" line=""
  line="$(grep -E '^UPSTREAM .* (downloading full source|installed|already pinned)' "$r27" 2>/dev/null | tail -n 1 || true)"
  if [[ "$line" =~ ^UPSTREAM[[:space:]]+([^[:space:]]+)[[:space:]]+downloading ]]; then
    printf 'Mengambil source %s · %s/4 siap' "${BASH_REMATCH[1]}" "$pins"
  elif [[ "$line" =~ ^UPSTREAM[[:space:]]+([^[:space:]]+)[[:space:]]+(installed|already) ]]; then
    printf 'Memverifikasi source upstream · %s/4 siap' "$pins"
  elif [[ -n "$child_msg" ]]; then
    printf '%s' "$child_msg"
  else
    printf 'Menyiapkan fondasi companion'
  fi
}

run_foundation_visible(){
  local child_out="$TMP/r28-progress.out" started now elapsed line child_p child_msg mapped pins label status
  : > "$child_out"
  started="$(date +%s)"
  FURINAHUB_MACHINE_PROGRESS=1 bash "$TMP/r28.sh" >"$child_out" 2>>"$LOG" &
  FOUNDATION_PID=$!

  while kill -0 "$FOUNDATION_PID" 2>/dev/null; do
    line="$(last_child_progress "$child_out")"
    child_p=0; child_msg=""
    if [[ "$line" =~ ^PROGRESS[[:space:]]+([0-9]+)[[:space:]]+(.*)$ ]]; then
      child_p="${BASH_REMATCH[1]}"
      child_msg="${BASH_REMATCH[2]}"
    fi
    mapped=$((12 + child_p * 17 / 100))
    (( mapped < 12 )) && mapped=12
    (( mapped > 29 )) && mapped=29

    pins="$(upstream_pin_count)"
    [[ "$pins" =~ ^[0-9]+$ ]] || pins=0
    if (( child_p <= 10 && pins > 0 )); then
      # These increments reflect completed pinned upstream archives, not elapsed time.
      mapped=$((13 + pins))
      (( mapped > 17 )) && mapped=17
    fi
    if [[ "$(core_version 2>/dev/null || true)" == "1.0.0-rc57" && "$mapped" -lt 17 ]]; then
      mapped=17
    fi

    label="$(foundation_status_label "$pins" "$child_msg")"
    now="$(date +%s)"; elapsed=$((now-started))
    progress "$mapped" "$label · ${elapsed}s"

    if (( elapsed >= 1200 )); then
      echo "Foundation RC58 melewati deadline 20 menit; child pid=$FOUNDATION_PID" >>"$LOG"
      kill "$FOUNDATION_PID" 2>/dev/null || true
      sleep 1
      kill -9 "$FOUNDATION_PID" 2>/dev/null || true
      wait "$FOUNDATION_PID" 2>/dev/null || true
      FOUNDATION_PID=""
      return 124
    fi
    sleep 2
  done

  if wait "$FOUNDATION_PID"; then
    status=0
  else
    status=$?
  fi
  FOUNDATION_PID=""
  {
    printf '\n--- runtime-r28 progress ---\n'
    cat "$child_out" 2>/dev/null || true
  } >>"$LOG"
  if (( status != 0 )); then
    {
      printf '\n--- runtime-r28 tail ---\n'
      tail -n 35 "$ROOT/logs/update-r28-furinahub.log" 2>/dev/null || true
      printf '\n--- runtime-r27 tail ---\n'
      tail -n 35 "$ROOT/logs/update-r27-furinahub.log" 2>/dev/null || true
    } >>"$LOG"
    return "$status"
  fi
  progress 29 "Fondasi RC58 siap"
  return 0
}

mkdir -p "$ROOT/logs" "$ROOT/data"
: >> "$LOG"
acquire_update_lock
progress 3 "Memeriksa instalasi"

CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then
  progress 100 "Sudah versi terbaru"
  printf '✓ Furina Core %s · runtime r29 aktif.\n' "$VERSION"
  exit 0
fi

if [[ "$CURRENT" != "1.0.0-rc58" && "$CURRENT" != "$VERSION" ]]; then
  progress 12 "Menyiapkan fondasi RC58"
  fetch_rel "$R28_PATH" "$TMP/r28.sh"; verify "$TMP/r28.sh" "$R28_BLOB"
  run_foundation_visible
fi
test "$(core_version)" = "1.0.0-rc58" || [[ "$(core_version)" == "$VERSION" ]]

progress 30 "Mengunci dependency runtime"
command -v node >/dev/null 2>&1 || pkg install -y nodejs >>"$LOG" 2>&1
command -v npm >/dev/null 2>&1 || { echo "npm tidak tersedia setelah instalasi Node.js." >&2; exit 1; }
if ! node - "$TSROOT" "$TYPESCRIPT_VERSION" <<'JS' >/dev/null 2>&1
const path=require('path');
const root=process.argv[2], expected=process.argv[3];
try {
  const ts=require(path.join(root,'node_modules','typescript'));
  process.exit(ts.version===expected ? 0 : 1);
} catch (_) { process.exit(1); }
JS
then
  mkdir -p "$TSROOT"
  npm install --prefix "$TSROOT" --no-audit --no-fund --omit=optional "typescript@$TYPESCRIPT_VERSION" >>"$LOG" 2>&1
fi
node - "$TSROOT" "$TYPESCRIPT_VERSION" <<'JS'
const path=require('path');
const ts=require(path.join(process.argv[2],'node_modules','typescript'));
if(ts.version!==process.argv[3]) throw new Error(`TypeScript ${ts.version} != ${process.argv[3]}`);
JS

progress 52 "Mengambil perbaikan sistem"
fetch_rel "$APPLY_PATH" "$TMP/apply.py"; verify "$TMP/apply.py" "$APPLY_BLOB"
fetch_rel "$BRIDGE_PATH" "$TMP/upstream_bridge.py"; verify "$TMP/upstream_bridge.py" "$BRIDGE_BLOB"
python -m py_compile "$TMP/apply.py" "$TMP/upstream_bridge.py"

progress 72 "Menerapkan perbaikan atomik"
python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1

progress 90 "Menjalankan pemeriksaan regresi"
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"
python - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); core=root/'core/furina_agent'
chat=(core/'chat.py').read_text(); bridge=(core/'upstream_bridge.py').read_text()
assert 'upstream_context = self.upstream_bridge.context(user_text)' in chat
assert 'if upstream_context:' in chat
assert 'self._background_queue.put((user_text, answer, turn))' in chat
assert 'def _background_worker_loop(self)' in chat
assert '_background_lock' not in chat
assert '_turn_queue.put' in bridge and '_turn_worker_loop' in bridge
assert 'worker deadline exceeded' in bridge
assert 'acquire(blocking=False)' not in bridge
assert '(belum ada upstream companion memory' not in bridge
assert not (core/'upstream_runtime/utsuwa_worker.mjs').exists()
print('FURINA_RC59_RUNTIME_REGRESSION_OK')
PY

progress 97 "Menyimpan revisi runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true

progress 100 "Selesai"
printf '✓ Furina Core %s · bug-sweep runtime r29 aktif.\n' "$VERSION"
