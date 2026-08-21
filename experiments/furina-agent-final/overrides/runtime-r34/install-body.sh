#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

VERSION="1.0.0-rc64"
DEPENDENCY_REVISION="2026.08.21-r34"
ROOT="$HOME/.furina-agent"
API_BASE="https://api.github.com/repos/WynnDev-rill/furina/contents/experiments/furina-agent-final"
RAW_BASE="https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final"
WEB_BASE="https://github.com/WynnDev-rill/furina/raw/refs/heads/experiment/furina-agent-termux/experiments/furina-agent-final"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
R33_PATH="overrides/runtime-r33/install-body.sh"
R33_BLOB="6bc0c9c8d97cb6e8f0838383527be1981edf02f3"
CORE_PATH="overrides/rc64/apply.py"
CORE_BLOB="94740c9ec52bfa4b825f3ad1fa487bec92d6b9e4"
PRODUCT_PATH="overrides/rc64/lite_full.py"
PRODUCT_BLOB="536bcafe227dd524a43eae4601b179a9bbd41efe"
ANDROID_PATH="overrides/android-rc52/apply.py"
ANDROID_BLOB="30f554dc076fe2880b38f16c71500247451ac6af"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
BUNDLE_ID="furina-2026.08.21-rc64-rc52"
TMP="$(mktemp -d)"; LOG="$ROOT/logs/update-r34-furinahub.log"; STAGE="checking"; PERCENT=0; LOCK_OWNED=0

