#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc35"
HUB_VERSION="1.0.0-rc19"
DEPENDENCY_REVISION="2026.08.14-r1"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PREV_COMMIT="118ced8b64858a2448ecd01d15c098049a1ec32e"
PREV_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PREV_COMMIT/experiments/furina-agent-final"
PREV_INSTALL_URL="$PREV_BASE/install.sh"
PREV_INSTALL_BLOB="dd9773ae9de73acb34f9ae70453d54624018536d"
RC35_URL="$BASE/overrides/rc35"
APPLY_BLOB="42446503423986177fb31a73d879441616059953"
SETTINGS_BLOB="d6bb11623353a3ff26a9000fb4b3a419c1919392"
HUB_BLOB="0d36622263bee864baa4a43477852bac7edc7f5a"
WEB_BLOB="e78482e18887cebaf8c4d2f4ec51c3c246d5b36a"
MAIN_ACTIVITY_BLOB="0999791565430cce8034d75e79bbb8c4beec12d8"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc35-furinahub.log"
: > "$LOG"
PROGRESS=0
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;35mFurinaHub\033[0m  \033[1mBy Wynn\033[0m\n'
  printf '\033[2mCore RC35 · Android RC19 · chat-first companion\033[0m\n\n'
}

ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=18 filled empty bar="" i
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
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
    i=$(((i+1)%10)); ui_progress "$next" "$label" "${frames:$i:1}"; sleep 0.16
  done
  set +e; wait "$pid"; rc=$?; set -e
  if (( rc != 0 )); then
    printf '\r\033[K\033[31m×\033[0m %s\n' "$label"
    printf '\033[2mLog: %s\033[0m\n' "$LOG" >&2
    tail -n 40 "$LOG" >&2 || true
    exit "$rc"
  fi
  mark "$target" "$label"
}

verify_git_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas file berubah: {path} {actual} != {expected}")
PY
}

fetch_blob() {
  local url="$1" expected="$2" out="$3"
  curl -fsSL --retry 3 "$url" -o "$out"
  verify_git_blob "$out" "$expected"
}

core_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try: s=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',s)
print(m.group(1) if m else 'unknown')
PY
}

fetch_manifest() {
  curl -fsSL --retry 3 "$BASE/manifest.json" -o "$TMP/manifest.json"
  python - "$TMP/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m.get('version') == '1.0.0-rc35'
assert m.get('bridge_version') == '1.0.0-rc19'
assert int(m.get('bridge_version_code')) == 10019
assert m.get('dependency_revision') == '2026.08.14-r1'
assert m.get('hub_name') == 'FurinaHub'
assert str(m.get('bridge_release_base','')).startswith('https://github.com/WynnDev-rill/furina/releases/download/')
PY
}

fetch_rc35_bundle() {
  mkdir -p "$TMP/rc35"
  fetch_blob "$RC35_URL/apply.py" "$APPLY_BLOB" "$TMP/rc35/apply.py"
  fetch_blob "$RC35_URL/hub_settings.py" "$SETTINGS_BLOB" "$TMP/rc35/hub_settings.py"
  fetch_blob "$RC35_URL/hub.py" "$HUB_BLOB" "$TMP/rc35/hub.py"
  fetch_blob "$RC35_URL/hub_web.py" "$WEB_BLOB" "$TMP/rc35/hub_web.py"
  fetch_blob "$RC35_URL/MainActivity.java" "$MAIN_ACTIVITY_BLOB" "$TMP/rc35/MainActivity.java"
  # hub_web.py is reviewed/stored as plain HTML and is packaged into a Python
  # string module by apply.py. Compile only actual Python templates here.
  python -m py_compile "$TMP/rc35/apply.py" "$TMP/rc35/hub_settings.py" "$TMP/rc35/hub.py"
}

prepare_rc34() {
  fetch_blob "$PREV_INSTALL_URL" "$PREV_INSTALL_BLOB" "$TMP/install-rc34.sh"
  python - "$TMP/install-rc34.sh" "$PREV_BASE" <<'PY'
import pathlib,sys
path=pathlib.Path(sys.argv[1]); pinned=sys.argv[2]
text=path.read_text(encoding='utf-8')
old='BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"'
new=f'BASE="{pinned}"'
if text.count(old) != 1:
    raise SystemExit('RC34 installer BASE marker berubah')
path.write_text(text.replace(old,new,1),encoding='utf-8')
PY
  bash "$TMP/install-rc34.sh"
  [[ "$(core_version)" == "1.0.0-rc34" ]]
}

