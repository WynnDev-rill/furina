#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail
VERSION="1.0.0-rc57"
DEPENDENCY_REVISION="2026.08.18-r27"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
R26_PATH="overrides/runtime-r26/install-body.sh"
R26_BLOB="2f10bd04925205898c5b0977e1a90d14fcc7cb80"
LOCK_PATH="upstreams.lock.json"; LOCK_BLOB="fa81a690d5b697194853668ffd035dc9b25ac73c"
VENDOR_PATH="overrides/rc57/vendor-install.sh"; VENDOR_BLOB="f5ed88c9daf9b6b99bbdd34cc86914c8de137e4c"
APPLY_PATH="overrides/rc57/apply.py"; APPLY_BLOB="680522409f6e149027007a4c04ed668f08e92b51"
BRIDGE_PATH="overrides/rc57/upstream_bridge.py"; BRIDGE_BLOB="78638fed17f7f56d99ac8b2b92fcdb979ac9b19e"
SOUL_PATH="overrides/rc57/soul_worker.py"; SOUL_BLOB="cdffe5cf05708d5a791c540c27660764dbfd0549"
UTSUWA_PATH="overrides/rc57/utsuwa_worker.mjs"; UTSUWA_BLOB="ac85c1cfba2c6079e8739edf32a29f82679ea201"
PERSONA_PATH="overrides/rc57/persona.py"; PERSONA_BLOB="848650bdad431a529f6692ca2753791dbf5eab63"
TMP="$(mktemp -d)"; LOG="$ROOT/logs/update-r27-furinahub.log"
trap 'rm -rf "$TMP"' EXIT

progress(){ local p="$1"; shift; if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then printf 'PROGRESS %d %s\n' "$p" "$*"; else printf '[%3d%%] %s\n' "$p" "$*"; fi; }
fetch_url(){ local u="$1" o="$2" api="${3:-0}" code; rm -f "$o"; local a=(-L --silent --show-error --connect-timeout 12 --max-time 120 --retry 3 --retry-delay 2 --retry-all-errors -o "$o" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/10' -H 'Cache-Control: no-cache'); [[ "$api" == 1 ]] && a+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "${a[@]}" "$u" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$o" ]]; }
fetch_rel(){
  local r="$1" o="$2" asset=""
  case "$r" in
    upstreams.lock.json) asset="upstreams.lock.json" ;;
    overrides/runtime-r26/install-body.sh) asset="furina-runtime-r26.sh" ;;
    overrides/rc57/vendor-install.sh) asset="core-rc57-vendor-install.sh" ;;
    overrides/rc57/apply.py) asset="core-rc57-apply.py" ;;
    overrides/rc57/upstream_bridge.py) asset="core-rc57-upstream-bridge.py" ;;
    overrides/rc57/soul_worker.py) asset="core-rc57-soul-worker.py" ;;
    overrides/rc57/utsuwa_worker.mjs) asset="core-rc57-utsuwa-worker.mjs" ;;
    overrides/rc57/persona.py) asset="core-rc57-persona.py" ;;
  esac
  fetch_url "$API_BASE/$r?ref=experiment/furina-agent-termux" "$o" 1 ||
  fetch_url "$RAW_BASE/$r" "$o" ||
  { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$o"; } ||
  fetch_url "$WEB_BASE/$r" "$o"
}
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
d=pathlib.Path(sys.argv[1]).read_bytes(); a=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if a!=sys.argv[2]: raise SystemExit(f"Integritas file berubah: {a} != {sys.argv[2]}")
PY
}
core_version(){ python - "$ROOT/core/furina_agent/version.py" <<'PY'
import re,sys
try:t=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',t); print(m.group(1) if m else 'unknown')
PY
}
mkdir -p "$ROOT/logs" "$ROOT/data"; : >> "$LOG"
CURRENT="$(core_version 2>/dev/null || true)"; REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then progress 100 "Upstream Companion Pack sudah terbaru"; exit 0; fi

if [[ "$CURRENT" != "1.0.0-rc56" && "$CURRENT" != "$VERSION" ]]; then
  progress 12 "Menyiapkan Conversation Runtime RC56"
  fetch_rel "$R26_PATH" "$TMP/r26.sh"; verify "$TMP/r26.sh" "$R26_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/r26.sh" >>"$LOG" 2>&1
fi
test "$(core_version)" = "1.0.0-rc56" || [[ "$(core_version)" == "$VERSION" ]]

progress 30 "Mengambil manifest dan adapter upstream"
for spec in \
 "$LOCK_PATH:$LOCK_BLOB:lock.json" "$VENDOR_PATH:$VENDOR_BLOB:vendor.sh" "$APPLY_PATH:$APPLY_BLOB:apply.py" \
 "$BRIDGE_PATH:$BRIDGE_BLOB:upstream_bridge.py" "$SOUL_PATH:$SOUL_BLOB:soul_worker.py" \
 "$UTSUWA_PATH:$UTSUWA_BLOB:utsuwa_worker.mjs" "$PERSONA_PATH:$PERSONA_BLOB:persona.py"; do
 IFS=: read -r rel blob out <<< "$spec"; fetch_rel "$rel" "$TMP/$out"; verify "$TMP/$out" "$blob"
done
bash -n "$TMP/vendor.sh"; python -m py_compile "$TMP/apply.py" "$TMP/upstream_bridge.py" "$TMP/soul_worker.py" "$TMP/persona.py"

progress 42 "Mengambil source upstream penuh (sekali per versi)"
bash "$TMP/vendor.sh" "$TMP/lock.json" >>"$LOG" 2>&1

if ! command -v node >/dev/null 2>&1; then
  progress 58 "Menyiapkan Node untuk Utsuwa engine"
  pkg install -y nodejs >>"$LOG" 2>&1 || printf '%s\n' 'WARN: Node tidak tersedia; source Utsuwa tetap terpasang, sidecar akan menunggu Node.' >>"$LOG"
fi

progress 70 "Mengaktifkan upstream companion bridge"
python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1

progress 88 "Memvalidasi upstream dan Core"
python -m compileall -q "$ROOT/core/furina_agent"; test "$(core_version)" = "$VERSION"
python - "$ROOT" "$TMP/lock.json" <<'PY'
import json,sys,pathlib
root=pathlib.Path(sys.argv[1]); lock=json.load(open(sys.argv[2]))
for s in lock['sources']:
 m=json.load(open(root/'upstreams/.locks'/f"{s['id']}.json")); assert m['ref']==s['ref'] and m['complete']
 p=root/'upstreams'/s['id']/s['ref']; assert (p/'LICENSE').exists()
 for rel in s['required']: assert (p/rel).exists(), (s['id'],rel)
chat=(root/'core/furina_agent/chat.py').read_text(); assert 'UPSTREAM COMPANION LAYERS:' in chat and 'upstream_bridge.after_turn' in chat
persona=(root/'core/furina_agent/persona.py').read_text(); assert 'Jangan mendeskripsikan dirimu sebagai kode' in persona
print('FURINA_RC57_VENDOR_SMOKE_OK')
PY

progress 96 "Menyimpan revisi upstream runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"; chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Upstream Companion Pack siap"
printf '✓ Furina Core %s · upstream companion runtime r27 aktif.\n' "$VERSION"
printf '  Source penuh Soul of Waifu, Utsuwa, LumiMuse, dan ZeroChat dipin lokal; Soul/Utsuwa terhubung lewat sidecar.\n'
