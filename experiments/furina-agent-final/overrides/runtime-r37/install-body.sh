#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

FURINA_RUNTIME_CONTRACT="furina-runtime/v3-full-snapshot"
VERSION="1.0.0-rc67"
DEPENDENCY_REVISION="2026.08.22-r37"
BUNDLE_ID="furina-2026.08.22-rc67-rc55"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
HUB_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furinahub-v1.0.0-rc55"
SNAPSHOT_ASSET="furina-core-bridge-rc67-rc55.tar.gz"
SNAPSHOT_SHA256="0f91696d6d9c9f88c33a827d69e2ce492f63e4269ac421777de975afc3e161bc"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r37-furinahub.log"
STAGE="checking"; PERCENT=0; LOCK_OWNED=0; COMMIT_STARTED=0; HAD_CORE=0; HAD_BRIDGE=0
CORE_BACKUP="$ROOT/core.pre-r37"; BRIDGE_BACKUP="$ROOT/bridge.pre-r37"

if [[ ! -t 1 && -z "${FURINAHUB_MACHINE_PROGRESS+x}" ]]; then export FURINAHUB_MACHINE_PROGRESS=1; fi
core_version(){ python - "$ROOT/core/furina_agent/version.py" <<'PY' 2>/dev/null || true
import re,sys
try: text=open(sys.argv[1],encoding="utf-8").read()
except Exception: print("missing"); raise SystemExit
m=re.search(r'VERSION\s*=\s*["\x27]([^"\x27]+)',text); print(m.group(1) if m else "unknown")
PY
}
revision(){ cat "$ROOT/data/dependency_revision" 2>/dev/null || true; }
write_state(){ python - "$STATUS_PATH" "$1" "$2" "$3" "$4" "$5" "$SOURCE" "$VERSION" "$DEPENDENCY_REVISION" "$(core_version)" "$(revision)" <<'PY' >/dev/null 2>&1 || true
import json,os,pathlib,sys,time
p,state,result,stage,percent,message,source,target,target_rev,installed,revision=sys.argv[1:]
path=pathlib.Path(p); path.parent.mkdir(parents=True,exist_ok=True)
payload={"schema":5,"state":state,"result":result,"stage":stage,"percent":int(percent),"message":message,"source":source,"target_version":target,"target_revision":target_rev,"installed_core_version":installed,"dependency_revision":revision,"bundle_id":"furina-2026.08.22-rc67-rc55","updated_at":time.time(),"restart_required":False}
tmp=path.with_name(path.name+".new"); tmp.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8"); os.chmod(tmp,0o600); os.replace(tmp,path)
PY
}
progress(){ PERCENT="$1"; STAGE="$2"; shift 2; write_state running "" "$STAGE" "$PERCENT" "$*"; printf 'PROGRESS %d %s\n' "$PERCENT" "$*"; }
rollback(){
  [[ "$COMMIT_STARTED" == 1 ]] || return 0
  rm -rf "$ROOT/core" "$ROOT/bridge"
  [[ "$HAD_CORE" == 1 && -d "$CORE_BACKUP" ]] && mv "$CORE_BACKUP" "$ROOT/core"
  [[ "$HAD_BRIDGE" == 1 && -d "$BRIDGE_BACKUP" ]] && mv "$BRIDGE_BACKUP" "$ROOT/bridge"
}
cleanup(){ [[ "$LOCK_OWNED" == 1 && -d "$LOCKDIR" ]] && rm -rf "$LOCKDIR"; rm -rf "$TMP"; }
failure(){ local rc=$?; trap - ERR; rollback || true; write_state error error "$STAGE" "$PERCENT" "Pembaruan gagal pada tahap $STAGE. Instalasi aktif dipertahankan; jalankan ulang installer stabil."; printf 'ERROR %s update gagal; instalasi aktif dipertahankan\n' "$STAGE" >&2; exit "$rc"; }
trap cleanup EXIT; trap failure ERR
fetch_url(){ local url="$1" out="$2" code; rm -f "$out"; code="$(curl -L --silent --show-error --connect-timeout 12 --max-time 240 --retry 4 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Snapshot-Updater/1' -H 'Cache-Control: no-cache' "$url" 2>/dev/null || true)"; [[ "$code" == 200 && -s "$out" ]]; }
acquire(){ mkdir -p "$ROOT/run"; while ! mkdir "$LOCKDIR" 2>/dev/null; do owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"; [[ -n "$owner" && -d "/proc/$owner" ]] || { rm -rf "$LOCKDIR"; continue; }; sleep 2; done; printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1; }

install_dependencies(){
  progress 22 dependencies "Memastikan dependency Termux"
  local packages=(); command -v python >/dev/null 2>&1 || packages+=(python); command -v curl >/dev/null 2>&1 || packages+=(curl)
  if (( ${#packages[@]} )); then pkg install -y "${packages[@]}" >>"$LOG" 2>&1; fi
  python - <<'PY' >/dev/null 2>&1 || python -m pip install --disable-pip-version-check --no-input 'rich>=13,<15' 'dateparser==1.4.2' >>"$LOG" 2>&1
import rich,dateparser
PY
}

validate_archive(){ python - "$1" <<'PY'
import hashlib,pathlib,sys,tarfile
p=pathlib.Path(sys.argv[1]); expected="0f91696d6d9c9f88c33a827d69e2ce492f63e4269ac421777de975afc3e161bc"
actual=hashlib.sha256(p.read_bytes()).hexdigest()
if actual != expected: raise SystemExit(f"snapshot sha256 {actual} != {expected}")
with tarfile.open(p,"r:gz") as archive:
    members=archive.getmembers()
    if not members: raise SystemExit("snapshot kosong")
    for member in members:
        parts=pathlib.PurePosixPath(member.name).parts
        if not parts or parts[0] not in {"core","bridge"} or ".." in parts or member.name.startswith("/") or member.issym() or member.islnk():
            raise SystemExit(f"path snapshot tidak aman: {member.name}")
PY
}

install_launchers(){
  mkdir -p "$PREFIX/bin"
  cat >"$PREFIX/bin/furina-real" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
export FURINA_HOME="$ROOT"
export PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"
exec python -m furina_agent "$@"
SH
  cat >"$PREFIX/bin/furina-hub" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
export FURINA_HOME="$ROOT"
export PYTHONPATH="$ROOT/core${PYTHONPATH:+:$PYTHONPATH}"
exec python -m furina_agent.hub "$@"
SH
  cat >"$PREFIX/bin/furina-update" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
URL="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh"
TARGET="$HOME/.furina-agent/run/furina-recover.sh"
mkdir -p "$(dirname "$TARGET")"
curl -fsSL --retry 4 --retry-all-errors -H 'Cache-Control: no-cache' "$URL" -o "$TARGET"
grep -Fq 'FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"' "$TARGET"
chmod 700 "$TARGET"
exec bash "$TARGET" --update "$@"
SH
  cat >"$PREFIX/bin/furina" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
# FURINA_FULL_SNAPSHOT_WRAPPER_V1
set -euo pipefail
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
if [[ "${1:-}" == update ]]; then shift; exec "$PREFIX/bin/furina-update" "$@"; fi
exec "$PREFIX/bin/furina-real" "$@"
SH
  chmod 755 "$PREFIX/bin/furina" "$PREFIX/bin/furina-real" "$PREFIX/bin/furina-hub" "$PREFIX/bin/furina-update"
}

sync_apk(){
  [[ "$SOURCE" == termux ]] || return 0
  local manifest="$TMP/bundle.json" marker="$ROOT/data/furinahub_apk_bundle"
  [[ "$(cat "$marker" 2>/dev/null || true)" == "$BUNDLE_ID" ]] && return 0
  fetch_url "$STABLE_RELEASE/bundle.json" "$manifest" || return 0
  read -r url sha < <(python - "$manifest" <<'PY'
import json,sys
x=json.load(open(sys.argv[1])); assert x.get("bundle_id")=="furina-2026.08.22-rc67-rc55"; assert x.get("bridge_version")=="1.0.0-rc55" and int(x.get("bridge_version_code",0))==10055
print(x["apk_url"],x["apk_sha256"])
PY
  ) || return 0
  fetch_url "$url" "$TMP/FurinaHub.apk" || return 0
  echo "$sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null || return 0
  local out="$HOME/FurinaHub-v1.0.0-rc55.apk"; cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"
  if command -v termux-open >/dev/null && termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1; then printf '%s\n' "$BUNDLE_ID" >"$marker"; fi
}

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"; : >"$LOG"; acquire
if [[ "$(core_version)" == "$VERSION" && "$(revision)" == "$DEPENDENCY_REVISION" ]]; then
  install_launchers; printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"; sync_apk
  write_state done no_update done 100 "Tidak ada pembaruan terbaru. Partner Core dan FurinaHub sudah selaras."
  printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'; exit 0
fi
progress 5 checking "Memeriksa full snapshot Furina"
install_dependencies
progress 36 download "Mengunduh snapshot Core dan bridge yang utuh"
fetch_url "$STABLE_RELEASE/$SNAPSHOT_ASSET" "$TMP/snapshot.tar.gz" || fetch_url "$HUB_RELEASE/$SNAPSHOT_ASSET" "$TMP/snapshot.tar.gz"
validate_archive "$TMP/snapshot.tar.gz"
progress 56 staging "Mengekstrak snapshot ke staging"
mkdir -p "$TMP/staged-root"; tar -xzf "$TMP/snapshot.tar.gz" -C "$TMP/staged-root"
progress 72 validation "Memvalidasi Partner Core dan FurinaHub"
FURINA_HOME="$TMP/test-home" PYTHONPATH="$TMP/staged-root/core" python -m compileall -q "$TMP/staged-root/core/furina_agent"
FURINA_HOME="$TMP/test-home" PYTHONPATH="$TMP/staged-root/core" python - "$TMP/staged-root" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); core=root/'core/furina_agent'; app=root/'bridge/app'
from furina_agent.memory import MemoryStore
from furina_agent.relationship_v4 import RelationshipEngine
from furina_agent.version import VERSION
assert VERSION=='1.0.0-rc67'
snap=RelationshipEngine(MemoryStore()).snapshot(); assert snap['relationship']['id']=='partner' and snap['baseline']['fresh']
build=(app/'build.gradle').read_text(); page=(app/'src/main/assets/furinahub/index.html').read_text()
assert "versionCode 10055" in build and "versionName '1.0.0-rc55'" in build
assert 'id="relationshipBaseline"' in page and 'setRelationshipMode(' not in page
PY
progress 84 commit "Mengaktifkan snapshot secara atomik"
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"; COMMIT_STARTED=1
if [[ -d "$ROOT/core" ]]; then HAD_CORE=1; mv "$ROOT/core" "$CORE_BACKUP"; fi
if [[ -d "$ROOT/bridge" ]]; then HAD_BRIDGE=1; mv "$ROOT/bridge" "$BRIDGE_BACKUP"; fi
mv "$TMP/staged-root/core" "$ROOT/core"; mv "$TMP/staged-root/bridge" "$ROOT/bridge"
[[ "$(core_version)" == "$VERSION" ]]; install_launchers; COMMIT_STARTED=0
progress 93 finalize "Menyimpan identitas bundle"
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"; printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"
chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null || true
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"
progress 97 bridge "Menawarkan FurinaHub RC55 satu kali"; sync_apk
write_state done updated done 100 "Pembaruan berhasil. Furina dimulai sebagai pasangan dengan baseline memori yang bersih."
printf 'PROGRESS 100 Pembaruan berhasil\n'
