#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc21"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
MANIFEST_URL="$BASE/manifest.json"
BASE_INSTALL_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/90ffa178c678441a666cd82f87f08b1755552fb1/experiments/furina-agent-final/install.sh"
BASE_INSTALL_BLOB="29f11a7c5d4452ca6c9e69f413118329e5958765"
RC19_URL="$BASE/overrides/apply-ui-performance-rc19.py"
RC19_BLOB="8e2e4f7248057c1cf8888fd15a990736767ed1fa"
RC20_URL="$BASE/overrides/apply-reactive-core-rc20.py"
RC20_BLOB="39e2a55579dd2ec90095c27a7498b6c088c7dbed"
RC21_URL="$BASE/overrides/apply-reactive-core-rc21.py"
RC21_BLOB="33f75d16d1734831a28e4daad987d94caabd59ef"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc21.log"
: > "$LOG"

DISPLAY_NAME="Furina"
if [[ -f "$ROOT/config.json" ]] && command -v python >/dev/null 2>&1; then
  DISPLAY_NAME="$(python - "$ROOT/config.json" <<'PY' 2>/dev/null || true
import json,sys
try:
    d=json.load(open(sys.argv[1],encoding='utf-8'))
    print(str(d.get('persona_name') or 'Furina').strip()[:48] or 'Furina')
except Exception:
    print('Furina')
PY
)"
fi

PROGRESS=0
ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;36m%s\033[0m \033[1mBy Wynn\033[0m\n' "$DISPLAY_NAME"
  printf '\033[2mUpdate Agent RC21 · memory dan model dipertahankan\033[0m\n\n'
}
ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=22 filled empty bar="" i
  (( pct < 0 )) && pct=0; (( pct > 100 )) && pct=100
  filled=$(( pct * width / 100 )); empty=$(( width - filled ))
  for ((i=0;i<filled;i++)); do bar+="█"; done
  for ((i=0;i<empty;i++)); do bar+="░"; done
  printf '\r\033[K\033[35m%s\033[0m \033[2m[%s]\033[0m \033[1m%3d%%\033[0m %s' "$glyph" "$bar" "$pct" "$label"
}
mark() { PROGRESS="$1"; ui_progress "$1" "$2" "✓"; printf '\n'; }
run_quiet() {
  local label="$1" target="$2"; shift 2
  local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0 rc next="$PROGRESS"
  ui_progress "$next" "$label" "${frames:0:1}"
  "$@" >>"$LOG" 2>&1 & local pid=$!
  while kill -0 "$pid" >/dev/null 2>&1; do
    (( next < target - 1 )) && next=$((next+1))
    i=$(((i+1)%10)); ui_progress "$next" "$label" "${frames:$i:1}"; sleep 0.18
  done
  set +e; wait "$pid"; rc=$?; set -e
  if (( rc != 0 )); then
    printf '\r\033[K\033[31m×\033[0m %s\n' "$label"
    tail -n 20 "$LOG" >&2 || true
    exit "$rc"
  fi
  mark "$target" "$label"
}
verify_git_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
p,e=sys.argv[1:]; d=pathlib.Path(p).read_bytes()
a=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if a!=e: raise SystemExit(f"Integritas update berubah: {p} {a}")
PY
}
read_core_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read(); m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',s)
print(m.group(1) if m else 'unknown')
PY
}
fetch_transform() {
  local url="$1" blob="$2" out="$3"
  curl -fsSL --retry 3 "$url" -o "$out"
  verify_git_blob "$out" "$blob"
}

ui_title
mark 5 "Memeriksa instalasi Furina"

if [[ ! -f "$ROOT/core/furina_agent/version.py" ]]; then
  fetch_transform "$BASE_INSTALL_URL" "$BASE_INSTALL_BLOB" "$TMP/install-base.sh"
  run_quiet "Menyiapkan fondasi Furina" 26 bash "$TMP/install-base.sh" "$@"
fi

CURRENT="$(read_core_version)"
mark 31 "Core saat ini: $CURRENT"

curl -fsSL --retry 3 "$MANIFEST_URL" -o "$TMP/manifest.json"
EXPECTED="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["version"])')"
[[ "$EXPECTED" == "1.0.0-rc21" ]] || { echo "Manifest belum menunjuk RC21: $EXPECTED" >&2; exit 1; }
mark 37 "Manifest RC21 terverifikasi"

mkdir -p "$TMP/stage"
cp -R "$ROOT/core" "$TMP/stage/core"
mark 43 "Membuat salinan aman Core"

