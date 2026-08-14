#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

VERSION="1.0.0-rc31"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
MANIFEST_URL="$BASE/manifest.json"
BASE_INSTALL_URL="https://raw.githubusercontent.com/WynnDev-rill/furina/90ffa178c678441a666cd82f87f08b1755552fb1/experiments/furina-agent-final/install.sh"
BASE_INSTALL_BLOB="29f11a7c5d4452ca6c9e69f413118329e5958765"
RC19_URL="$BASE/overrides/apply-ui-performance-rc19.py"; RC19_BLOB="8e2e4f7248057c1cf8888fd15a990736767ed1fa"
RC20_URL="$BASE/overrides/apply-reactive-core-rc20.py"; RC20_BLOB="39e2a55579dd2ec90095c27a7498b6c088c7dbed"
RC21_URL="$BASE/overrides/apply-reactive-core-rc21.py"; RC21_BLOB="33f75d16d1734831a28e4daad987d94caabd59ef"
RC22_URL="$BASE/overrides/apply-system-rc22.py"; RC22_BLOB="828146920bfbceba759e1163ffce731e9ad65b05"
RC22_SAFETY_URL="$BASE/overrides/apply-safety-rc22.py"; RC22_SAFETY_BLOB="38237e878d206e831677e9d83980a436e7f3bc80"
RC23_URL="$BASE/overrides/apply-semantic-core-rc23.py"; RC23_BLOB="9f339191a3b0ddab2b89f0690e019b63552fe377"
RC23_GUARD_URL="$BASE/overrides/apply-semantic-guard-rc23.py"; RC23_GUARD_BLOB="a1bbd134c2b2424465e1b85fbc478ad20f9ea0ea"
RC24_URL="$BASE/overrides/apply-lifecycle-core-rc24.py"; RC24_BLOB="09e34acce76ed6675de1aa752ee10ef067b0d2bb"
RC25_URL="$BASE/overrides/apply-stateful-core-rc25.py"; RC25_BLOB="45d763724a3385eab3f278a14f0465279357b67c"
RC25_POSTFIX_URL="$BASE/overrides/apply-stateful-core-rc25-postfix.py"; RC25_POSTFIX_BLOB="16cb897717beb33063bcd1863b30060e1607b092"
RC26_URL="$BASE/overrides/apply-semantic-resilience-rc26.py"; RC26_BLOB="9fd353b275a2a426fe9ab2e8d7ebb5808586b965"
RC27_URL="$BASE/overrides/apply-runtime-recovery-rc27.py"; RC27_BLOB="0329f71edfad6f34f1892bdbc7e0388f432ce070"
RC28_URL="$BASE/overrides/apply-runtime-core-rc28.py"; RC28_BLOB="98038cd52fa88652ca141a1af2ee3f9d10cebf5f"
RC29_URL="$BASE/overrides/apply-universal-ui-core-rc29.py"; RC29_BLOB="eb0a507da074d280f2f263ae70e3c0e4e2afd220"
RC30_URL="$BASE/overrides/apply-privileged-core-rc30.py"; RC30_BLOB="e2a98f867c86786de99c942c3baf832fdc330e5d"
RC31_URL="$BASE/overrides/apply-device-control-core-rc31.py"; RC31_BLOB="8ce33b8a81feb379f6187583f350b4bf3097268c"

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer ini harus dijalankan dari Termux." >&2
  exit 1
fi
mkdir -p "$ROOT"/{cache,logs,run,data,models}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
LOG="$ROOT/logs/update-rc31.log"
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
  printf '\033[2mUpdate Agent RC31 · hanya runtime device-control yang diperbarui\033[0m\n\n'
}
ui_progress() {
  local pct="$1" label="$2" glyph="${3:-›}" width=16 filled empty bar="" i
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
    tail -n 24 "$LOG" >&2 || true
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
fetch_transform() {
  curl -fsSL --retry 3 "$1" -o "$3"
  verify_git_blob "$3" "$2"
}
read_core_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
s=open(sys.argv[1],encoding='utf-8').read(); m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',s)
print(m.group(1) if m else 'unknown')
PY
}

ui_title
mark 5 "Memeriksa instalasi Furina"

if [[ ! -f "$ROOT/core/furina_agent/version.py" ]]; then
  fetch_transform "$BASE_INSTALL_URL" "$BASE_INSTALL_BLOB" "$TMP/install-base.sh"
  run_quiet "Menyiapkan fondasi Furina" 28 bash "$TMP/install-base.sh" "$@"
fi

CURRENT="$(read_core_version)"
mark 33 "Core saat ini: $CURRENT"
curl -fsSL --retry 3 "$MANIFEST_URL" -o "$TMP/manifest.json"
EXPECTED="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["version"])')"
[[ "$EXPECTED" == "1.0.0-rc31" ]] || { echo "Manifest belum menunjuk RC31: $EXPECTED" >&2; exit 1; }
mark 39 "Manifest RC31 terverifikasi"

