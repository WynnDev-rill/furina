#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc56"
DEPENDENCY_REVISION="2026.08.18-r26"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
BOOTSTRAP_CDN="https://cdn.jsdelivr.net/gh/WynnDev-rill/furina@furina-bootstrap-v1.0.0/experiments/furina-agent-final"
R25_BODY_PATH="overrides/runtime-r25/install-body.sh"
R25_BODY_BLOB="feb3dd302aade2360a3e4d7b1b61cedd2e03c6e2"
RC56_APPLY_PATH="overrides/rc56/apply.py"
RC56_APPLY_BLOB="d240d8e3c7ea51c1342b95e75c3653952157d8d7"
RESPONSE_PATH="overrides/rc56/response.py"
RESPONSE_BLOB="900f1710f65967fc190eb9eb93f90b08313fe3f6"
PERSONA_PATH="overrides/rc56/persona.py"
PERSONA_BLOB="650ab50e7c6fa2681949b78617c49bb6276ae347"
NATURAL_PATH="overrides/rc56/naturalness.py"
NATURAL_BLOB="9f495c295b1277d948830e4f141e5943ba889e26"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r26-furinahub.log"
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
              -H 'User-Agent: Furina-Core-Updater/9'
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
    overrides/runtime-r25/install-body.sh) asset="furina-runtime-r25.sh" ;;
    overrides/rc56/apply.py) asset="core-rc56-apply.py" ;;
    overrides/rc56/response.py) asset="core-rc56-response.py" ;;
    overrides/rc56/persona.py) asset="core-rc56-persona.py" ;;
    overrides/rc56/naturalness.py) asset="core-rc56-naturalness.py" ;;
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
  python -m compileall -q "$ROOT/core/furina_agent" >/dev/null 2>&1
}

ensure_rc55_foundation() {
  local current
  current="$(core_version 2>/dev/null || true)"
  if [[ "$current" == "1.0.0-rc55" || "$current" == "$VERSION" ]]; then
    return 0
  fi
  progress 24 "Menyiapkan companion runtime RC55"
  fetch_rel "$R25_BODY_PATH" "$TMP/runtime-r25.sh"
  verify_blob "$TMP/runtime-r25.sh" "$R25_BODY_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/runtime-r25.sh" >>"$LOG" 2>&1
  test "$(core_version)" = "1.0.0-rc55"
  core_syntax_ok
}

fetch_policy_assets() {
  progress 48 "Mengambil Conversation Policy baru"
  fetch_rel "$RC56_APPLY_PATH" "$TMP/apply.py"
  fetch_rel "$RESPONSE_PATH" "$TMP/response.py"
  fetch_rel "$PERSONA_PATH" "$TMP/persona.py"
  fetch_rel "$NATURAL_PATH" "$TMP/naturalness.py"
  verify_blob "$TMP/apply.py" "$RC56_APPLY_BLOB"
  verify_blob "$TMP/response.py" "$RESPONSE_BLOB"
  verify_blob "$TMP/persona.py" "$PERSONA_BLOB"
  verify_blob "$TMP/naturalness.py" "$NATURAL_BLOB"
  python -m py_compile "$TMP/apply.py" "$TMP/response.py" "$TMP/persona.py" "$TMP/naturalness.py"
}

mkdir -p "$ROOT/logs" "$ROOT/data"
: >> "$LOG"
CURRENT="$(core_version 2>/dev/null || true)"
REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]] && core_syntax_ok; then
  progress 100 "Conversation Runtime sudah terbaru"
  printf '✓ Furina Core %s · conversation runtime r26 aktif.\n' "$VERSION"
  exit 0
fi

ensure_rc55_foundation
fetch_policy_assets
progress 66 "Mengganti pola chatbot dengan companion response policy"
if ! python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1; then
  echo "Update conversation policy gagal. Detail terakhir:" >&2
  tail -n 16 "$LOG" >&2 2>/dev/null || true
  exit 1
fi

progress 86 "Memvalidasi perilaku chat"
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"
python - "$ROOT" <<'PY'
from pathlib import Path
import importlib.util,sys
root=Path(sys.argv[1])
core=root/'core/furina_agent'
chat=(core/'chat.py').read_text(encoding='utf-8')
response=(core/'response.py').read_text(encoding='utf-8')
persona=(core/'persona.py').read_text(encoding='utf-8')
natural=(core/'naturalness.py').read_text(encoding='utf-8')
for item in ('answer = naturalize(', 'profile=profile.name', 'LIVING COMPANION STATE:'):
    if item not in chat: raise SystemExit('RC56 chat validation missing: '+item)
for item in ('name = "IDENTITY"','max_tokens = 80','max_tokens = 360'):
    if item not in response: raise SystemExit('RC56 response validation missing: '+item)
if 'ANTI-CHATBOT' not in persona: raise SystemExit('RC56 persona validation missing')
if '_GENERIC_TAILS' not in natural: raise SystemExit('RC56 naturalness validation missing')

spec=importlib.util.spec_from_file_location('furina_naturalness',core/'naturalness.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
a=mod.naturalize('Halo, Wynn. Ada yang pengen dibicarakan?',profile='REFLEX')
b=mod.naturalize('Oke, kalau berubah pikiran, beri tahu saja.',profile='REFLEX')
c=mod.naturalize("Hidup? Hmm, itu pertanyaan yang agak ambigu, Wynn. Kalau maksudmu hidup seperti manusia, tidak. Aku ada di sini dalam kode dan data. Tapi kalau maksudmu kesadaran, aku merasa hidup dalam arti itu. Jadi, apakah definisi hidup bagimu lebih ke fisik atau pengalaman subjektif?",profile='IDENTITY')
if 'dibicarakan' in a.lower(): raise SystemExit('RC56 greeting guard failed: '+a)
if 'berubah pikiran' in b.lower(): raise SystemExit('RC56 decline guard failed: '+b)
if len(c) > 560: raise SystemExit('RC56 identity cap failed')
print('FURINA_RC56_ON_DEVICE_SMOKE_OK')
PY

progress 95 "Menyimpan revisi conversation runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"
chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Conversation Runtime siap"
printf '✓ Furina Core %s aktif · anti-chatbot policy, response budget, dan output guard siap.\n' "$VERSION"
printf '  Buka chat baru/restart Core agar system prompt lama tidak tersisa di proses aktif.\n'