reconcile_dependencies() {
  local marker="$ROOT/data/dependency_revision"
  local current=""
  [[ -f "$marker" ]] && current="$(cat "$marker" 2>/dev/null || true)"
  if [[ "$current" == "$DEPENDENCY_REVISION" ]] && command -v python >/dev/null && command -v curl >/dev/null; then
    python - <<'PY' >/dev/null
import rich
PY
    return 0
  fi
  pkg install -y python curl >/dev/null
  if ! python - <<'PY' >/dev/null 2>&1
import rich
PY
  then
    python -m pip install 'rich>=13,<15' >/dev/null
  fi
  printf '%s\n' "$DEPENDENCY_REVISION" > "$marker"
}

enable_termux_integration() {
  mkdir -p "$HOME/.termux"
  local props="$HOME/.termux/termux.properties"
  touch "$props"
  python - "$props" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
lines=[x for x in p.read_text(encoding='utf-8').splitlines() if not x.strip().startswith('allow-external-apps=')]
lines.append('allow-external-apps=true')
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
PY
  command -v termux-reload-settings >/dev/null 2>&1 && termux-reload-settings >/dev/null 2>&1 || true
}

stage_core() {
  rm -rf "$TMP/stage"; mkdir -p "$TMP/stage"
  cp -R "$ROOT/core" "$TMP/stage/core"
}

apply_rc35() {
  python "$TMP/rc35/apply.py" "$TMP/stage" "$TMP/rc35"
}

validate_core() {
  FURINA_HOME="$TMP/home-test" PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  FURINA_HOME="$TMP/home-test" PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.hub_settings import defaults,normalize,skill_allows_action,effective_device_mode,personalization_prompt
from furina_agent.intent_guard import conversation_frame,strong_device_request
assert VERSION == '1.0.0-rc35'
s=defaults()
assert s['base_style']=='adaptive' and 'tsundere' not in s['base_style']
s['agent_skills']['android_navigation']=False
assert not skill_allows_action('open_app',s)
s['device_control_mode']='root'
assert effective_device_mode(s)=='normal'
s['agent_skills']['privileged_controls']=True
assert effective_device_mode(s)=='root'
assert 'tidak pernah memberi izin kontrol perangkat' in personalization_prompt(s)
assert conversation_frame('WhatsApp sekarang sering lambat menurutmu kenapa?')
assert strong_device_request('Bisa buka WhatsApp?')
from furina_agent.hub import HUB_HOST,HUB_PORT
assert HUB_HOST=='127.0.0.1' and HUB_PORT==8787
import furina_agent.hub as hubmod
src=open(hubmod.__file__,encoding='utf-8').read()
assert '/api/update/core' in src and 'dependency_revision' in src
print('FURINAHUB_RC35_CORE_OK')
PY
}

install_launchers() {
  cat > "$PREFIX/bin/furina-hub" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
export FURINA_HOME="$ROOT"
export PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"

if [[ -f "$ROOT/run/furinahub.pid" ]]; then
  old_pid="$(cat "$ROOT/run/furinahub.pid" 2>/dev/null || true)"
  if [[ "$old_pid" =~ ^[0-9]+$ ]]; then
    kill "$old_pid" >/dev/null 2>&1 || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      kill -0 "$old_pid" >/dev/null 2>&1 || break
      sleep 0.1
    done
  fi
  rm -f "$ROOT/run/furinahub.pid"
fi

exec python -m furina_agent.hub "$@"
SH
  chmod 755 "$PREFIX/bin/furina-hub"
}

stop_hub() {
  if [[ -f "$ROOT/run/furinahub.pid" ]]; then
    local pid
    pid="$(cat "$ROOT/run/furinahub.pid" 2>/dev/null || true)"
    [[ "$pid" =~ ^[0-9]+$ ]] && kill "$pid" >/dev/null 2>&1 || true
    rm -f "$ROOT/run/furinahub.pid"
  fi
}

