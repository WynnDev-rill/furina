#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

FURINA_RUNTIME_CONTRACT="furina-runtime/v2"
VERSION="1.0.0-rc66"
DEPENDENCY_REVISION="2026.08.22-r36"
BUNDLE_ID="furina-2026.08.22-rc66-rc54"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
R35_PATH="overrides/runtime-r35/install-body.sh"
R35_BLOB="653e080b8313ec54d0555180bab42af989838ced"
CORE_PATH="overrides/rc66/apply.py"
CORE_BLOB="3e4da7161d7cbd1593338a95b705be0924241df4"
RELATIONSHIP_PATH="overrides/rc66/relationship_v3.py"
RELATIONSHIP_BLOB="06bb973fa445413827c1cd4cd4ede16e85a2b3c2"
ANDROID_PATH="overrides/android-rc54/apply.py"
ANDROID_BLOB="000583f2b71e6e6c8b9361d8ac89662eb46a5c58"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r36-furinahub.log"
STAGE="checking"
PERCENT=0
LOCK_OWNED=0
COMMIT_STARTED=0
CORE_BACKUP="$ROOT/core.pre-rc66"
BRIDGE_BACKUP="$ROOT/bridge.pre-rc54"

if [[ ! -t 1 && -z "${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then export FURINAHUB_MACHINE_PROGRESS=1; fi
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
path=pathlib.Path(p); path.parent.mkdir(parents=True,exist_ok=True)
payload={"schema":4,"state":state,"result":result,"stage":stage,"percent":int(percent),"message":message,"source":source,"target_version":target,"target_revision":target_rev,"installed_core_version":installed,"dependency_revision":revision,"bundle_id":"furina-2026.08.22-rc66-rc54","updated_at":time.time(),"restart_required":False}
tmp=path.with_name(path.name+".new"); tmp.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8"); os.chmod(tmp,0o600); os.replace(tmp,path)
PY
}
progress(){ PERCENT="$1"; STAGE="$2"; shift 2; write_state running "" "$STAGE" "$PERCENT" "$*"; printf 'PROGRESS %d %s\n' "$PERCENT" "$*"; }
rollback(){
  [[ "$COMMIT_STARTED" == 1 ]] || return 0
  if [[ -d "$CORE_BACKUP" ]]; then rm -rf "$ROOT/core"; mv "$CORE_BACKUP" "$ROOT/core"; fi
  if [[ -d "$BRIDGE_BACKUP" ]]; then rm -rf "$ROOT/bridge"; mv "$BRIDGE_BACKUP" "$ROOT/bridge"; fi
}
cleanup(){ [[ "$LOCK_OWNED" == 1 && -d "$LOCKDIR" ]] && rm -rf "$LOCKDIR"; rm -rf "$TMP"; }
failure(){ local rc=$?; trap - ERR; rollback || true; write_state error error "$STAGE" "$PERCENT" "Pembaruan gagal pada tahap $STAGE. Instalasi aktif dipertahankan; jalankan furina recover."; printf 'ERROR %s update gagal; instalasi aktif dipertahankan\n' "$STAGE" >&2; exit "$rc"; }
trap cleanup EXIT
trap failure ERR
fetch_url(){ local url="$1" out="$2" api="${3:-0}" code; local args=(-L --silent --show-error --connect-timeout 12 --max-time 180 --retry 3 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/21' -H 'Cache-Control: no-cache'); [[ "$api" == 1 ]] && args+=(-H 'Accept: application/vnd.github.raw+json'); code="$(curl "${args[@]}" "$url" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$out" ]]; }
fetch_rel(){ local rel="$1" out="$2" asset=""; case "$rel" in overrides/runtime-r35/install-body.sh)asset=furina-runtime-r35.sh;;overrides/rc66/apply.py)asset=core-rc66-apply.py;;overrides/rc66/relationship_v3.py)asset=core-rc66-relationship-v3.py;;overrides/android-rc54/apply.py)asset=android-rc54-apply.py;;esac; { [[ -n "$asset" ]] && fetch_url "$STABLE_RELEASE/$asset" "$out"; } || fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1 || fetch_url "$RAW_BASE/$rel" "$out" || fetch_url "$WEB_BASE/$rel" "$out"; }
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
data=pathlib.Path(sys.argv[1]).read_bytes(); actual=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
assert actual==sys.argv[2],f"{actual} != {sys.argv[2]}"
PY
}
acquire(){ mkdir -p "$ROOT/run"; while ! mkdir "$LOCKDIR" 2>/dev/null; do owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; [[ -n "$owner" && -d "/proc/$owner" ]] || { rm -rf "$LOCKDIR"; continue; }; sleep 2; done; printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1; }
sync_apk(){ [[ "$SOURCE" == termux ]] || return 0; local manifest="$TMP/bundle.json" marker="$ROOT/data/furinahub_apk_bundle"; [[ "$(cat "$marker" 2>/dev/null || true)" == "$BUNDLE_ID" ]] && return 0; fetch_url "$STABLE_RELEASE/bundle.json" "$manifest" || return 0; read -r url sha < <(python - "$manifest" <<'PY'
import json,sys
item=json.load(open(sys.argv[1])); assert item.get("bundle_id")=="furina-2026.08.22-rc66-rc54"; assert item.get("bridge_version")=="1.0.0-rc54" and int(item.get("bridge_version_code",0))==10054
print(item["apk_url"],item["apk_sha256"])
PY
) || return 0; fetch_url "$url" "$TMP/FurinaHub.apk" || return 0; echo "$sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null || return 0; local out="$HOME/FurinaHub-v1.0.0-rc54.apk"; cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"; if command -v termux-open >/dev/null && termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1; then printf '%s\n' "$BUNDLE_ID" >"$marker"; fi; }

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"
: >"$LOG"
acquire
OLD="$(core_version)"
OLD_REV="$(revision)"
if [[ "$OLD" == "$VERSION" && "$OLD_REV" == "$DEPENDENCY_REVISION" ]]; then
  printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"; sync_apk
  write_state done no_update done 100 "Tidak ada pembaruan terbaru. Relationship Core dan FurinaHub sudah selaras."
  printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'
  exit 0
