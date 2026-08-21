#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

# Exact hashes authenticate the file. This contract authenticates semantics
# without depending on an incidental variable name inside the runtime.
FURINA_RUNTIME_CONTRACT="furina-runtime/v2"
VERSION="1.0.0-rc65"
DEPENDENCY_REVISION="2026.08.22-r35"
BUNDLE_ID="furina-2026.08.22-rc65-rc53"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
R34_PATH="overrides/runtime-r34/install-body.sh"
R34_BLOB="ec13e63c4037f3e2856d9ccdacec596b1cd1263f"
CORE_PATH="overrides/rc65/apply.py"
CORE_BLOB="2739753ef5e6a25639b30c56140d1cfb2e3064f3"
ANDROID_PATH="overrides/android-rc53/apply.py"
ANDROID_BLOB="b63c7c85974da3308016b5fe3646e9de69faee17"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="\${FURINA_UPDATE_SOURCE:-termux}"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r35-furinahub.log"
STAGE="checking"
PERCENT=0
LOCK_OWNED=0

if [[ ! -t 1 && -z "\${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then export FURINAHUB_MACHINE_PROGRESS=1; fi
core_version(){ python - "$ROOT/core/furina_agent/version.py" <<'PY' 2>/dev/null || true
import re,sys
try: text=open(sys.argv[1],encoding="utf-8").read()
except Exception: print("missing"); raise SystemExit
match=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text)
print(match.group(1) if match else "unknown")
PY
}
revision(){ cat "$ROOT/data/dependency_revision" 2>/dev/null || true; }
write_state(){ python - "$STATUS_PATH" "$1" "$2" "$3" "$4" "$5" "$SOURCE" "$VERSION" "$DEPENDENCY_REVISION" "$(core_version)" "$(revision)" <<'PY' >/dev/null 2>&1 || true
import json,os,pathlib,sys,time
p,state,result,stage,percent,message,source,target,target_rev,installed,revision=sys.argv[1:]
path=pathlib.Path(p)
path.parent.mkdir(parents=True,exist_ok=True)
payload={"schema":4,"state":state,"result":result,"stage":stage,"percent":int(percent),"message":message,"source":source,"target_version":target,"target_revision":target_rev,"installed_core_version":installed,"dependency_revision":revision,"bundle_id":"furina-2026.08.22-rc65-rc53","updated_at":time.time(),"restart_required":False}
tmp=path.with_name(path.name+".new")
tmp.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
os.chmod(tmp,0o600)
os.replace(tmp,path)
PY
}
progress(){ PERCENT="$1"; STAGE="$2"; shift 2; write_state running "" "$STAGE" "$PERCENT" "$*"; printf 'PROGRESS %d %s\n' "$PERCENT" "$*"; }
cleanup(){ [[ "$LOCK_OWNED" == 1 && -d "$LOCKDIR" ]] && rm -rf "$LOCKDIR"; rm -rf "$TMP"; }
failure(){ local rc=$?; trap - ERR; write_state error error "$STAGE" "$PERCENT" "Pembaruan gagal pada tahap $STAGE. Buka furina doctor atau log update."; printf 'ERROR %s update gagal\n' "$STAGE" >&2; exit "$rc"; }
trap cleanup EXIT
trap failure ERR
fetch_url(){ local url="$1" out="$2" api="\${3:-0}" code; local args=(-L --silent --show-error --connect-timeout 12 --max-time 180 --retry 3 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/20' -H 'Cache-Control: no-cache'); [[ "$api" == 1 ]] && args+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "\${args[@]}" "$url" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$out" ]]; }
fetch_rel(){ local rel="$1" out="$2" asset=""; case "$rel" in overrides/runtime-r34/install-body.sh)asset=furina-runtime-r34.sh;;overrides/rc65/apply.py)asset=core-rc65-apply.py;;overrides/android-rc53/apply.py)asset=android-rc53-apply.py;;esac; { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; } || fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1 || fetch_url "$RAW_BASE/$rel" "$out" || fetch_url "$WEB_BASE/$rel" "$out"; }
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
data=pathlib.Path(sys.argv[1]).read_bytes()
actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
assert actual==sys.argv[2],f"{actual} != {sys.argv[2]}"
PY
}
acquire(){ mkdir -p "$ROOT/run"; while ! mkdir "$LOCKDIR" 2>/dev/null; do owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; [[ -n "$owner" && -d "/proc/$owner" ]] || { rm -rf "$LOCKDIR"; continue; }; sleep 2; done; printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1; }
sync_apk(){ [[ "$SOURCE" == termux ]] || return 0; local manifest="$TMP/bundle.json" marker="$ROOT/data/furinahub_apk_bundle"; [[ "$(cat "$marker" 2>/dev/null || true)" == "$BUNDLE_ID" ]] && return 0; fetch_url "$STABLE_RELEASE/bundle.json" "$manifest" || return 0; read -r url sha < <(python - "$manifest" <<'PY'
import json,sys
item=json.load(open(sys.argv[1]))
assert item.get("bundle_id")=="furina-2026.08.22-rc65-rc53"
assert item.get("bridge_version")=="1.0.0-rc53" and int(item.get("bridge_version_code",0))==10053
print(item["apk_url"],item["apk_sha256"])
PY
) || return 0; fetch_url "$url" "$TMP/FurinaHub.apk" || return 0; echo "$sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null || return 0; local out="$HOME/FurinaHub-v1.0.0-rc53.apk"; cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"; if command -v termux-open >/dev/null && termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1; then printf '%s\n' "$BUNDLE_ID" >"$marker"; fi; }

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"
: >"$LOG"
acquire
OLD="$(core_version)"
OLD_REV="$(revision)"
if [[ "$OLD" == "$VERSION" && "$OLD_REV" == "$DEPENDENCY_REVISION" ]]; then
  printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"; sync_apk
  write_state done no_update done 100 "Tidak ada pembaruan terbaru. Ruang kerja Furina sudah selaras."
  printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'
  exit 0