if [[ ! -t 1 && -z "${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then export FURINAHUB_MACHINE_PROGRESS=1; fi
core_version(){ python - "$ROOT/core/furina_agent/version.py" <<'PY' 2>/dev/null || true
import re,sys
try: t=open(sys.argv[1],encoding='utf-8').read()
except Exception: print('missing');raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',t);print(m.group(1) if m else 'unknown')
PY
}
revision(){ cat "$ROOT/data/dependency_revision" 2>/dev/null || true; }
write_state(){ python - "$STATUS_PATH" "$1" "$2" "$3" "$4" "$5" "$SOURCE" "$VERSION" "$DEPENDENCY_REVISION" "$(core_version)" "$(revision)" <<'PY' >/dev/null 2>&1 || true
import json,os,pathlib,sys,time
p,state,result,stage,percent,message,source,target,target_rev,installed,revision=sys.argv[1:]
path=pathlib.Path(p);path.parent.mkdir(parents=True,exist_ok=True)
d={'schema':3,'state':state,'result':result,'stage':stage,'percent':int(percent),'message':message,'source':source,'target_version':target,'target_revision':target_rev,'installed_core_version':installed,'dependency_revision':revision,'bundle_id':'furina-2026.08.21-rc64-rc52','updated_at':time.time(),'restart_required':False}
t=path.with_name(path.name+'.new');t.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8');os.chmod(t,0o600);os.replace(t,path)
PY
}
progress(){ PERCENT="$1";STAGE="$2";shift 2;write_state running "" "$STAGE" "$PERCENT" "$*";printf 'PROGRESS %d %s\n' "$PERCENT" "$*"; }
cleanup(){ [[ "$LOCK_OWNED" == 1 && -d "$LOCKDIR" ]] && rm -rf "$LOCKDIR";rm -rf "$TMP"; }
failure(){ local rc=$?;trap - ERR;write_state error error "$STAGE" "$PERCENT" "Pembaruan gagal pada tahap $STAGE. Buka furina doctor atau log update.";printf 'ERROR %s update gagal\n' "$STAGE" >&2;exit "$rc"; }
trap cleanup EXIT;trap failure ERR
fetch_url(){ local url="$1" out="$2" api="${3:-0}" code;local args=(-L --silent --show-error --connect-timeout 12 --max-time 180 --retry 3 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Core-Updater/18' -H 'Cache-Control: no-cache');[[ "$api" == 1 ]]&&args+=(-H 'Accept: application/vnd.github.raw+json');code="$(curl "${args[@]}" "$url" 2>/dev/null||true)";[[ "$code" == 200 && -s "$out" ]]; }
fetch_rel(){ local rel="$1" out="$2" asset="";case "$rel" in overrides/runtime-r33/install-body.sh)asset=furina-runtime-r33.sh;;overrides/rc64/apply.py)asset=core-rc64-apply.py;;overrides/rc64/lite_full.py)asset=core-rc64-lite-full.py;;overrides/android-rc52/apply.py)asset=android-rc52-apply.py;;esac;{ [[ -n "$asset" ]]&&fetch_url "$STABLE_RELEASE/$asset" "$out";}||fetch_url "$API_BASE/$rel?ref=experiment/furina-agent-termux" "$out" 1||fetch_url "$RAW_BASE/$rel" "$out"||fetch_url "$WEB_BASE/$rel" "$out"; }
verify(){ python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys
d=pathlib.Path(sys.argv[1]).read_bytes();a=hashlib.sha1(f'blob {len(d)}\0'.encode()+d).hexdigest();assert a==sys.argv[2],f'{a} != {sys.argv[2]}'
PY
}
acquire(){ mkdir -p "$ROOT/run";while ! mkdir "$LOCKDIR" 2>/dev/null;do owner="$(cat "$LOCKDIR/pid" 2>/dev/null||true)";[[ -n "$owner" && -d "/proc/$owner" ]]||{ rm -rf "$LOCKDIR";continue;};sleep 2;done;printf '%s\n' "$$">"$LOCKDIR/pid";LOCK_OWNED=1; }
sync_apk(){ [[ "$SOURCE" == termux ]]||return 0;local manifest="$TMP/bundle.json" marker="$ROOT/data/furinahub_apk_bundle";[[ "$(cat "$marker" 2>/dev/null||true)" == "$BUNDLE_ID" ]]&&return 0;fetch_url "$STABLE_RELEASE/bundle.json" "$manifest"||return 0;read -r url sha < <(python - "$manifest" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]));assert m.get('bundle_id')=='furina-2026.08.21-rc64-rc52' and m.get('bridge_version')=='1.0.0-rc52' and int(m.get('bridge_version_code',0))==10052
print(m['apk_url'],m['apk_sha256'])
PY
)||return 0;fetch_url "$url" "$TMP/FurinaHub.apk"||return 0;echo "$sha  $TMP/FurinaHub.apk"|sha256sum -c - >/dev/null||return 0;local out="$HOME/FurinaHub-v1.0.0-rc52.apk";cp "$TMP/FurinaHub.apk" "$out";chmod 600 "$out";if command -v termux-open >/dev/null&&termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1;then printf '%s\n' "$BUNDLE_ID">"$marker";fi; }

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run";:>"$LOG";acquire
OLD="$(core_version)";OLD_REV="$(revision)"
if [[ "$OLD" == "$VERSION" && "$OLD_REV" == "$DEPENDENCY_REVISION" ]];then printf '%s\n' "$BUNDLE_ID">"$ROOT/data/bundle_id";sync_apk;write_state done no_update done 100 "Tidak ada pembaruan terbaru. Furina Lite dan FurinaHub Full sudah selaras.";printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n';exit 0;fi
progress 5 checking "Memeriksa Furina Lite dan FurinaHub"
if [[ "$OLD" != "1.0.0-rc63" && "$OLD" != "$VERSION" ]];then progress 15 foundation "Menyiapkan fondasi rilis sebelumnya";fetch_rel "$R33_PATH" "$TMP/r33.sh";verify "$TMP/r33.sh" "$R33_BLOB";rm -rf "$LOCKDIR";LOCK_OWNED=0;FURINAHUB_MACHINE_PROGRESS=1 FURINA_UPDATE_SOURCE=foundation bash "$TMP/r33.sh" >>"$LOG" 2>&1;acquire;fi
[[ "$(core_version)" == "1.0.0-rc63" || "$(core_version)" == "$VERSION" ]]
progress 40 download "Mengambil workspace Furina Lite dan Full";fetch_rel "$CORE_PATH" "$TMP/core.py";verify "$TMP/core.py" "$CORE_BLOB";fetch_rel "$PRODUCT_PATH" "$TMP/lite_full.py";verify "$TMP/lite_full.py" "$PRODUCT_BLOB";fetch_rel "$ANDROID_PATH" "$TMP/android.py";verify "$TMP/android.py" "$ANDROID_BLOB";python -m py_compile "$TMP/core.py" "$TMP/lite_full.py" "$TMP/android.py"
progress 62 apply "Menyatukan fitur Lite dan FurinaHub";[[ "$(core_version)" == "$VERSION" ]]||python "$TMP/core.py" "$ROOT" >>"$LOG" 2>&1;python "$TMP/android.py" "$ROOT" >>"$LOG" 2>&1
progress 83 validation "Memvalidasi chat, Fokus, memori, dan profil bersama";python -m compileall -q "$ROOT/core/furina_agent";[[ "$(core_version)" == "$VERSION" ]];python - "$ROOT" <<'PY'
from pathlib import Path
import ast,sys
c=Path(sys.argv[1])/'core/furina_agent'
for p in ('hub.py','tui.py','lite_full.py'):ast.parse((c/p).read_text(encoding='utf-8'))
h=(c/'hub.py').read_text();assert '/api/focus' in h and '/api/workspace' in h and 'ProductWorkspace' in h
PY
progress 94 commit "Menyimpan bundle Furina Lite dan Full";printf '%s\n' "$DEPENDENCY_REVISION">"$ROOT/data/dependency_revision";printf '%s\n' "$BUNDLE_ID">"$ROOT/data/bundle_id";chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null||true
progress 97 bridge "Menyinkronkan APK satu kali";sync_apk
write_state done updated done 100 "Pembaruan berhasil. Furina Lite dan FurinaHub Full menggunakan workspace yang sama.";printf 'PROGRESS 100 Pembaruan berhasil\n'
