#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc61"
DEPENDENCY_REVISION="2026.08.21-r31"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
R30_PATH="overrides/runtime-r30/install-body.sh"
R30_BLOB="61d0650b238173a55dd10dd2b979b595c063b010"
APPLY_PATH="overrides/rc61/apply.py"
APPLY_BLOB="3992cdc9bf7da0f4269c8a9e0f35d6946ef5113e"

TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r31-furinahub.log"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
STAGE="checking"
PERCENT=0
LOCK_OWNED=0

if [[ ! -t 1 && -z "${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then export FURINAHUB_MACHINE_PROGRESS=1; fi
core_version(){ python - "$ROOT/core/furina_agent/version.py" <<'PY' 2>/dev/null || true
import re,sys
try: text=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text); print(m.group(1) if m else 'unknown')
PY
}
revision(){ cat "$ROOT/data/dependency_revision" 2>/dev/null || true; }
write_state(){
  local state="$1" result="$2" stage="$3" percent="$4" message="$5" installed rev
  installed="$(core_version)"; rev="$(revision)"; mkdir -p "$ROOT/run"
  python - "$STATUS_PATH" "$state" "$result" "$stage" "$percent" "$message" "$SOURCE" "$VERSION" "$DEPENDENCY_REVISION" "$installed" "$rev" <<'PY' >/dev/null 2>&1 || true
import json,os,pathlib,sys,time
(path,state,result,stage,percent,message,source,target,target_rev,installed,revision)=sys.argv[1:]
p=pathlib.Path(path); p.parent.mkdir(parents=True,exist_ok=True)
obj={'schema':2,'state':state,'result':result,'stage':stage,'percent':int(percent),'message':message,'source':source,'target_version':target,'target_revision':target_rev,'installed_core_version':installed,'dependency_revision':revision,'updated_at':time.time(),'restart_required':state=='done' and installed!=target}
if state in ('starting','running'): obj['started_at']=time.time()
if state in ('done','error'): obj['finished_at']=time.time()
t=p.with_name(p.name+'.new'); t.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8'); os.chmod(t,0o600); os.replace(t,p)
PY
}
progress(){ PERCENT="$1"; STAGE="$2"; shift 2; local message="$*"; write_state running "" "$STAGE" "$PERCENT" "$message"; printf 'PROGRESS %d %s\n' "$PERCENT" "$message"; }
cleanup(){ if [[ "$LOCK_OWNED" == 1 && -d "$LOCKDIR" && "$(cat "$LOCKDIR/pid" 2>/dev/null || true)" == "$$" ]]; then rm -rf "$LOCKDIR"; fi; rm -rf "$TMP"; }
failure(){ local code=$? detail=""; trap - ERR; detail="$(tail -n 20 "$LOG" 2>/dev/null | awk 'NF{line=$0} END{print line}' | cut -c1-220)"; [[ -n "$detail" ]] || detail="proses berhenti dengan kode $code"; write_state error error "$STAGE" "$PERCENT" "Pembaruan gagal pada tahap $STAGE: $detail"; printf 'ERROR %s %s\n' "$STAGE" "$detail" >&2; exit "$code"; }
trap cleanup EXIT
trap failure ERR
fetch_url(){ local url="$1" out="$2" api="${3:-0}" code; local args=(-L --silent --show-error --connect-timeout 12 --max-time 180 --retry 3 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/16' -H 'Cache-Control: no-cache'); [[ "$api" == 1 ]] && args+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$out" ]]; }
fetch_rel(){ local rel="$1" out="$2" asset=""; case "$rel" in overrides/runtime-r30/install-body.sh) asset=furina-runtime-r30.sh ;; overrides/rc61/apply.py) asset=core-rc61-apply.py ;; esac; fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1 || fetch_url "$RAW_BASE/$rel" "$out" || { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; } || fetch_url "$WEB_BASE/$rel" "$out"; }
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
d=pathlib.Path(sys.argv[1]).read_bytes(); actual=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if actual!=sys.argv[2]: raise SystemExit(f"Integritas file berubah: {actual} != {sys.argv[2]}")
PY
}
acquire_lock(){ mkdir -p "$ROOT/run"; local waited=0 owner=""; while ! mkdir "$LOCKDIR" 2>/dev/null; do owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; if [[ -z "$owner" || ! "$owner" =~ ^[0-9]+$ || ! -d "/proc/$owner" ]]; then rm -rf "$LOCKDIR"; continue; fi; sleep 2; waited=$((waited+2)); (( waited < 900 )) || return 75; done; printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1; }

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"; : >"$LOG"; acquire_lock
OLD_VERSION="$(core_version)"; OLD_REVISION="$(revision)"
if [[ "$OLD_VERSION" == "$VERSION" && "$OLD_REVISION" == "$DEPENDENCY_REVISION" ]]; then write_state done no_update done 100 "Tidak ada pembaruan terbaru. Core $VERSION · runtime r31 sudah aktif."; printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'; exit 0; fi
progress 5 checking "Memeriksa kondisi Core"
if [[ "$OLD_VERSION" != "1.0.0-rc60" && "$OLD_VERSION" != "$VERSION" ]]; then
  progress 12 foundation "Menyiapkan fondasi Core RC60"
  fetch_rel "$R30_PATH" "$TMP/r30.sh"; verify "$TMP/r30.sh" "$R30_BLOB"
  # The outer lock belongs to this process; let the foundation own its own lock.
  rm -rf "$LOCKDIR"; LOCK_OWNED=0
  FURINAHUB_MACHINE_PROGRESS=1 FURINA_UPDATE_SOURCE="$SOURCE" bash "$TMP/r30.sh" >>"$LOG" 2>&1
  acquire_lock
fi
[[ "$(core_version)" == "1.0.0-rc60" || "$(core_version)" == "$VERSION" ]]
progress 36 download "Mengambil pipeline efisien RC61"
fetch_rel "$APPLY_PATH" "$TMP/apply.py"; verify "$TMP/apply.py" "$APPLY_BLOB"; python -m py_compile "$TMP/apply.py"
progress 62 apply "Menerapkan efisiensi tanpa membuang konteks"
python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1
progress 84 validation "Memvalidasi Core, antrean, dan watchdog"
python -m compileall -q "$ROOT/core/furina_agent"; [[ "$(core_version)" == "$VERSION" ]]
python - "$ROOT" <<'PY'
from pathlib import Path
import ast,sys
core=Path(sys.argv[1])/'core/furina_agent'
for name in ('hub.py','chat.py','upstream_bridge.py'): ast.parse((core/name).read_text(encoding='utf-8'))
hub=(core/'hub.py').read_text(encoding='utf-8'); assert 'updater melewati batas waktu 25 menit' in hub and 'headers["Range"]' in hub
PY
progress 94 commit "Menyimpan runtime r31"
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"; chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
write_state done updated done 100 "Pembaruan berhasil. Core $OLD_VERSION → $VERSION · runtime r31 aktif."
printf 'PROGRESS 100 Pembaruan berhasil\n'