install_stage() {
  # Keep the currently running FurinaHub UI alive while files are swapped.
  # The process keeps its already-imported modules until the app reconnects.
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage/core" "$ROOT/core"
}

download_hub_apk() {
  local release_base apk_url sha out="$HOME/FurinaHub.apk" marker="$ROOT/data/furinahub_apk_revision"
  if [[ -f "$marker" ]] && [[ "$(cat "$marker" 2>/dev/null || true)" == "$HUB_VERSION" ]] && [[ -s "$out" ]]; then
    return 0
  fi
  release_base="$(python - "$TMP/manifest.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8'))['bridge_release_base'])
PY
)"
  curl -fsSL --retry 4 "$release_base/bridge.json" -o "$TMP/bridge.json"
  read -r apk_url sha < <(python - "$TMP/bridge.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['package_name']=='com.wynndev.furinaagentbridge'
assert int(m['version_code'])==10019
assert m['version']=='1.0.0-rc19'
assert str(m['apk_url']).startswith('https://github.com/WynnDev-rill/furina/releases/download/')
assert len(str(m['sha256']))==64
print(m['apk_url'],m['sha256'])
PY
)
  curl -fL --retry 4 "$apk_url" -o "$TMP/FurinaHub.apk"
  echo "$sha  $TMP/FurinaHub.apk" | sha256sum -c -
  cp "$TMP/FurinaHub.apk" "$out"
  chmod 600 "$out"
  printf '%s\n' "$HUB_VERSION" > "$marker"
}

open_hub_apk() {
  local out="$HOME/FurinaHub.apk"
  if command -v termux-open >/dev/null 2>&1; then
    termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1 || true
  fi
}

ui_title
run_quiet "Memeriksa dependency terkelola" 8 reconcile_dependencies
CURRENT="$(core_version 2>/dev/null || true)"
mark 14 "Versi Core saat ini: ${CURRENT:-missing}"
run_quiet "Memeriksa manifest RC35 / FurinaHub RC19" 22 fetch_manifest
run_quiet "Memverifikasi hash paket RC35" 32 fetch_rc35_bundle

if [[ "$CURRENT" != "1.0.0-rc34" && "$CURRENT" != "1.0.0-rc35" ]]; then
  run_quiet "Merekonstruksi fondasi Core hingga RC34" 52 prepare_rc34
  CURRENT="$(core_version)"
elif [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  mark 52 "Core RC34 ditemukan; siap migrasi FurinaHub"
else
  mark 52 "Core RC35 ditemukan; menjalankan health-check penuh"
fi

run_quiet "Membuat salinan aman Core" 59 stage_core
UPGRADED=0
if [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  run_quiet "Menerapkan Core FurinaHub RC35" 70 apply_rc35
  UPGRADED=1
else
  mark 70 "Tidak perlu menulis ulang Core RC35"
fi
run_quiet "Compile + regression chat/personality/skill" 80 validate_core
run_quiet "Menyiapkan integrasi Termux ↔ FurinaHub" 86 enable_termux_integration
run_quiet "Memasang launcher furina-hub" 89 install_launchers

if (( UPGRADED == 1 )); then
  run_quiet "Memasang Core secara atomik" 93 install_stage
else
  mark 93 "Core RC35 sehat; data tidak diubah"
fi

APK_BEFORE="$(cat "$ROOT/data/furinahub_apk_revision" 2>/dev/null || true)"
run_quiet "Memeriksa / menyiapkan APK FurinaHub" 98 download_hub_apk
APK_AFTER="$(cat "$ROOT/data/furinahub_apk_revision" 2>/dev/null || true)"
if [[ "$APK_BEFORE" != "$APK_AFTER" ]]; then
  open_hub_apk
fi
mark 100 "FurinaHub siap"

printf '\n\033[32m✓\033[0m FurinaHub Core RC35 aktif.\n'
printf '  CLI tetap tersedia: \033[1mfurina\033[0m\n'
printf '  GUI server manual:  \033[1mfurina-hub\033[0m\n'
printf '  APK: %s\n' "$HOME/FurinaHub.apk"
printf '  Jika installer Android belum terbuka otomatis, buka file APK tersebut dari Termux/file manager.\n'
printf '\033[2m  Log lengkap: %s\033[0m\n' "$LOG"
