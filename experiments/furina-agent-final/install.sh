#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc34"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PREV_COMMIT="5b6b3685e8b0e82eb6d92af7b187340420d041b7"
PREV_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PREV_COMMIT/experiments/furina-agent-final"
PREV_INSTALL_URL="$PREV_BASE/install.sh"
PREV_INSTALL_BLOB="77dcc0247300d8d68fa33ce07a0e094c68d4552a"
RC34_APPLY_URL="$BASE/overrides/rc34/apply.py"
RC34_APPLY_BLOB="4c41cc7a1405d42c8d1e6f51c2ab0daa5e5cd53a"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi

mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc34.log"
: > "$LOG"
PROGRESS=0

ui_title() {
  printf '\033[2J\033[H'
  printf '\033[1;36mFurina\033[0m \033[1mBy Wynn\033[0m\n'
  printf '\033[2mUpdate Agent RC34 · chat-first intent guard\033[0m\n\n'
}

ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=16 filled empty bar="" i
  (( pct < 0 )) && pct=0
  (( pct > 100 )) && pct=100
  filled=$(( pct * width / 100 ))
  empty=$(( width - filled ))
  for ((i=0;i<filled;i++)); do bar+="█"; done
  for ((i=0;i<empty;i++)); do bar+="░"; done
  printf '\r\033[K\033[35m%s\033[0m \033[2m[%s]\033[0m \033[1m%3d%%\033[0m %s' "$glyph" "$bar" "$pct" "$label"
}

mark() {
  PROGRESS="$1"
  ui_progress "$1" "$2" "✓"
  printf '\n'
}

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
  set +e
  wait "$pid"
  rc=$?
  set -e
  if (( rc != 0 )); then
    printf '\r\033[K\033[31m×\033[0m %s\n' "$label"
    printf '\033[2mLog: %s\033[0m\n' "$LOG" >&2
    tail -n 35 "$LOG" >&2 || true
    exit "$rc"
  fi
  mark "$target" "$label"
}

ensure_python() {
  command -v python >/dev/null 2>&1 || pkg install -y python
}

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
assert m.get('version') == '1.0.0-rc34', m.get('version')
assert m.get('bridge_version') == '1.0.0-rc18', m.get('bridge_version')
assert int(m.get('bridge_version_code')) == 10018
assert len(m.get('source_sha256','')) == 64
PY
}

fetch_rc34_bundle() {
  mkdir -p "$TMP/rc34"
  fetch_blob "$RC34_APPLY_URL" "$RC34_APPLY_BLOB" "$TMP/rc34/apply.py"
  python -m py_compile "$TMP/rc34/apply.py"
}

prepare_rc33() {
  fetch_blob "$PREV_INSTALL_URL" "$PREV_INSTALL_BLOB" "$TMP/install-rc33.sh"
  python - "$TMP/install-rc33.sh" "$PREV_BASE" <<'PY'
import pathlib,sys
path=pathlib.Path(sys.argv[1]); pinned=sys.argv[2]
text=path.read_text(encoding='utf-8')
old='BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"'
new=f'BASE="{pinned}"'
if text.count(old) != 1:
    raise SystemExit('RC33 installer BASE marker berubah')
path.write_text(text.replace(old,new,1),encoding='utf-8')
PY
  bash "$TMP/install-rc33.sh" "$@"
  [[ "$(core_version)" == "1.0.0-rc33" ]]
}

stage_core() {
  rm -rf "$TMP/stage"
  mkdir -p "$TMP/stage"
  cp -R "$ROOT/core" "$TMP/stage/core"
}

apply_rc34() {
  python "$TMP/rc34/apply.py" "$TMP/stage"
}

validate_compile() {
  PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.intent_guard import conversation_frame,strong_device_request
assert VERSION == '1.0.0-rc34'
assert conversation_frame('WhatsApp sekarang sering lambat menurutmu kenapa?')
assert not strong_device_request('WhatsApp sekarang sering lambat menurutmu kenapa?')
assert strong_device_request('Tolong bukain WhatsApp')
PY
}

