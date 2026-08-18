#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc54"
DEPENDENCY_REVISION="2026.08.18-r24"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
R22_BODY_PATH="overrides/runtime-r22/install-body.sh"
R22_BODY_BLOB="3e892305bad6ddc880cff610d87c37ca814e9351"
RC54_APPLY_PATH="overrides/rc54/apply.py"
RC54_APPLY_BLOB="0b7e0449de01fe40746230e79d93740078fc785c"
STATE_PATH="overrides/rc53/companion_state_v2.py"
STATE_BLOB="27fdb2a785bfdf28d7514ca35db1d5e73cfd5584"
MIND_PATH="overrides/core/furina_agent/mind_v2.py"
MIND_BLOB="05f5a5a6d5700c449f03535ec658363351e3c560"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r24-furinahub.log"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -d /data/data/com.termux/files/usr ]]; then
  echo "Installer FurinaHub harus dijalankan dari Termux." >&2
  exit 1
fi

progress() {
  local pct="$1"; shift
  if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then
    printf 'PROGRESS %d %s\n' "$pct" "$*"
  else
    printf '[%3d%%] %s\n' "$pct" "$*"
  fi
}

FETCH_CODE="000"
fetch_url() {
  local url="$1" out="$2" api="${3:-0}" code
  rm -f "$out"
  local args=(-L --silent --show-error --connect-timeout 10 --max-time 90
              --retry 2 --retry-delay 1 --retry-all-errors
              -o "$out" -w '%{http_code}'
              -H 'User-Agent: Furina-Core-Updater/7'
              -H 'Cache-Control: no-cache' -H 'Pragma: no-cache')
  if [[ "$api" == "1" ]]; then args+=(-H 'Accept: application/vnd.github.raw+json'); fi
  code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"
  FETCH_CODE="${code:-000}"
  if [[ "$FETCH_CODE" == "200" && -s "$out" ]]; then return 0; fi
  rm -f "$out"; return 1
}

fetch_rel() {
  local rel="$1" out="$2" asset=""
  command -v curl >/dev/null 2>&1 || pkg install -y curl >/dev/null
  case "$rel" in
    overrides/runtime-r22/install-body.sh) asset="core-r22-install-body.sh" ;;
    overrides/rc54/apply.py) asset="core-rc54-apply.py" ;;
    overrides/rc53/companion_state_v2.py) asset="core-rc54-companion-state.py" ;;
    overrides/core/furina_agent/mind_v2.py) asset="core-rc54-mind.py" ;;
  esac
  if fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1; then return 0; fi
  if fetch_url "$RAW_BASE/$rel" "$out"; then return 0; fi
  if [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; then return 0; fi
  if fetch_url "$WEB_BASE/$rel" "$out"; then return 0; fi
  if fetch_url "$BOOTSTRAP_CDN/$rel" "$out"; then return 0; fi
  echo "Tidak dapat mengambil $rel dari source maupun channel fallback." >&2
  return 1
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

core_syntax_ok() {
  python -m py_compile "$ROOT/core/furina_agent/chat.py" "$ROOT/core/furina_agent/version.py" >/dev/null 2>&1
}

rebase_rc52() {
  progress 28 "Memulihkan fondasi Core yang konsisten"
  fetch_rel "$R22_BODY_PATH" "$TMP/runtime-r22.sh"
  verify_blob "$TMP/runtime-r22.sh" "$R22_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/runtime-r22.sh" >>"$LOG" 2>&1
  test "$(core_version)" = "1.0.0-rc52"
  core_syntax_ok
}

fetch_patch_assets() {
  progress 52 "Mengambil Companion Runtime yang diperbaiki"
  fetch_rel "$RC54_APPLY_PATH" "$TMP/apply.py"
  fetch_rel "$STATE_PATH" "$TMP/companion_state_v2.py"
  fetch_rel "$MIND_PATH" "$TMP/mind_v2.py"
  verify_blob "$TMP/apply.py" "$RC54_APPLY_BLOB"
  verify_blob "$TMP/companion_state_v2.py" "$STATE_BLOB"
  verify_blob "$TMP/mind_v2.py" "$MIND_BLOB"
  python -m py_compile "$TMP/apply.py" "$TMP/companion_state_v2.py" "$TMP/mind_v2.py"
}

apply_once() {
  python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1
}

mkdir -p "$ROOT/logs" "$ROOT/data"
: >> "$LOG"
CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]] && core_syntax_ok; then
  progress 100 "Furina Companion Runtime sudah terbaru"
  printf '✓ Furina Core %s · companion runtime r24 aktif.\n' "$VERSION"
  exit 0
fi

# RC54 explicitly supports a clean RC52 and a syntactically valid partial RC53.
# Anything else is normalized first. This is the recovery path for the failed
# RC53 update seen on-device at the previous 66%% activation step.
if [[ "$CURRENT" != "1.0.0-rc52" && "$CURRENT" != "1.0.0-rc53" && "$CURRENT" != "$VERSION" ]]; then
  rebase_rc52
elif ! core_syntax_ok; then
  rebase_rc52
fi

fetch_patch_assets
progress 66 "Mengaktifkan state, learned-self, dan continuity"
if ! apply_once; then
  # Do not leave the user trapped by a partially modified RC53. Rebuild the
  # known-good RC52 code foundation and retry exactly once with the robust patch.
  printf '%s\n' "RC54: patch pertama gagal; melakukan recovery otomatis dari RC52." >>"$LOG"
  rebase_rc52
  progress 70 "Mencoba ulang patch secara aman"
  if ! apply_once; then
    echo "Update companion gagal setelah recovery otomatis. Detail terakhir:" >&2
    tail -n 12 "$LOG" >&2 2>/dev/null || true
    exit 1
  fi
fi

progress 86 "Memvalidasi Core"
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"
python - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
state=(root/"core/furina_agent/companion_state_v2.py").read_text(encoding="utf-8")
mind=(root/"core/furina_agent/mind_v2.py").read_text(encoding="utf-8")
chat=(root/"core/furina_agent/chat.py").read_text(encoding="utf-8")
for item in ("class CompanionStateV2","STATE COMPANION PERSISTEN","BEHAVIOR CONTRACT:"):
    if item not in state: raise SystemExit("RC54 state validation missing: "+item)
if "class FurinaMind" not in mind: raise SystemExit("RC54 mind validation missing")
for item in (
    "LIVING COMPANION STATE:",
    "LEARNED SELF / EXPERIENCE:",
    "self.mind.observe_user_feedback(user_text)",
    "self.companion_state.after_turn(user_text, answer)",
    "self.companion_state.maintenance()",
):
    if item not in chat: raise SystemExit("RC54 chat validation missing: "+item)
PY

progress 95 "Menyimpan revisi runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Companion Runtime siap"
printf '✓ Furina Core %s aktif · recovery patch dan state/mind/continuity siap.\n' "$VERSION"
printf '  FurinaHub memakai Core yang sama; buka ulang percakapan bila proses Core lama masih tersambung.\n'
