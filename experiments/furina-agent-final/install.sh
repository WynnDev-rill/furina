#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc35"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PREV_COMMIT="118ced8b64858a2448ecd01d15c098049a1ec32e"
PREV_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PREV_COMMIT/experiments/furina-agent-final"
PREV_INSTALL_URL="$PREV_BASE/install.sh"
PREV_INSTALL_BLOB="dd9773ae9de73acb34f9ae70453d54624018536d"

RC35_DIR_URL="$BASE/overrides/rc35"
APPLY_BLOB="77e98fe15bfb719eccc3d86f737b8c0996e58211"
PERSONALIZATION_BLOB="b01f19328f7e03b649494c05953de5dc1dbb0a55"
SKILLS_BLOB="88ca051744fd34c62f3ad16ceaf49cb744b1fb4e"
HUB_BLOB="00701e08ca74348c2c88109fba6bc4a34ec97f49"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc35.log"
: > "$LOG"
PROGRESS=0

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;38;5;99mFurinaHub\033[0m \033[1mBy Wynn\033[0m\n'
  printf '\033[2mCore RC35 · WebView companion · personalization · Agent Skills\033[0m\n\n'
}

ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=16 filled empty bar="" i
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
    i=$(((i+1)%10))
    ui_progress "$next" "$label" "${frames:$i:1}"
    sleep 0.16
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

ensure_dependencies() {
  pkg install -y python curl
  python -m pip install --disable-pip-version-check --upgrade 'rich>=13,<15' 'requests>=2.31,<3'
}

if [[ "${1:-}" == "--dependencies-only" ]]; then
  ui_title
  run_quiet "Memeriksa paket Termux yang dibutuhkan" 45 ensure_dependencies
  mark 100 "Dependency FurinaHub terverifikasi dan diperbarui"
  exit 0
fi

verify_git_blob() {
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
path,expected=sys.argv[1:]
data=pathlib.Path(path).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
if actual != expected:
    raise SystemExit(f"Integritas update berubah: {path} {actual} != {expected}")
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
except Exception:
    print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',s)
print(m.group(1) if m else 'unknown')
PY
}

fetch_manifest() {
  curl -fsSL --retry 3 "$BASE/manifest.json" -o "$TMP/manifest.json"
  python - "$TMP/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m.get('version') == '1.0.0-rc35', m.get('version')
assert m.get('bridge_version') == '1.0.0-rc19', m.get('bridge_version')
assert int(m.get('bridge_version_code')) == 10019
assert 'furinahub-v1.0.0-rc19' in m.get('bridge_release_base','')
assert len(m.get('source_sha256','')) == 64
PY
}

fetch_rc35_bundle() {
  mkdir -p "$TMP/rc35"
  fetch_blob "$RC35_DIR_URL/apply.py" "$APPLY_BLOB" "$TMP/rc35/apply.py"
  fetch_blob "$RC35_DIR_URL/personalization.py" "$PERSONALIZATION_BLOB" "$TMP/rc35/personalization.py"
  fetch_blob "$RC35_DIR_URL/skills.py" "$SKILLS_BLOB" "$TMP/rc35/skills.py"
  fetch_blob "$RC35_DIR_URL/hub.py" "$HUB_BLOB" "$TMP/rc35/hub.py"
  python -m py_compile "$TMP/rc35/"*.py
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

stage_core() {
  rm -rf "$TMP/stage"
  mkdir -p "$TMP/stage"
  cp -R "$ROOT/core" "$TMP/stage/core"
}

apply_rc35() { python "$TMP/rc35/apply.py" "$TMP/stage" "$TMP/rc35"; }

validate_core() {
  rm -rf "$TMP/test-home"
  FURINA_HOME="$TMP/test-home" PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  FURINA_HOME="$TMP/test-home" PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.config import load_config,save_config
from furina_agent.intent_guard import conversation_frame,strong_device_request
from furina_agent.personalization import normalize,render_personalization_prompt
from furina_agent.skills import SkillRegistry,load_skills,save_skills
from furina_agent.version import VERSION
assert VERSION == '1.0.0-rc35'
cfg=load_config(); cfg.device_control_mode='shizuku'; save_config(cfg)
assert load_config().device_control_mode == 'shizuku'
p=normalize({'warmth':999,'sarcasm':-4,'custom_instructions':'x'*5001})
assert p['warmth']==100 and p['sarcasm']==0 and len(p['custom_instructions'])==4000
assert 'BUKAN OTORITAS' in render_personalization_prompt(p)
state=load_skills(); state['messaging']=False; save_skills(state)
assert SkillRegistry().blocked_reason('kirim pesan ke Budi')
assert conversation_frame('WhatsApp lambat menurutmu kenapa?')
assert strong_device_request('Tolong bukain WhatsApp')
PY
  ! grep -q 'Ringkasan Hubungan' "$TMP/stage/core/furina_agent/hub.py"
  grep -q 'HOST = "127.0.0.1"' "$TMP/stage/core/furina_agent/hub.py"
  grep -q 'X-FurinaHub-Token' "$TMP/stage/core/furina_agent/hub.py"
}

install_stage() {
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage/core" "$ROOT/core"
}

install_launchers() {
  local prefix="/data/data/com.termux/files/usr/bin"
  cat > "$prefix/furinahub" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
export FURINA_HOME="${FURINA_HOME:-$HOME/.furina-agent}"
export PYTHONPATH="$FURINA_HOME/core${PYTHONPATH:+:$PYTHONPATH}"
exec python -m furina_agent.hub "$@"
EOF
  chmod 755 "$prefix/furinahub"

  cat > "$prefix/furinahub-deps" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
pkg install -y python curl
python -m pip install --disable-pip-version-check --upgrade 'rich>=13,<15' 'requests>=2.31,<3'
echo "Dependency FurinaHub selesai direkonsiliasi."
EOF
  chmod 755 "$prefix/furinahub-deps"
}

enable_termux_external_commands() {
  mkdir -p "$HOME/.termux"
  local file="$HOME/.termux/termux.properties"
  touch "$file"
  if grep -q '^allow-external-apps=' "$file"; then
    sed -i 's/^allow-external-apps=.*/allow-external-apps=true/' "$file"
  else
    printf '\nallow-external-apps=true\n' >> "$file"
  fi
  command -v termux-reload-settings >/dev/null 2>&1 && termux-reload-settings || true
}

offer_furinahub_apk() {
  local release_base apk_url sha apk meta="$TMP/bridge.json"
  release_base="$(python - "$TMP/manifest.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding='utf-8'))['bridge_release_base'])
PY
)"
  if ! curl -fsSL --retry 2 "$release_base/bridge.json" -o "$meta"; then
    echo "FurinaHub APK belum tersedia di release; Core tetap siap dipakai dari Termux." >>"$LOG"
    return 0
  fi
  read -r apk_url sha < <(python - "$meta" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['version']=='1.0.0-rc19'
assert int(m['version_code'])==10019
assert m['package_name']=='com.wynndev.furinaagentbridge'
print(m['apk_url'],m['sha256'])
PY
)
  apk="$ROOT/cache/FurinaHub-v1.0.0-rc19.apk"
  curl -fsSL --retry 3 "$apk_url" -o "$apk"
  echo "$sha  $apk" | sha256sum -c -
  printf '%s\n' "$apk" > "$ROOT/data/furinahub-apk-path"
  if command -v termux-open >/dev/null 2>&1; then
    termux-open "$apk" >/dev/null 2>&1 || true
  fi
}