validate_behavior() {
  PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.intent_guard import conversation_frame,strong_device_request,committed_device_intent
from furina_agent.policy import build_goal_lock,classify_action

chat_cases=(
    'WhatsApp sekarang sering lambat menurutmu kenapa?',
    'Tadi aku buka WhatsApp lalu chat Ariel',
    'Kalau aku bilang buka WhatsApp, kamu bakal apa?',
    'Jangan buka WhatsApp',
    'ketik itu artinya apa?',
)
for text in chat_cases:
    assert conversation_frame(text), text
    assert not strong_device_request(text), text

assert not conversation_frame('Bisa buka WhatsApp?')
assert strong_device_request('Bisa buka WhatsApp?')
assert strong_device_request('Buka WhatsApp lalu cari Ariel')

assert committed_device_intent(
    'Bisa buka WhatsApp?',
    {'speech_act':'request','explicit_device_action':True,'action_span':'buka WhatsApp'},
    [{'type':'open_app','package':'com.whatsapp'}],
    0.90,
)
assert not committed_device_intent(
    'WhatsApp lagi lambat',
    {'speech_act':'request','explicit_device_action':True,'action_span':'WhatsApp'},
    [{'type':'open_app','package':'com.whatsapp'}],
    0.99,
)

import furina_agent.companion as companion
import furina_agent.direct_control as direct
companion_src=open(companion.__file__,encoding='utf-8').read()
direct_src=open(direct.__file__,encoding='utf-8').read()
assert 'semantic_intent_device_fallback' not in companion_src
assert 'semantic_device_rejected' in companion_src
assert 'semantic_intent_error_chat_fallback' in companion_src
assert 'role="intent"' in companion_src
assert 'direct_control_chat_guard' in direct_src

# Existing RC32 device-action firewall remains the authority after routing.
apps=[{'label':'WhatsApp','package':'com.whatsapp'},{'label':'Notes','package':'com.notes'}]
lock=build_goal_lock('buka WhatsApp cari Ariel',apps,[{'type':'open_app','package':'com.whatsapp'}])
assert classify_action(
    {'package':'com.whatsapp','nodes':[{'id':7,'text':'Send'}]},
    {'type':'tap_node','node':7},lock
)[0] == 'blocked'
print('RC34_INTENT_GUARD_LOCAL_OK')
PY
}

install_stage() {
  furina stop >/dev/null 2>&1 || true
  rm -rf "$ROOT/core.prev"
  mv "$ROOT/core" "$ROOT/core.prev"
  mv "$TMP/stage/core" "$ROOT/core"
}

ui_title
run_quiet "Memeriksa lingkungan Termux" 6 ensure_python
CURRENT="$(core_version 2>/dev/null || true)"
mark 12 "Versi Core saat ini: ${CURRENT:-missing}"
run_quiet "Memeriksa manifest RC34 dan Bridge target" 22 fetch_manifest
run_quiet "Memverifikasi integritas intent-guard RC34" 34 fetch_rc34_bundle

if [[ "$CURRENT" != "1.0.0-rc33" && "$CURRENT" != "1.0.0-rc34" ]]; then
  run_quiet "Menyiapkan fondasi Core RC33" 54 prepare_rc33 "$@"
  CURRENT="$(core_version)"
  mark 58 "Fondasi Core RC33 terverifikasi"
elif [[ "$CURRENT" == "1.0.0-rc33" ]]; then
  mark 54 "Core RC33 ditemukan; siap migrasi intent guard"
else
  mark 54 "Core RC34 ditemukan; lanjut health-check penuh"
fi

run_quiet "Membuat salinan aman Core" 64 stage_core
UPGRADED=0
if [[ "$CURRENT" == "1.0.0-rc33" ]]; then
  run_quiet "Menerapkan chat-first intent commitment gate" 76 apply_rc34
  UPGRADED=1
elif [[ "$CURRENT" == "1.0.0-rc34" ]]; then
  mark 76 "Tidak perlu menulis ulang Core RC34"
else
  echo "Versi Core tidak dapat divalidasi otomatis: $CURRENT" >&2
  exit 1
fi

run_quiet "Memeriksa syntax dan import seluruh Core" 86 validate_compile
run_quiet "Menguji chat vs perintah Agent + RC32 policy" 95 validate_behavior

if (( UPGRADED == 1 )); then
  run_quiet "Memasang Core secara atomik" 99 install_stage
  mark 100 "Update Agent RC34 selesai dan terverifikasi"
else
  mark 100 "Core RC34 terverifikasi sehat; tidak ada file yang diubah"
fi

printf '\n\033[32m✓\033[0m Chat-first intent guard aktif.\n'
printf '  Nama aplikasi sekarang hanya konteks, bukan izin menjalankan Agent.\n'
printf '  Memory/model/data tetap dipertahankan. Bridge tetap RC18.\n'
printf '\033[2m  Log lengkap: %s\033[0m\n' "$LOG"
