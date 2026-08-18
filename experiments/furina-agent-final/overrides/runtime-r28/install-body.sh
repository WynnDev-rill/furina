#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc58"
DEPENDENCY_REVISION="2026.08.18-r28"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
R27_PATH="overrides/runtime-r27/install-body.sh"; R27_BLOB="394c75e22b8df660ac2dcf9ecce3989de3c2d088"
LOCK_PATH="upstreams.lock.json"; LOCK_BLOB="fa81a690d5b697194853668ffd035dc9b25ac73c"
VENDOR_PATH="overrides/rc57/vendor-install.sh"; VENDOR_BLOB="f5ed88c9daf9b6b99bbdd34cc86914c8de137e4c"
APPLY_PATH="overrides/rc58/apply.py"; APPLY_BLOB="453ec291aed738157ac504a941614432096704be"
BRIDGE_PATH="overrides/rc58/upstream_bridge.py"; BRIDGE_BLOB="ace3c3c4bc98f7400ef3b183cc508c87ace76111"
LUMI_PATH="overrides/rc58/lumimuse_worker.cjs"; LUMI_BLOB="0fdd60c7b83448a9d954febef123e73cec2c477c"
ZERO_PATH="overrides/rc58/zerochat_worker.py"; ZERO_BLOB="492311a1e8ac0f37a17358fe7866816eb89c338a"
UTSUWA_PATH="overrides/rc58/utsuwa_worker.cjs"; UTSUWA_BLOB="83619ffba46119a58dc994bf7e9e28a1f32db735"
SOUL_PATH="overrides/rc58/soul_worker.py"; SOUL_BLOB="b6caebc1b2f393500f96e78feade2195ad69e14e"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r28-furinahub.log"
TSROOT="$ROOT/upstream-node"
trap 'rm -rf "$TMP"' EXIT

progress(){ local p="$1"; shift; if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then printf 'PROGRESS %d %s\n' "$p" "$*"; else printf '[%3d%%] %s\n' "$p" "$*"; fi; }
fetch_url(){ local u="$1" o="$2" api="${3:-0}" code; rm -f "$o"; local a=(-L --silent --show-error --connect-timeout 12 --max-time 150 --retry 3 --retry-delay 2 --retry-all-errors -o "$o" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/11' -H 'Cache-Control: no-cache'); [[ "$api" == 1 ]] && a+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "${a[@]}" "$u" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$o" ]]; }
fetch_rel(){
  local r="$1" o="$2" asset=""
  case "$r" in
    overrides/runtime-r27/install-body.sh) asset="furina-runtime-r27.sh" ;;
    upstreams.lock.json) asset="upstreams.lock.json" ;;
    overrides/rc57/vendor-install.sh) asset="core-rc57-vendor-install.sh" ;;
    overrides/rc58/apply.py) asset="core-rc58-apply.py" ;;
    overrides/rc58/upstream_bridge.py) asset="core-rc58-upstream-bridge.py" ;;
    overrides/rc58/lumimuse_worker.cjs) asset="core-rc58-lumimuse-worker.cjs" ;;
    overrides/rc58/zerochat_worker.py) asset="core-rc58-zerochat-worker.py" ;;
    overrides/rc58/utsuwa_worker.cjs) asset="core-rc58-utsuwa-worker.cjs" ;;
    overrides/rc58/soul_worker.py) asset="core-rc58-soul-worker.py" ;;
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
if [[ "$CURRENT" == "$VERSION" && "$REVISION" == "$DEPENDENCY_REVISION" ]]; then
  progress 100 "Semua upstream companion runtime sudah aktif"
  printf '✓ Furina Core %s · all-upstream runtime r28 aktif.\n' "$VERSION"
  exit 0
fi

if [[ "$CURRENT" != "1.0.0-rc57" && "$CURRENT" != "$VERSION" ]]; then
  progress 10 "Menyiapkan Upstream Companion Pack RC57"
  fetch_rel "$R27_PATH" "$TMP/r27.sh"; verify "$TMP/r27.sh" "$R27_BLOB"
  FURINAHUB_MACHINE_PROGRESS=0 bash "$TMP/r27.sh" >>"$LOG" 2>&1
fi
test "$(core_version)" = "1.0.0-rc57" || [[ "$(core_version)" == "$VERSION" ]]

progress 26 "Memverifikasi source upstream penuh"
fetch_rel "$LOCK_PATH" "$TMP/lock.json"; verify "$TMP/lock.json" "$LOCK_BLOB"
fetch_rel "$VENDOR_PATH" "$TMP/vendor.sh"; verify "$TMP/vendor.sh" "$VENDOR_BLOB"
bash "$TMP/vendor.sh" "$TMP/lock.json" >>"$LOG" 2>&1

progress 38 "Menyiapkan runtime TypeScript upstream"
command -v node >/dev/null 2>&1 || pkg install -y nodejs >>"$LOG" 2>&1
command -v npm >/dev/null 2>&1 || { echo "npm tidak tersedia setelah instalasi Node.js." >&2; exit 1; }
if ! node -e "require('$TSROOT/node_modules/typescript')" >/dev/null 2>&1; then
  mkdir -p "$TSROOT"
  npm install --prefix "$TSROOT" --no-audit --no-fund --omit=optional typescript@5 >>"$LOG" 2>&1
fi
node -e "const ts=require('$TSROOT/node_modules/typescript'); if(!ts.transpileModule) process.exit(1)"