mkdir -p "$TMP/stage"
cp -R "$ROOT/core" "$TMP/stage/core"
mark 44 "Membuat salinan aman Core"

apply_core_updates() {
  local current="$1"
  if [[ "$current" == "1.0.0-rc18" ]]; then fetch_transform "$RC19_URL" "$RC19_BLOB" "$TMP/rc19.py"; python "$TMP/rc19.py" "$TMP/stage"; current="1.0.0-rc19"; fi
  if [[ "$current" == "1.0.0-rc19" ]]; then fetch_transform "$RC20_URL" "$RC20_BLOB" "$TMP/rc20.py"; python "$TMP/rc20.py" "$TMP/stage"; current="1.0.0-rc20"; fi
  if [[ "$current" == "1.0.0-rc20" ]]; then fetch_transform "$RC21_URL" "$RC21_BLOB" "$TMP/rc21.py"; python "$TMP/rc21.py" "$TMP/stage"; current="1.0.0-rc21"; fi
  if [[ "$current" == "1.0.0-rc21" ]]; then fetch_transform "$RC22_URL" "$RC22_BLOB" "$TMP/rc22.py"; python "$TMP/rc22.py" "$TMP/stage"; current="1.0.0-rc22"; fi
  if [[ "$current" == "1.0.0-rc22" ]]; then
    fetch_transform "$RC22_SAFETY_URL" "$RC22_SAFETY_BLOB" "$TMP/rc22-safety.py"; python "$TMP/rc22-safety.py" "$TMP/stage"
    fetch_transform "$RC23_URL" "$RC23_BLOB" "$TMP/rc23.py"; python "$TMP/rc23.py" "$TMP/stage"; current="1.0.0-rc23"
  fi
  if [[ "$current" == "1.0.0-rc23" ]]; then
    fetch_transform "$RC23_GUARD_URL" "$RC23_GUARD_BLOB" "$TMP/rc23-guard.py"; python "$TMP/rc23-guard.py" "$TMP/stage"
    fetch_transform "$RC24_URL" "$RC24_BLOB" "$TMP/rc24.py"; python "$TMP/rc24.py" "$TMP/stage"; current="1.0.0-rc24"
  fi
  if [[ "$current" == "1.0.0-rc24" ]]; then fetch_transform "$RC25_URL" "$RC25_BLOB" "$TMP/rc25.py"; python "$TMP/rc25.py" "$TMP/stage"; current="1.0.0-rc25"; fi
  if [[ "$current" == "1.0.0-rc25" ]]; then
    fetch_transform "$RC25_POSTFIX_URL" "$RC25_POSTFIX_BLOB" "$TMP/rc25-postfix.py"; python "$TMP/rc25-postfix.py" "$TMP/stage"
    fetch_transform "$RC26_URL" "$RC26_BLOB" "$TMP/rc26.py"; python "$TMP/rc26.py" "$TMP/stage"; current="1.0.0-rc26"
  fi
  if [[ "$current" == "1.0.0-rc26" ]]; then fetch_transform "$RC27_URL" "$RC27_BLOB" "$TMP/rc27.py"; python "$TMP/rc27.py" "$TMP/stage"; current="1.0.0-rc27"; fi
  if [[ "$current" == "1.0.0-rc27" ]]; then fetch_transform "$RC28_URL" "$RC28_BLOB" "$TMP/rc28.py"; python "$TMP/rc28.py" "$TMP/stage"; current="1.0.0-rc28"; fi
  if [[ "$current" == "1.0.0-rc28" ]]; then fetch_transform "$RC29_URL" "$RC29_BLOB" "$TMP/rc29.py"; python "$TMP/rc29.py" "$TMP/stage"; current="1.0.0-rc29"; fi
  if [[ "$current" == "1.0.0-rc29" ]]; then fetch_transform "$RC30_URL" "$RC30_BLOB" "$TMP/rc30.py"; python "$TMP/rc30.py" "$TMP/stage"; current="1.0.0-rc30"; fi
  if [[ "$current" == "1.0.0-rc30" ]]; then fetch_transform "$RC31_URL" "$RC31_BLOB" "$TMP/rc31.py"; python "$TMP/rc31.py" "$TMP/stage"; current="1.0.0-rc31"; fi
  [[ "$current" == "1.0.0-rc31" ]] || { echo "Versi Core tidak dapat dimigrasikan otomatis: $current" >&2; return 1; }
}
run_quiet "Menerapkan runtime device-control RC31" 67 apply_core_updates "$CURRENT"

