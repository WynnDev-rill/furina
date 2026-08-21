#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc62"
DEPENDENCY_REVISION="2026.08.21-r32"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
R31_PATH="overrides/runtime-r31/install-body.sh"
R31_BLOB="333a96066a585dbae38e4ceb6dedb56512d4f90e"
APPLY_PATH="overrides/rc62/apply.py"
APPLY_BLOB="7f3fb20870141c498fb51b3c91d7f6cd36391050"

TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r32-furinahub.log"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
BUNDLE_ID="furina-2026.08.21-rc62-rc50"
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
fetch_url(){ local url="$1" out="$2" api="${3:-0}" code; local args=(-L --silent --show-error --connect-timeout 12 --max-time 180 --retry 3 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/17' -H 'Cache-Control: no-cache'); [[ "$api" == 1 ]] && args+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$out" ]]; }
fetch_rel(){ local rel="$1" out="$2" asset=""; case "$rel" in overrides/runtime-r31/install-body.sh) asset=furina-runtime-r31.sh ;; overrides/rc62/apply.py) asset=core-rc62-apply.py ;; esac; { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; } || fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1 || fetch_url "$RAW_BASE/$rel" "$out" || fetch_url "$WEB_BASE/$rel" "$out"; }
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
d=pathlib.Path(sys.argv[1]).read_bytes(); actual=hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
if actual!=sys.argv[2]: raise SystemExit(f"Integritas file berubah: {actual} != {sys.argv[2]}")
PY
}
acquire_lock(){ mkdir -p "$ROOT/run"; local waited=0 owner=""; while ! mkdir "$LOCKDIR" 2>/dev/null; do owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; if [[ -z "$owner" || ! "$owner" =~ ^[0-9]+$ || ! -d "/proc/$owner" ]]; then rm -rf "$LOCKDIR"; continue; fi; sleep 2; waited=$((waited+2)); (( waited < 900 )) || return 75; done; printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1; }

# Android requires user confirmation for an APK update.  Termux therefore offers
# each signed shared bundle once; APK-originated Core updates never reopen the APK.
sync_furinahub_apk(){
  [[ "$SOURCE" == "termux" ]] || return 0
  local marker="$ROOT/data/furinahub_apk_bundle" manifest="$TMP/bundle.json"
  local out="$HOME/FurinaHub-v1.0.0-rc50.apk" bridge_bundle="" apk_url="" apk_sha=""
  bridge_bundle="$(curl -fsS --connect-timeout 2 --max-time 3 http://127.0.0.1:8765/health 2>/dev/null | python -c 'import json,sys; print(json.load(sys.stdin).get("bundle_id", ""))' 2>/dev/null || true)"
  [[ "$bridge_bundle" == "$BUNDLE_ID" ]] && { printf '%s\n' "$BUNDLE_ID" >"$marker"; return 0; }
  [[ "$(cat "$marker" 2>/dev/null || true)" == "$BUNDLE_ID" ]] && return 0
  fetch_url "$STABLE_RELEASE/bundle.json" "$manifest" || { printf '%s\n' "APK belum disinkronkan: metadata bundle belum tersedia." >>"$LOG"; return 0; }
  read -r apk_url apk_sha < <(python - "$manifest" "$BUNDLE_ID" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m.get('schema') == 1 and m.get('bundle_id') == sys.argv[2]
assert m.get('package_name') == 'com.wynndev.furinaagentbridge'
assert m.get('bridge_version') == '1.0.0-rc50' and int(m.get('bridge_version_code',0)) == 10050
url=str(m.get('apk_url','')); sha=str(m.get('apk_sha256','')).lower()
assert url.startswith('https://github.com/WynnDev-rill/furina/releases/download/') and len(sha) == 64
print(url,sha)
PY
) || { printf '%s\n' "APK belum disinkronkan: metadata bundle tidak valid." >>"$LOG"; return 0; }
  fetch_url "$apk_url" "$TMP/FurinaHub.apk" || { printf '%s\n' "APK belum disinkronkan: unduhan gagal." >>"$LOG"; return 0; }
  echo "$apk_sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null || { printf '%s\n' "APK ditolak: hash tidak cocok." >>"$LOG"; return 0; }
  cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"
  if command -v termux-open >/dev/null 2>&1 && termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1; then
    printf '%s\n' "$BUNDLE_ID" >"$marker"
  else
    printf '%s\n' "APK siap di $out; buka file itu untuk menyelesaikan sinkronisasi." >>"$LOG"
  fi
}

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"; : >"$LOG"; acquire_lock
OLD_VERSION="$(core_version)"; OLD_REVISION="$(revision)"
if [[ "$OLD_VERSION" == "$VERSION" && "$OLD_REVISION" == "$DEPENDENCY_REVISION" ]]; then
  printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"; sync_furinahub_apk
  write_state done no_update done 100 "Tidak ada pembaruan terbaru. Core $VERSION · runtime r32 dan bundle terpadu sudah aktif."
  printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'; exit 0