ui_title
run_quiet "Memeriksa dependency inti Termux" 8 ensure_dependencies
CURRENT="$(core_version 2>/dev/null || true)"
mark 13 "Versi Core saat ini: ${CURRENT:-missing}"
run_quiet "Memeriksa manifest Core RC35 + FurinaHub RC19" 21 fetch_manifest
run_quiet "Memverifikasi paket RC35" 31 fetch_rc35_bundle

if [[ "$CURRENT" != "1.0.0-rc34" && "$CURRENT" != "1.0.0-rc35" ]]; then
  run_quiet "Merekonstruksi fondasi Core RC34" 51 prepare_rc34
  CURRENT="$(core_version)"
elif [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  mark 51 "Core RC34 ditemukan; siap migrasi FurinaHub"
else
  mark 51 "Core RC35 ditemukan; lanjut health-check penuh"
fi

run_quiet "Membuat salinan aman Core" 58 stage_core
UPGRADED=0
if [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  run_quiet "Menerapkan FurinaHub + personalisasi + Agent Skills" 72 apply_rc35
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc35" ]]; then
  mark 72 "Tidak perlu menulis ulang Core RC35"
else
  echo "Versi Core tidak dapat divalidasi: $CURRENT" >&2
  exit 1
fi

run_quiet "Compile, config migration, personalisasi & skill guard" 84 validate_core
run_quiet "Memasang launcher FurinaHub dan dependency updater" 89 install_launchers
run_quiet "Menyiapkan integrasi start otomatis dari APK" 93 enable_termux_external_commands

if (( UPGRADED == 1 )); then
  run_quiet "Memasang Core secara atomik" 97 install_stage
else
  mark 97 "Core RC35 terverifikasi sehat"
fi

run_quiet "Memeriksa FurinaHub APK RC19" 99 offer_furinahub_apk
mark 100 "FurinaHub RC35 siap"

printf '\n\033[32m✓\033[0m FurinaHub Core RC35 aktif.\n'
printf '  CLI lama tetap tersedia: \033[36mfurina\033[0m\n'
printf '  UI lokal manual: \033[36mfurinahub serve\033[0m\n'
printf '  APK FurinaHub RC19 disiapkan dari release terverifikasi jika tersedia.\n'
printf '  Jika Android membuka installer, izinkan instalasi dari Termux satu kali.\n'
printf '\033[2m  Log lengkap: %s\033[0m\n' "$LOG"