progress 50 "Mengambil adapter runtime empat upstream"
for spec in \
 "$APPLY_PATH:$APPLY_BLOB:apply.py" "$BRIDGE_PATH:$BRIDGE_BLOB:upstream_bridge.py" \
 "$LUMI_PATH:$LUMI_BLOB:lumimuse_worker.cjs" "$ZERO_PATH:$ZERO_BLOB:zerochat_worker.py" \
 "$UTSUWA_PATH:$UTSUWA_BLOB:utsuwa_worker.cjs" "$SOUL_PATH:$SOUL_BLOB:soul_worker.py"; do
  IFS=: read -r rel blob out <<< "$spec"; fetch_rel "$rel" "$TMP/$out"; verify "$TMP/$out" "$blob"
done
python -m py_compile "$TMP/apply.py" "$TMP/upstream_bridge.py" "$TMP/zerochat_worker.py" "$TMP/soul_worker.py"
node --check "$TMP/lumimuse_worker.cjs"; node --check "$TMP/utsuwa_worker.cjs"

progress 62 "Menjalankan smoke test engine upstream asli"
python - "$TMP/lock.json" "$ROOT" "$TMP" "$TSROOT" <<'PY'
import json,pathlib,subprocess,sys,tempfile
lock=json.load(open(sys.argv[1])); root=pathlib.Path(sys.argv[2]); tmp=pathlib.Path(sys.argv[3]); tsroot=sys.argv[4]
refs={s['id']:s['ref'] for s in lock['sources']}
def src(i): return root/'upstreams'/i/refs[i]
# LumiMuse original memory-retrieval.ts through its native TS source.
lumi={"upstream":str(src('lumimuse')),"typescript_root":tsroot,"query":"aku suka kopi","token_budget":600,"final_top_k":6,"memories":[{"id":"m1","character_id":"furina","category":"偏好习惯","content":"User suka kopi tanpa gula","confidence":0.9,"tags":["kopi"],"source_msg_ids":[],"memory_kind":"user_preference","importance":0.8,"emotional_weight":0.4,"status":"active","pinned":False,"usage_count":1,"created_at":"2026-08-01T00:00:00+00:00","updated_at":"2026-08-01T00:00:00+00:00"}],"priority_memories":[]}
p=subprocess.run(['node',str(tmp/'lumimuse_worker.cjs')],input=json.dumps(lumi),text=True,capture_output=True,timeout=20); assert p.returncode==0,p.stderr; lr=json.loads(p.stdout); assert lr['ok'] and 'kopi' in lr['text'].lower(),lr
# Utsuwa original state-updates.ts.
uts={"upstream":str(src('utsuwa')),"typescript_root":tsroot,"state":{"energy":80,"affection":100,"trust":50,"intimacy":30,"comfort":50,"respect":50,"mood":{"primary":"neutral","intensity":30,"causes":[]},"lastInteraction":"2026-08-18T00:00:00+00:00"},"hours_since":2,"sentiment":0.8,"topic_depth":"moderate","is_emotional":True,"is_question":False}
p=subprocess.run(['node',str(tmp/'utsuwa_worker.cjs')],input=json.dumps(uts),text=True,capture_output=True,timeout=20); assert p.returncode==0,p.stderr; ur=json.loads(p.stdout); assert 'impact' in ur and 'decay' in ur,ur
# ZeroChat original memory_service.py, no summary LLM needed in this smoke.
with tempfile.TemporaryDirectory() as d:
 req={"op":"update","upstream":str(src('zerochat')),"data_root":d,"role_id":"furina","user_text":"halo","answer":"hm","allow_summary":False}
 p=subprocess.run([sys.executable,str(tmp/'zerochat_worker.py')],input=json.dumps(req)+'\n',text=True,capture_output=True,timeout=20); assert p.returncode==0,p.stderr; event=json.loads(p.stdout.strip().splitlines()[-1]); assert event['event']=='done' and event['short_term_count']==2,event
# Soul original SoulMemoryAgent can load and expose empty context without LLM.
with tempfile.TemporaryDirectory() as d:
 req={"op":"context","upstream":str(src('soul_of_waifu')),"data_root":d,"mode":1,"batch":4,"character":"Furina","user":"Wynn","chat_id":"default"}
 p=subprocess.run([sys.executable,str(tmp/'soul_worker.py')],input=json.dumps(req)+'\n',text=True,capture_output=True,timeout=20); assert p.returncode==0,p.stderr; event=json.loads(p.stdout.strip().splitlines()[-1]); assert event['event']=='done',event
print('FURINA_RC58_FOUR_UPSTREAM_SMOKE_OK')
PY

progress 76 "Mengaktifkan semua upstream runtime"
python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1

progress 90 "Memvalidasi Core"
python -m compileall -q "$ROOT/core/furina_agent"
test "$(core_version)" = "$VERSION"
python - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); core=root/'core/furina_agent'; runtime=core/'upstream_runtime'
chat=(core/'chat.py').read_text(); bridge=(core/'upstream_bridge.py').read_text()
assert 'self.upstream_bridge.context(user_text)' in chat
for marker in ('_lumimuse_context','_run_zerochat','_run_utsuwa','_run_soul'): assert marker in bridge,marker
for name in ('lumimuse_worker.cjs','zerochat_worker.py','utsuwa_worker.cjs','soul_worker.py'): assert (runtime/name).is_file(),name
print('FURINA_RC58_CORE_SMOKE_OK')
PY

progress 97 "Menyimpan revisi runtime"
printf '%s\n' "$DEPENDENCY_REVISION" > "$ROOT/data/dependency_revision"; chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
progress 100 "Semua upstream companion runtime siap"
printf '✓ Furina Core %s · all-upstream runtime r28 aktif.\n' "$VERSION"
printf '  Soul of Waifu + Utsuwa + LumiMuse + ZeroChat kini dieksekusi dari source upstream yang dipin.\n'