validate_core() {
  PYTHONPATH="$TMP/stage/core" python -m compileall -q "$TMP/stage/core/furina_agent"
  PYTHONPATH="$TMP/stage/core" python - <<'PY'
from furina_agent.version import VERSION
from furina_agent.agent import AndroidAgent
if VERSION != '1.0.0-rc31': raise SystemExit(VERSION)
for name in ('_compact_screen','_with_vision','_plan','risk','_wait_after_action','_try_fast_skill','_device_mode'):
    if not hasattr(AndroidAgent,name): raise SystemExit('missing '+name)
src=open(__import__('furina_agent.agent').agent.__file__,encoding='utf-8').read()
for marker in ('STATE_UI_UNTRUSTED','nodes_ranked','agent_vision_rescue','event_then_single_snapshot','choose_fast_skill'):
    assert marker in src, marker
rt=open(__import__('furina_agent.tool_runtime').tool_runtime.__file__,encoding='utf-8').read()
assert '"requested_mode": requested_mode[:16]' in rt
PY
}
run_quiet "Memvalidasi runtime Agent" 79 validate_core

furina stop >/dev/null 2>&1 || true
rm -rf "$ROOT/core.prev"
mv "$ROOT/core" "$ROOT/core.prev"
mv "$TMP/stage/core" "$ROOT/core"
mark 85 "Core RC31 aktif · data percakapan/model tidak diubah"

prepare_bridge() {
  local health expected_name expected_code installed_name installed_code release meta_name meta_code meta_package apk_url
  printf '%s' "unknown" > "$TMP/bridge-state"
  health="$(curl -fsS --max-time 2 http://127.0.0.1:8765/health 2>/dev/null || true)"
  expected_name="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["bridge_version"])')"
  expected_code="$(python -c 'import json;print(int(json.load(open("'"$TMP"'/manifest.json"))["bridge_version_code"]))')"
  [[ -n "$health" ]] || return 0
  printf '%s' "$health" > "$TMP/bridge-health.json"
  installed_name="$(python - "$TMP/bridge-health.json" <<'PY' 2>/dev/null || true
import json,sys
try: print(str(json.load(open(sys.argv[1])).get('version') or ''))
except Exception: print('')
PY
)"
  installed_code="$(python - "$TMP/bridge-health.json" <<'PY' 2>/dev/null || true
import json,sys
try: print(int(json.load(open(sys.argv[1])).get('version_code') or 0))
except Exception: print(0)
PY
)"
  installed_code="${installed_code:-0}"
  if (( installed_code >= expected_code )) || [[ "$installed_name" == "$expected_name" ]]; then
    furina connect >/dev/null 2>&1 || true
    printf '%s' "ready" > "$TMP/bridge-state"
    return 0
  fi
  release="$(python -c 'import json;print(json.load(open("'"$TMP"'/manifest.json"))["bridge_release_base"])')"
  curl -fsSL --retry 3 "$release/bridge.json" -o "$TMP/bridge.json"
  meta_name="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["version"])')"
  meta_code="$(python -c 'import json;print(int(json.load(open("'"$TMP"'/bridge.json"))["version_code"]))')"
  meta_package="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["package_name"])')"
  apk_url="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["apk_url"])')"
  [[ "$meta_name" == "$expected_name" && "$meta_code" == "$expected_code" ]] || { echo "Metadata Bridge tidak cocok." >&2; return 1; }
  [[ "$meta_package" == "com.wynndev.furinaagentbridge" ]] || { echo "Package Bridge tidak dikenal." >&2; return 1; }
  [[ "$apk_url" == https://github.com/WynnDev-rill/furina/releases/download/* ]] || { echo "URL Bridge tidak dipercaya." >&2; return 1; }
  printf '%s' "install" > "$TMP/bridge-state"
}
run_quiet "Memeriksa Bridge RC18" 94 prepare_bridge

BRIDGE_STATE="$(cat "$TMP/bridge-state" 2>/dev/null || true)"
if [[ "$BRIDGE_STATE" == "install" ]]; then
  APK_URL="$(python -c 'import json;print(json.load(open("'"$TMP"'/bridge.json"))["apk_url"])')"
  termux-open-url "$APK_URL" >/dev/null 2>&1 || true
  printf '\n\033[33m!\033[0m Bridge RC18 tersedia. Selesaikan tombol \033[1mPerbarui\033[0m di Android, lalu jalankan furina lagi.\n'
elif [[ "$BRIDGE_STATE" == "unknown" ]]; then
  printf '\n\033[33m!\033[0m Bridge tidak sedang dapat diperiksa. Buka Furina Bridge/aktifkan Accessibility, lalu jalankan \033[1mfurina update\033[0m lagi.\n'
else
  printf '\n\033[32m✓\033[0m Bridge RC18 sudah siap.\n'
fi
mark 100 "Update Agent RC31 selesai"
printf '\n'