fi
progress 5 checking "Memeriksa relationship bundle Furina"
if [[ "$OLD" != "1.0.0-rc65" && "$OLD" != "$VERSION" ]]; then
  progress 14 foundation "Menyiapkan fondasi RC65 yang kompatibel"
  fetch_rel "$R35_PATH" "$TMP/r35.sh"; verify "$TMP/r35.sh" "$R35_BLOB"
  rm -rf "$LOCKDIR"; LOCK_OWNED=0
  FURINAHUB_MACHINE_PROGRESS=1 FURINA_UPDATE_SOURCE=foundation bash "$TMP/r35.sh" >>"$LOG" 2>&1
  acquire
fi
[[ "$(core_version)" == "1.0.0-rc65" || "$(core_version)" == "$VERSION" ]]

progress 34 download "Mengambil Core, relationship domain, dan UI baru"
mkdir -p "$TMP/rc66"
fetch_rel "$CORE_PATH" "$TMP/rc66/apply.py"; verify "$TMP/rc66/apply.py" "$CORE_BLOB"
fetch_rel "$RELATIONSHIP_PATH" "$TMP/rc66/relationship_v3.py"; verify "$TMP/rc66/relationship_v3.py" "$RELATIONSHIP_BLOB"
fetch_rel "$ANDROID_PATH" "$TMP/android.py"; verify "$TMP/android.py" "$ANDROID_BLOB"
python -m py_compile "$TMP/rc66/apply.py" "$TMP/rc66/relationship_v3.py" "$TMP/android.py"

progress 55 staging "Menerapkan perubahan di staging"
STAGED_ROOT="$TMP/staged-root"
mkdir -p "$STAGED_ROOT"
cp -a "$ROOT/core" "$STAGED_ROOT/core"
cp -a "$ROOT/bridge" "$STAGED_ROOT/bridge"
python "$TMP/rc66/apply.py" "$STAGED_ROOT" >>"$LOG" 2>&1
python "$TMP/android.py" "$STAGED_ROOT" >>"$LOG" 2>&1

progress 73 validation "Memvalidasi dialog, relationship state, dan APK source"
python -m compileall -q "$STAGED_ROOT/core/furina_agent"
python - "$STAGED_ROOT" <<'PY'
from pathlib import Path
import ast,sys
root=Path(sys.argv[1]); core=root/"core/furina_agent"; app=root/"bridge/app"
for name in ("chat.py","hub.py","tui.py","cli.py","relationship_v3.py","version.py"): ast.parse((core/name).read_text(encoding="utf-8"))
assert 'VERSION = "1.0.0-rc66"' in (core/"version.py").read_text(encoding="utf-8")
hub=(core/"hub.py").read_text(encoding="utf-8"); cli=(core/"cli.py").read_text(encoding="utf-8")
html=(app/"src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
assert all(x in hub for x in ("/api/relationship","/api/relationship/preferences","/api/relationship/moments"))
assert "def cmd_recover" in cli and 'RUN_DIR / "furina-recover.sh"' in cli
assert 'data-view="relationship"' in html and 'data-view="focus"' not in html and "Jadikan Fokus" not in html
PY

progress 84 commit "Mengaktifkan bundle terverifikasi secara atomik"
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"
COMMIT_STARTED=1
mv "$ROOT/core" "$CORE_BACKUP"
mv "$STAGED_ROOT/core" "$ROOT/core"
mv "$ROOT/bridge" "$BRIDGE_BACKUP"
mv "$STAGED_ROOT/bridge" "$ROOT/bridge"
[[ "$(core_version)" == "$VERSION" ]]
COMMIT_STARTED=0

progress 93 finalize "Menyimpan identitas bundle"
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"
printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"
chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null || true
progress 97 bridge "Menawarkan FurinaHub RC54 satu kali"
sync_apk
write_state done updated done 100 "Pembaruan besar berhasil. Furina sekarang memakai Relationship Core v3."
printf 'PROGRESS 100 Pembaruan berhasil\n'
