#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc47"
DEPENDENCY_REVISION="2026.08.15-r11"
ROOT="$HOME/.furina-agent"
BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
PINNED_RC46="5cf4080ac5bc5ae8204c45490825715f63a89627"
RC46_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/$PINNED_RC46/experiments/furina-agent-final"
RC46_BODY_URL="$RC46_BASE/overrides/rc46/install-body.sh"
RC46_BODY_BLOB="de2b7c6acb892ce7a9049558456f418a68f4e880"
RC47_APPLY_URL="$BASE/overrides/rc47/apply.py"
RC47_APPLY_BLOB="285b1911b580fffdfea1c9484151c1d5ba680559"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi
mkdir -p "$ROOT"/{cache,logs,run,data,models}
EXISTING_INSTALL=0
[[ -f "$ROOT/core/furina_agent/version.py" ]] && EXISTING_INSTALL=1
LOG="$ROOT/logs/update-rc47-furinahub.log"
: > "$LOG"

progress() {
  local pct="$1"; shift
  if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then
    printf 'PROGRESS %d %s\n' "$pct" "$*"
  else
    printf '[%3d%%] %s\n' "$pct" "$*"
  fi
}

installed_version() {
  python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try: text=open(sys.argv[1],encoding='utf-8').read()
except OSError: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text)
print(m.group(1) if m else 'unknown')
PY
}

# Normal `furina update` must be cheap and idempotent. Do not reconstruct
# historical RC layers when the installed Core/runtime already matches.
CURRENT="$(installed_version 2>/dev/null || true)"
CURRENT_REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$CURRENT_REVISION" == "$DEPENDENCY_REVISION" ]]; then
  if command -v furina-openconnector >/dev/null 2>&1; then
    furina-openconnector start >>"$LOG" 2>&1 || true
  fi
  progress 100 "Core dan runtime sudah terbaru"
  printf '✓ FurinaHub Core %s sudah terbaru · runtime %s\n' "$VERSION" "$DEPENDENCY_REVISION"
  exit 0
fi

fetch() {
  local url="$1"
  local out="$2"
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

progress 1 "Menyiapkan updater Core"
fetch "$RC46_BODY_URL" "$TMP/rc46-install-body.sh"
verify_blob "$TMP/rc46-install-body.sh" "$RC46_BODY_BLOB"
python - "$TMP/rc46-install-body.sh" "$RC46_BASE" <<'PY'
from pathlib import Path
import re,sys
path=Path(sys.argv[1]); pinned=sys.argv[2]
text=path.read_text(encoding='utf-8')
old='local from="$1" to="$2" url="$3" blob="$4" label="$5" file="$TMP/apply-$to.py" stage="$TMP/stage-$to"'
new='''local from="$1"
  local to="$2"
  local url="$3"
  local blob="$4"
  local label="$5"
  local file="$TMP/apply-$to.py"
  local stage="$TMP/stage-$to"'''
if old not in text:
    raise SystemExit('Marker bug apply_overlay RC46 tidak ditemukan')
text=text.replace(old,new,1)
text,count=re.subn(r'^BASE="[^"]+"$', f'BASE="{pinned}"', text, count=1, flags=re.M)
if count != 1:
    raise SystemExit('BASE RC46 tidak dapat dipin')
old_apk='\nensure_rc29_apk_file\n'
new_apk='\nif [[ "${FURINAHUB_CORE_ONLY:-0}" != "1" ]]; then ensure_rc29_apk_file; fi\n'
if old_apk not in text:
    raise SystemExit('Marker APK RC46 tidak ditemukan')
text=text.replace(old_apk,new_apk,1)
text=text.replace('Core, Plugin, dan APK siap','Core dan Plugin siap')
text=text.replace('Core & APK siap; Plugin perlu perhatian','Core siap; Plugin perlu perhatian')
text=text.replace('  APK: FurinaHub RC29.\\n','')
path.write_text(text,encoding='utf-8')
PY
bash -n "$TMP/rc46-install-body.sh"

# Existing installations update only Core/runtime. APK lifecycle belongs to
# FurinaHub's Android updater, so `furina update` cannot downgrade/reinstall APK.
FURINAHUB_CORE_ONLY="$EXISTING_INSTALL" FURINAHUB_MACHINE_PROGRESS="${FURINAHUB_MACHINE_PROGRESS:-0}" bash "$TMP/rc46-install-body.sh" "$@" >>"$LOG" 2>&1

progress 94 "Memastikan Core RC47 dan skill Agent"
fetch "$RC47_APPLY_URL" "$TMP/apply-rc47.py"
verify_blob "$TMP/apply-rc47.py" "$RC47_APPLY_BLOB"
python "$TMP/apply-rc47.py" "$ROOT" >>"$LOG" 2>&1
python -m compileall -q "$ROOT/core/furina_agent"
grep -q 'VERSION = "1.0.0-rc47"' "$ROOT/core/furina_agent/version.py"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"

if command -v furina-openconnector >/dev/null 2>&1; then
  furina-openconnector start >>"$LOG" 2>&1 || true
fi
progress 100 "Core RC47 dan runtime siap"
printf '✓ FurinaHub Core %s aktif · runtime %s\n' "$VERSION" "$DEPENDENCY_REVISION"
if (( EXISTING_INSTALL == 1 )); then
  printf '  APK tidak diubah; update APK dilakukan dari menu Update FurinaHub.\n'
fi
printf '  Log: %s\n' "$LOG"
