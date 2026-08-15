#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc39"
HUB_VERSION="1.0.0-rc23"
DEPENDENCY_REVISION="2026.08.15-r4"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PREV_COMMIT="118ced8b64858a2448ecd01d15c098049a1ec32e"
PREV_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PREV_COMMIT/experiments/furina-agent-final"
PREV_INSTALL_URL="$PREV_BASE/install.sh"
PREV_INSTALL_BLOB="dd9773ae9de73acb34f9ae70453d54624018536d"
RC35_URL="$BASE/overrides/rc35"
RC36_URL="$BASE/overrides/rc36"
RC37_URL="$BASE/overrides/rc37"
RC38_URL="$BASE/overrides/rc38"
RC39_URL="$BASE/overrides/rc39"
APPLY_BLOB="386f092c94c1d6d0d45e215772e8320dc127271d"
SETTINGS_BLOB="d6bb11623353a3ff26a9000fb4b3a419c1919392"
HUB_BLOB="0d36622263bee864baa4a43477852bac7edc7f5a"
WEB_BLOB="e78482e18887cebaf8c4d2f4ec51c3c246d5b36a"
MAIN_ACTIVITY_BLOB="0999791565430cce8034d75e79bbb8c4beec12d8"
RC36_APPLY_BLOB="23e6cea5e60bbd9f6d0dbcba2f834118ebe9459f"
RC36_SETTINGS_BLOB="08c82b36c9a52c91ee6995625885166b74618a53"
RC36_HUB_BLOB="72f9e38e727378d206d1a969f9b46daf4c6e82c6"
RC37_APPLY_BLOB="43f0d3087b083cefaece6504ea7e8653c93563b6"
RC37_HUB_BLOB="ce0ec08ee2d6b3b4044d94c28f24ea7e3ba1b97b"
RC38_APPLY_BLOB="66780ad6106cacedde11e37154df65737bd7d10b"
RC38_HUB_BLOB="971e401f246fc43882bac1c0215241da458c7714"
RC38_DIRECT_BLOB="7ef20de18a1a2ad858b803d27fd86c1247ce82d6"
RC39_APPLY_BLOB="3e824d8d43db7064357b17596184d1a37ae2135d"
RC39_HUB_BLOB="7ea7218bde2e375f75714d821535aa1e4a99369f"
RC39_DIRECT_BLOB="7ef20de18a1a2ad858b803d27fd86c1247ce82d6"
RC39_MEMORY_BLOB="8b23ebea80f5a4a9f7ea102cf742e0514ac39490"
RC39_COMPANION_BLOB="64c9989d25c401aa568ed96d228698c8a9e5dc46"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc39-furinahub.log"
: > "$LOG"
PROGRESS=0
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;35mFurinaHub\033[0m  \033[1mBy Wynn\033[0m\n'
  printf '\033[2mCore RC39 · Android RC23 · chat, vision, riwayat, dan kontrol perangkat\033[0m\n\n'
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
assert m.get('version') == '1.0.0-rc39'
assert m.get('bridge_version') == '1.0.0-rc23'
assert int(m.get('bridge_version_code')) == 10023
assert m.get('dependency_revision') == '2026.08.15-r4'
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
  python -m py_compile "$TMP/rc35/apply.py" "$TMP/rc35/hub_settings.py" "$TMP/rc35/hub.py"
}

fetch_rc36_bundle() {
  mkdir -p "$TMP/rc36"
  fetch_blob "$RC36_URL/apply.py" "$RC36_APPLY_BLOB" "$TMP/rc36/apply.py"
  fetch_blob "$RC36_URL/hub_settings.py" "$RC36_SETTINGS_BLOB" "$TMP/rc36/hub_settings.py"
  fetch_blob "$RC36_URL/hub.py" "$RC36_HUB_BLOB" "$TMP/rc36/hub.py"
  python -m py_compile "$TMP/rc36/apply.py" "$TMP/rc36/hub_settings.py" "$TMP/rc36/hub.py"
}

fetch_rc37_bundle() {
  mkdir -p "$TMP/rc37"
  fetch_blob "$RC37_URL/apply.py" "$RC37_APPLY_BLOB" "$TMP/rc37/apply.py"
  fetch_blob "$RC37_URL/hub.py" "$RC37_HUB_BLOB" "$TMP/rc37/hub.py"
  python -m py_compile "$TMP/rc37/apply.py" "$TMP/rc37/hub.py"
}

fetch_rc38_bundle() {
  mkdir -p "$TMP/rc38"
  fetch_blob "$RC38_URL/apply.py" "$RC38_APPLY_BLOB" "$TMP/rc38/apply.py"
  fetch_blob "$RC38_URL/hub.py" "$RC38_HUB_BLOB" "$TMP/rc38/hub.py"
  fetch_blob "$RC38_URL/direct_control.py" "$RC38_DIRECT_BLOB" "$TMP/rc38/direct_control.py"
  python -m py_compile "$TMP/rc38/apply.py" "$TMP/rc38/hub.py" "$TMP/rc38/direct_control.py"
}

fetch_rc39_bundle() {
  mkdir -p "$TMP/rc39"
  fetch_blob "$RC39_URL/apply.py" "$RC39_APPLY_BLOB" "$TMP/rc39/apply.py"
  fetch_blob "$RC39_URL/hub.py" "$RC39_HUB_BLOB" "$TMP/rc39/hub.py"
  fetch_blob "$RC39_URL/direct_control.py" "$RC39_DIRECT_BLOB" "$TMP/rc39/direct_control.py"
  fetch_blob "$RC39_URL/memory.py" "$RC39_MEMORY_BLOB" "$TMP/rc39/memory.py"
  fetch_blob "$RC39_URL/companion.py" "$RC39_COMPANION_BLOB" "$TMP/rc39/companion.py"
  python -m py_compile "$TMP/rc39/apply.py" "$TMP/rc39/hub.py" "$TMP/rc39/direct_control.py" "$TMP/rc39/memory.py" "$TMP/rc39/companion.py"
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
  dependency_health() {
    command -v python >/dev/null 2>&1 || return 1
    command -v curl >/dev/null 2>&1 || return 1
    python - <<'PY' >/dev/null 2>&1
import rich
PY
  }
  if dependency_health; then
    printf '%s\n' "$DEPENDENCY_REVISION" > "$marker"
    echo "Dependency python, curl, dan rich sudah sehat; repository tidak disentuh."
    return 0
  fi

  local packages=()
  command -v python >/dev/null 2>&1 || packages+=(python)
  command -v curl >/dev/null 2>&1 || packages+=(curl)
  if (( ${#packages[@]} )); then
    command -v pkg >/dev/null 2>&1 || { echo "pkg Termux tidak ditemukan" >&2; return 1; }
    if ! pkg install -y "${packages[@]}"; then
      echo "Percobaan pertama gagal; menyegarkan indeks repository Termux lalu mencoba sekali lagi." >&2
      pkg update -y
      pkg install -y "${packages[@]}"
    fi
  fi
  if ! python - <<'PY' >/dev/null 2>&1
import rich
PY
  then
    python -m pip install --disable-pip-version-check 'rich>=13,<15'
  fi
  dependency_health || { echo "Dependency tetap tidak sehat setelah perbaikan" >&2; return 1; }
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

apply_rc36() {
  python "$TMP/rc36/apply.py" "$TMP/stage" "$TMP/rc36"
}

apply_rc37() {
  python "$TMP/rc37/apply.py" "$TMP/stage" "$TMP/rc37"
}

apply_rc38() {
  python "$TMP/rc38/apply.py" "$TMP/stage" "$TMP/rc38"
}

apply_rc39() {
  python "$TMP/rc39/apply.py" "$TMP/stage" "$TMP/rc39"
}

validate_core() {
  FURINA_HOME="$TMP/home-test" PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  FURINA_HOME="$TMP/home-test" PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.hub_settings import defaults,normalize,skill_allows_action,effective_device_mode,personalization_prompt
from furina_agent.intent_guard import conversation_frame,strong_device_request
assert VERSION == '1.0.0-rc39'
s=defaults()
assert s['base_style']=='adaptive' and 'tsundere' not in s['base_style']
s['agent_skills']['android_navigation']=False
assert not skill_allows_action('open_app',s)
s['device_control_mode']='root'
assert effective_device_mode(s)=='normal'
s['agent_skills']['privileged_controls']=True
s['device_access']['root']['verified']=True
assert effective_device_mode(s)=='root'
assert 'tidak pernah memberi izin kontrol perangkat' in personalization_prompt(s)
assert conversation_frame('WhatsApp sekarang sering lambat menurutmu kenapa?')
assert strong_device_request('Bisa buka WhatsApp?')
from furina_agent.hub import HUB_HOST,HUB_PORT
assert HUB_HOST=='127.0.0.1' and HUB_PORT==8787
import furina_agent.hub as hubmod
src=open(hubmod.__file__,encoding='utf-8').read()
assert '/api/update/core' in src and '/api/device/probe' in src and '/api/connectors/execute' in src
assert '/api/conversations' in src and 'llm.vision' in src
assert 'prepare_" + mode' in src and 'rish di Termux tidak diperlukan' in src
print('FURINAHUB_RC38_CORE_OK')
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

install_stage() {
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
assert int(m['version_code'])==10023
assert m['version']=='1.0.0-rc23'
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
run_quiet "Memeriksa manifest RC39 / FurinaHub RC23" 22 fetch_manifest
run_quiet "Memverifikasi hash paket RC35" 29 fetch_rc35_bundle
run_quiet "Memverifikasi hash paket RC36" 36 fetch_rc36_bundle
run_quiet "Memverifikasi hash paket RC37" 43 fetch_rc37_bundle
run_quiet "Memverifikasi hash paket RC38" 47 fetch_rc38_bundle
run_quiet "Memverifikasi hash paket RC39" 49 fetch_rc39_bundle

if [[ "$CURRENT" != "1.0.0-rc34" && "$CURRENT" != "1.0.0-rc35" && "$CURRENT" != "1.0.0-rc36" && "$CURRENT" != "1.0.0-rc37" && "$CURRENT" != "1.0.0-rc38" && "$CURRENT" != "1.0.0-rc39" ]]; then
  run_quiet "Merekonstruksi fondasi Core hingga RC34" 52 prepare_rc34
  CURRENT="$(core_version)"
elif [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  mark 52 "Core RC34 ditemukan; siap migrasi FurinaHub"
elif [[ "$CURRENT" == "1.0.0-rc35" ]]; then
  mark 52 "Core RC35 ditemukan; siap sinkronisasi RC39"
elif [[ "$CURRENT" == "1.0.0-rc36" ]]; then
  mark 52 "Core RC36 ditemukan; siap perbaikan RC39"
elif [[ "$CURRENT" == "1.0.0-rc37" ]]; then
  mark 52 "Core RC37 ditemukan; siap sinkronisasi RC39"
elif [[ "$CURRENT" == "1.0.0-rc38" ]]; then
  mark 52 "Core RC38 ditemukan; siap fitur chat RC39"
else
  mark 52 "Core RC39 ditemukan; menjalankan health-check penuh"
fi

run_quiet "Membuat salinan aman Core" 59 stage_core
UPGRADED=0
if [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  run_quiet "Menerapkan fondasi Core RC35" 64 apply_rc35
  run_quiet "Menerapkan sinkronisasi Core RC36" 72 apply_rc36
  run_quiet "Menerapkan perbaikan dependency Core RC37" 78 apply_rc37
  run_quiet "Menerapkan sinkronisasi perangkat Core RC38" 79 apply_rc38
  run_quiet "Menerapkan chat, vision, dan riwayat Core RC39" 80 apply_rc39
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc35" ]]; then
  run_quiet "Menerapkan sinkronisasi Core RC36" 72 apply_rc36
  run_quiet "Menerapkan perbaikan dependency Core RC37" 78 apply_rc37
  run_quiet "Menerapkan sinkronisasi perangkat Core RC38" 79 apply_rc38
  run_quiet "Menerapkan chat, vision, dan riwayat Core RC39" 80 apply_rc39
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc36" ]]; then
  run_quiet "Menerapkan perbaikan dependency Core RC37" 78 apply_rc37
  run_quiet "Menerapkan sinkronisasi perangkat Core RC38" 79 apply_rc38
  run_quiet "Menerapkan chat, vision, dan riwayat Core RC39" 80 apply_rc39
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc37" ]]; then
  run_quiet "Menerapkan sinkronisasi perangkat Core RC38" 79 apply_rc38
  run_quiet "Menerapkan chat, vision, dan riwayat Core RC39" 80 apply_rc39
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc38" ]]; then
  run_quiet "Menerapkan chat, vision, dan riwayat Core RC39" 80 apply_rc39
  UPGRADED=1
else
  mark 80 "Tidak perlu menulis ulang Core RC39"
fi
run_quiet "Compile + regression chat/personality/skill" 82 validate_core
run_quiet "Menyiapkan integrasi Termux ↔ FurinaHub" 86 enable_termux_integration
run_quiet "Memasang launcher furina-hub" 89 install_launchers

if (( UPGRADED == 1 )); then
  run_quiet "Memasang Core secara atomik" 93 install_stage
else
  mark 93 "Core RC39 sehat; data tidak diubah"
fi

APK_BEFORE="$(cat "$ROOT/data/furinahub_apk_revision" 2>/dev/null || true)"
run_quiet "Memeriksa / menyiapkan APK FurinaHub RC23" 98 download_hub_apk
APK_AFTER="$(cat "$ROOT/data/furinahub_apk_revision" 2>/dev/null || true)"
if [[ "$APK_BEFORE" != "$APK_AFTER" ]]; then
  open_hub_apk
fi
mark 100 "FurinaHub siap"

printf '\n\033[32m✓\033[0m FurinaHub Core RC39 aktif.\n'
printf '  CLI tetap tersedia: \033[1mfurina\033[0m\n'
printf '  GUI server manual:  \033[1mfurina-hub\033[0m\n'
printf '  APK RC23: %s\n' "$HOME/FurinaHub.apk"
printf '  FurinaHub kini dapat dibuka tanpa Core; hubungkan Termux dari Pengaturan APK.\n'
printf '\033[2m  Log lengkap: %s\033[0m\n' "$LOG"