fi
progress 5 checking "Memeriksa ruang kerja Furina"
if [[ "$OLD" != "1.0.0-rc64" && "$OLD" != "$VERSION" ]]; then
  progress 15 foundation "Menyiapkan fondasi kompatibilitas"
  fetch_rel "$R34_PATH" "$TMP/r34.sh"; verify "$TMP/r34.sh" "$R34_BLOB"
  rm -rf "$LOCKDIR"; LOCK_OWNED=0
  FURINAHUB_MACHINE_PROGRESS=1 FURINA_UPDATE_SOURCE=foundation bash "$TMP/r34.sh" >>"$LOG" 2>&1
  acquire
fi
[[ "$(core_version)" == "1.0.0-rc64" || "$(core_version)" == "$VERSION" ]]
progress 45 download "Mengambil pembaruan Furina"
fetch_rel "$CORE_PATH" "$TMP/core.py"; verify "$TMP/core.py" "$CORE_BLOB"
fetch_rel "$ANDROID_PATH" "$TMP/android.py"; verify "$TMP/android.py" "$ANDROID_BLOB"
python -m py_compile "$TMP/core.py" "$TMP/android.py"
progress 68 apply "Menyatukan chat, memori, dan Fokus"
[[ "$(core_version)" == "$VERSION" ]] || python "$TMP/core.py" "$ROOT" >>"$LOG" 2>&1
python "$TMP/android.py" "$ROOT" >>"$LOG" 2>&1
progress 86 validation "Memvalidasi ruang kerja bersama"
python -m compileall -q "$ROOT/core/furina_agent"
[[ "$(core_version)" == "$VERSION" ]]
python - "$ROOT" <<'PY'
from pathlib import Path
import ast,sys
core=Path(sys.argv[1])/"core/furina_agent"
for name in ("hub.py","tui.py","lite_full.py"): ast.parse((core/name).read_text(encoding="utf-8"))
hub=(core/"hub.py").read_text(encoding="utf-8")
assert "/api/capture" in hub and "/api/workspace/brief" in hub
PY
progress 94 commit "Menyimpan rilis terverifikasi"
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"
printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"
chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null || true
progress 97 bridge "Menyinkronkan APK satu kali"
sync_apk
write_state done updated done 100 "Pembaruan berhasil. Furina Lite dan FurinaHub memakai ruang kerja yang sama."
printf 'PROGRESS 100 Pembaruan berhasil\n'
