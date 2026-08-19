#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc60"
DEPENDENCY_REVISION="2026.08.18-r30"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
R29_PATH="overrides/runtime-r29/install-body.sh"
R29_BLOB="37852141f012b66d7350e25ea3b5fa4389444745"
APPLY_PATH="overrides/rc60/apply.py"
APPLY_BLOB="4895f1c1da600bd53a5b4b449feee0883ad2161f"

TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r30-furinahub.log"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
CURRENT_STAGE="checking"
CURRENT_PERCENT=0
OLD_VERSION=""
OLD_REVISION=""
LOCK_OWNED=0
UI_DRAWN=0
UI_LINES=5

if [[ ! -t 1 && -z "${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then
  export FURINAHUB_MACHINE_PROGRESS=1
fi

is_tty(){ [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" != "1" && -t 1 && "${TERM:-dumb}" != "dumb" ]]; }
core_version(){
  python - "$ROOT/core/furina_agent/version.py" <<'PY' 2>/dev/null || true
import re,sys
try: text=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing'); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text)
print(m.group(1) if m else 'unknown')
PY
}
revision(){ cat "$ROOT/data/dependency_revision" 2>/dev/null || true; }

write_state(){
  local state="$1" result="$2" stage="$3" percent="$4" message="$5" installed rev
  installed="$(core_version)"; rev="$(revision)"
  mkdir -p "$ROOT/run"
  python - "$STATUS_PATH" "$state" "$result" "$stage" "$percent" "$message" "$SOURCE" "$VERSION" "$DEPENDENCY_REVISION" "$installed" "$rev" <<'PY' >/dev/null 2>&1 || true
import json,os,pathlib,sys,time
(path,state,result,stage,percent,message,source,target,target_rev,installed,revision)=sys.argv[1:]
p=pathlib.Path(path); p.parent.mkdir(parents=True,exist_ok=True)
obj={
  'schema':2,'state':state,'result':result,'stage':stage,'percent':int(percent),
  'message':message,'source':source,'target_version':target,'target_revision':target_rev,
  'installed_core_version':installed,'dependency_revision':revision,
  'updated_at':time.time(),'restart_required':False,
}
old={}
try:
  old=json.loads(p.read_text(encoding='utf-8'))
  if isinstance(old,dict):
    for key in ('started_at','from_version','from_revision'):
      if key in old: obj[key]=old[key]
except Exception: pass
if state in ('starting','running') and 'started_at' not in obj: obj['started_at']=time.time()
if state in ('done','error'): obj['finished_at']=time.time()
t=p.with_name(p.name+'.new'); t.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8'); os.chmod(t,0o600); os.replace(t,p)
PY
}

repeat_char(){ local n="$1" ch="$2" out="" i; for ((i=0;i<n;i++)); do out+="$ch"; done; printf '%s' "$out"; }
fit_text(){ local text="$1" width="$2"; text="${text//$'\n'/ }"; if (( ${#text} > width )); then text="${text:0:$((width-3))}..."; fi; printf '%-*s' "$width" "$text"; }
render_panel(){
  local pct="$1" msg="$2" cols width inner barw fill empty bar="" i line info status
  cols="$(tput cols 2>/dev/null || printf '72')"; [[ "$cols" =~ ^[0-9]+$ ]] || cols=72
  width=$((cols-2)); (( width > 58 )) && width=58; (( width < 38 )) && width=38
  inner=$((width-2)); barw=$((inner-9)); (( barw > 28 )) && barw=28; (( barw < 14 )) && barw=14
  fill=$((pct*barw/100)); empty=$((barw-fill)); for ((i=0;i<fill;i++)); do bar+="█"; done; for ((i=0;i<empty;i++)); do bar+="·"; done
  line="$(repeat_char "$inner" '─')"; info="Core $VERSION · runtime r30"; status="[$bar] $(printf '%3d' "$pct")%"
  if (( UI_DRAWN == 1 )); then printf '\033[%dA' "$UI_LINES"; fi
  printf '\r\033[2K\033[38;5;45m╭%s╮\033[0m\n' "$line"
  printf '\r\033[2K\033[38;5;45m│\033[0m \033[38;5;45mFURINA\033[0m \033[38;5;213m/ UPDATE\033[0m%*s\033[38;5;45m│\033[0m\n' "$((inner-15))" ''
  printf '\r\033[2K\033[38;5;45m│\033[0m %s \033[38;5;45m│\033[0m\n' "$(fit_text "$status  $msg" "$((inner-2))")"
  printf '\r\033[2K\033[38;5;45m│\033[0m \033[38;5;244m%s\033[0m \033[38;5;45m│\033[0m\n' "$(fit_text "$info" "$((inner-2))")"
  printf '\r\033[2K\033[38;5;45m╰%s╯\033[0m\n' "$line"; UI_DRAWN=1
}
progress(){ local p="$1" stage="$2"; shift 2; local msg="$*"; CURRENT_PERCENT="$p"; CURRENT_STAGE="$stage"; write_state "running" "" "$stage" "$p" "$msg"; if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then printf 'PROGRESS %d %s\n' "$p" "$msg"; elif is_tty; then render_panel "$p" "$msg"; else printf '[%3d%%] %s\n' "$p" "$msg"; fi; }
cleanup(){ if [[ "$LOCK_OWNED" == "1" && -d "$LOCKDIR" ]]; then local owner=""; owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; [[ "$owner" == "$$" ]] && rm -rf "$LOCKDIR"; fi; rm -rf "$TMP"; }
trap cleanup EXIT
failure_detail(){ if [[ -s "$LOG" ]]; then tail -n 30 "$LOG" | sed -E 's/\x1B\[[0-9;]*[[:alpha:]]//g' | awk 'NF{line=$0} END{print line}' | cut -c1-220; fi; }
fail(){ local code=$? detail; trap - ERR; detail="$(failure_detail)"; [[ -n "$detail" ]] || detail="proses berhenti dengan kode $code"; write_state "error" "error" "$CURRENT_STAGE" "$CURRENT_PERCENT" "Pembaruan gagal pada tahap $CURRENT_STAGE: $detail"; if is_tty; then render_panel "$CURRENT_PERCENT" "Gagal · $CURRENT_STAGE"; printf '\n\033[38;5;203m✗ Pembaruan gagal\033[0m pada tahap \033[1m%s\033[0m.\n' "$CURRENT_STAGE" >&2; printf '  %s\n' "$detail" >&2; else printf 'ERROR %s %s\n' "$CURRENT_STAGE" "$detail" >&2; fi; printf 'Log: tail -n 60 %q\n' "$LOG" >&2; exit "$code"; }
trap fail ERR
fetch_url(){ local u="$1" o="$2" api="${3:-0}" code; rm -f "$o"; local a=(-L --silent --show-error --connect-timeout 12 --max-time 180 --retry 3 --retry-delay 2 --retry-all-errors -o "$o" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/15' -H 'Cache-Control: no-cache'); [[ "$api" == "1" ]] && a+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "${a[@]}" "$u" 2>/dev/null || true)"; [[ "$code" == "200" && -s "$o" ]]; }
fetch_rel(){ local r="$1" o="$2" asset=""; case "$r" in overrides/runtime-r29/install-body.sh) asset="furina-runtime-r29.sh" ;; overrides/rc60/apply.py) asset="core-rc60-apply.py" ;; esac; fetch_url "$API_BASE/$r?ref=experiment/furina-agent-termux" "$o" 1 || fetch_url "$RAW_BASE/$r" "$o" || { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$o"; } || fetch_url "$WEB_BASE/$r" "$o"; }
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
d=pathlib.Path(sys.argv[1]).read_bytes(); actual=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if actual!=sys.argv[2]: raise SystemExit(f"Integritas file berubah: {actual} != {sys.argv[2]}")
PY
}
acquire_lock(){ mkdir -p "$ROOT/run"; local waited=0 owner=""; while ! mkdir "$LOCKDIR" 2>/dev/null; do owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; if [[ -z "$owner" || ! "$owner" =~ ^[0-9]+$ || ! -d "/proc/$owner" ]]; then rm -rf "$LOCKDIR"; continue; fi; progress 1 "waiting" "Updater lain sedang berjalan · menunggu"; sleep 2; waited=$((waited+2)); if (( waited >= 900 )); then echo "Updater lain masih aktif (pid $owner)." >>"$LOG"; return 75; fi; done; printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1; }

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"; : >"$LOG"; acquire_lock
OLD_VERSION="$(core_version)"; OLD_REVISION="$(revision)"
if [[ "$OLD_VERSION" == "$VERSION" && "$OLD_REVISION" == "$DEPENDENCY_REVISION" ]]; then write_state "done" "no_update" "done" 100 "Tidak ada pembaruan terbaru. Core $VERSION · runtime r30 sudah aktif."; if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'; else render_panel 100 "Tidak ada pembaruan terbaru"; fi; printf '\n✓ Tidak ada pembaruan terbaru.\n  Core %s · runtime r30 sudah aktif.\n' "$VERSION"; exit 0; fi
progress 4 "checking" "Memeriksa kondisi Core"
if [[ "$OLD_VERSION" != "1.0.0-rc59" && "$OLD_VERSION" != "$VERSION" ]]; then progress 8 "foundation" "Menyiapkan fondasi kompatibel"; fetch_rel "$R29_PATH" "$TMP/r29.sh"; verify "$TMP/r29.sh" "$R29_BLOB"; FURINAHUB_MACHINE_PROGRESS=1 FURINA_UPDATE_SOURCE="$SOURCE" bash "$TMP/r29.sh" >>"$LOG" 2>&1; fi
[[ "$(core_version)" == "1.0.0-rc59" || "$(core_version)" == "$VERSION" ]]
progress 34 "download" "Mengambil Unified Update Runtime"; fetch_rel "$APPLY_PATH" "$TMP/apply.py"; verify "$TMP/apply.py" "$APPLY_BLOB"; python -m py_compile "$TMP/apply.py"
progress 58 "apply" "Menyatukan status Termux dan FurinaHub"; python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1
progress 78 "validation" "Memvalidasi Core dan update state"; python -m compileall -q "$ROOT/core/furina_agent"; [[ "$(core_version)" == "$VERSION" ]]
python - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); core=root/'core/furina_agent'; hub=(core/'hub.py').read_text(encoding='utf-8')
for item in ('def _disk_update_versions','Disk state is authoritative','FURINA_UPDATE_SOURCE','EXPECTED_DEPENDENCY_REVISION = "2026.08.18-r30"'): assert item in hub,item
compile(hub,str(core/'hub.py'),'exec'); print('FURINA_RC60_UNIFIED_UPDATE_SMOKE_OK')
PY
progress 92 "commit" "Menyimpan revisi runtime"; printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"; chmod 600 "$ROOT/data/dependency_revision" 2>/dev/null || true
write_state "done" "updated" "done" 100 "Pembaruan berhasil. Core $OLD_VERSION → $VERSION · runtime r30 aktif."
if [[ "${FURINAHUB_MACHINE_PROGRESS:-0}" == "1" ]]; then printf 'PROGRESS 100 Pembaruan berhasil\n'; else render_panel 100 "Pembaruan berhasil"; fi
printf '\n✓ Pembaruan berhasil.\n  Core %s → %s · runtime r30 aktif.\n' "$OLD_VERSION" "$VERSION"