fi
progress 5 checking "Memeriksa kondisi Core"
if [[ "$OLD_VERSION" != "1.0.0-rc61" && "$OLD_VERSION" != "$VERSION" ]]; then
  progress 12 foundation "Menyiapkan fondasi Core RC61"
  fetch_rel "$R31_PATH" "$TMP/r31.sh"; verify "$TMP/r31.sh" "$R31_BLOB"
  # The outer lock belongs to this process; let the foundation own its own lock.
  rm -rf "$LOCKDIR"; LOCK_OWNED=0
  FURINAHUB_MACHINE_PROGRESS=1 FURINA_UPDATE_SOURCE="$SOURCE" bash "$TMP/r31.sh" >>"$LOG" 2>&1
  acquire_lock
fi
[[ "$(core_version)" == "1.0.0-rc61" || "$(core_version)" == "$VERSION" ]]
progress 28 dependency "Memasang dateparser 1.4.2 resmi"
if ! python -c 'import importlib.metadata as m; raise SystemExit(0 if m.version("dateparser")=="1.4.2" else 1)' >/dev/null 2>&1; then
  python -m pip install --disable-pip-version-check --no-input --upgrade "dateparser==1.4.2" >>"$LOG" 2>&1
fi
python -c 'import dateparser,importlib.metadata as m; assert m.version("dateparser")=="1.4.2"'
progress 42 download "Mengambil Core RC62 dan kontrak bundle"
fetch_rel "$APPLY_PATH" "$TMP/apply.py"; verify "$TMP/apply.py" "$APPLY_BLOB"; python -m py_compile "$TMP/apply.py"
progress 64 apply "Menerapkan dateparser dan status bundle terpadu"
python "$TMP/apply.py" "$ROOT" >>"$LOG" 2>&1
progress 84 validation "Memvalidasi parser waktu dan sinkronisasi versi"
python -m compileall -q "$ROOT/core/furina_agent"; [[ "$(core_version)" == "$VERSION" ]]
python - "$ROOT" <<'PY'
from pathlib import Path
import ast,sys
core=Path(sys.argv[1])/'core/furina_agent'
for name in ('hub.py','prospective.py'): ast.parse((core/name).read_text(encoding='utf-8'))
hub=(core/'hub.py').read_text(encoding='utf-8'); prospective=(core/'prospective.py').read_text(encoding='utf-8')
assert 'bundle_synced' in hub and 'search_dates(' in prospective and 'DATEPARSER_VERSION = "1.4.2"' in prospective
PY
progress 94 commit "Menyimpan runtime r32 dan bundle terpadu"
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"
printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"
chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null || true
progress 97 bridge "Menyinkronkan FurinaHub dengan bundle yang sama"
sync_furinahub_apk
write_state done updated done 100 "Pembaruan berhasil. Core $OLD_VERSION → $VERSION · runtime r32 aktif."
printf 'PROGRESS 100 Pembaruan berhasil\n'