apply_core_updates() {
  local current="$1"
  if [[ "$current" == "1.0.0-rc18" ]]; then
    fetch_transform "$RC19_URL" "$RC19_BLOB" "$TMP/rc19.py"
    python "$TMP/rc19.py" "$TMP/stage"
    current="1.0.0-rc19"
  fi
  if [[ "$current" == "1.0.0-rc19" ]]; then
    fetch_transform "$RC20_URL" "$RC20_BLOB" "$TMP/rc20.py"
    python "$TMP/rc20.py" "$TMP/stage"
    current="1.0.0-rc20"
  fi
  if [[ "$current" == "1.0.0-rc20" ]]; then
    fetch_transform "$RC21_URL" "$RC21_BLOB" "$TMP/rc21.py"
    python "$TMP/rc21.py" "$TMP/stage"
    current="1.0.0-rc21"
  fi
  [[ "$current" == "1.0.0-rc21" ]] || { echo "Versi Core tidak dapat dimigrasikan otomatis: $current" >&2; return 1; }
}
run_quiet "Menerapkan reactive runtime RC21" 66 apply_core_updates "$CURRENT"

validate_core() {
  PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.agent import AndroidAgent
assert VERSION == '1.0.0-rc21', VERSION
assert hasattr(AndroidAgent, '_compile_ui_sequence')
assert hasattr(AndroidAgent, '_try_ui_sequence')
text=open(__import__('furina_agent.chat_surface').chat_surface.__file__,encoding='utf-8').read()
assert '#080f0d' in text and 'Furina[/]' in text
PY
}
run_quiet "Memvalidasi Core dan UI Agent" 78 validate_core

if [[ "$CURRENT" != "1.0.0-rc21" ]]; then
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage/core" "$ROOT/core"
fi
mark 84 "Core RC21 aktif · memory/model tetap"

BRIDGE_NEEDS_INSTALL=0
BRIDGE_STATUS_UNKNOWN=0
prepare_bridge() {
  local installed expected release apk_url apk_sha
  installed="$(curl -fsS --max-time 2 http://127.0.0.1:8765/health 2>/dev/null | python -c 'import json,sys;print(json.load(sys.stdin).get("version",""))' 2>/dev/null || true)"
  expected="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["bridge_version"])')"

  if [[ -z "$installed" ]]; then
    printf '%s' "unknown" > "$TMP/bridge-state"
    return 0
  fi
  if [[ "$installed" == "$expected" ]]; then
    furina connect >/dev/null 2>&1 || true
    printf '%s' "ready" > "$TMP/bridge-state"
    return 0
  fi

  release="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["bridge_release_base"])')"
  curl -fsSL --retry 4 "$release/bridge.json" -o "$TMP/bridge.json"
  apk_url="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["apk_url"])')"
  apk_sha="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["sha256"])')"
  curl -fsSL --retry 4 "$apk_url" -o "$ROOT/cache/Furina-Agent-Bridge-RC12.apk"
  echo "$apk_sha  $ROOT/cache/Furina-Agent-Bridge-RC12.apk" | sha256sum -c - >/dev/null
  printf '%s' "install" > "$TMP/bridge-state"
}
run_quiet "Memeriksa Furina Bridge RC12" 94 prepare_bridge

BRIDGE_STATE="$(cat "$TMP/bridge-state" 2>/dev/null || true)"
if [[ "$BRIDGE_STATE" == "install" ]]; then
  APK_URL="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["apk_url"])')"
  termux-open-url "$APK_URL" >/dev/null 2>&1 || true
  BRIDGE_NEEDS_INSTALL=1
  mark 98 "Update Bridge diperlukan · download dibuka"
elif [[ "$BRIDGE_STATE" == "unknown" ]]; then
  BRIDGE_STATUS_UNKNOWN=1
  mark 98 "Bridge belum dapat diverifikasi · download tidak dibuka"
else
  mark 98 "Bridge sudah sesuai · tidak perlu download"
fi
mark 100 "Update selesai"

printf '\n\033[32m✓\033[0m Furina Agent RC21 siap.\n'
if (( BRIDGE_NEEDS_INSTALL )); then
  printf '\033[33m!\033[0m Bridge yang terpasang memang berbeda dari versi yang dibutuhkan. URL APK resmi sudah dibuka.\n'
elif (( BRIDGE_STATUS_UNKNOWN )); then
  printf '\033[33m!\033[0m Bridge sedang tidak merespons, jadi updater tidak menganggapnya outdated dan tidak membuka download. Buka Furina Bridge sekali lalu jalankan \033[1;36mfurina update\033[0m untuk verifikasi versi.\n'
else
  printf '\033[2mCore RC21 · Bridge sudah sesuai · memory dan model dipertahankan.\033[0m\n'
fi
printf '\n'
