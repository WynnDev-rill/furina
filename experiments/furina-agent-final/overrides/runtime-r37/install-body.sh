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
SNAPSHOT_ASSET="furina-core-bridge-rc67-rc55.tar"
SNAPSHOT_SHA256="502df5c11809b027ec118b3209adb3a4d14ffa441b570b8da02083dc9f2b20f9"
OPENCONNECTOR_COMMIT="d478400141c33bb5ddf823e09b293e9d7154da97"
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
  local packages=(); command -v python >/dev/null 2>&1 || packages+=(python); command -v curl >/dev/null 2>&1 || packages+=(curl); command -v git >/dev/null 2>&1 || packages+=(git); command -v node >/dev/null 2>&1 || packages+=(nodejs-lts)
  if (( ${#packages[@]} )); then pkg install -y "${packages[@]}" >>"$LOG" 2>&1; fi
  if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<22||(a===22&&b<18))process.exit(1);import("node:sqlite").then(x=>process.exit(x.DatabaseSync?0:1)).catch(()=>process.exit(1))' >/dev/null 2>&1; then pkg install -y nodejs-lts >>"$LOG" 2>&1; fi
  python - <<'PY' >/dev/null 2>&1 || python -m pip install --disable-pip-version-check --no-input 'rich>=13,<15' 'dateparser==1.4.2' >>"$LOG" 2>&1
import rich,dateparser
PY
  node -e 'import("node:sqlite").then(x=>process.exit(x.DatabaseSync?0:1)).catch(()=>process.exit(1))' >/dev/null 2>&1
}

enable_termux_integration(){
  mkdir -p "$HOME/.termux"
  local props="$HOME/.termux/termux.properties"; touch "$props"
  python - "$props" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); lines=[x for x in p.read_text(encoding="utf-8").splitlines() if not x.strip().startswith("allow-external-apps=")]
lines.append("allow-external-apps=true"); p.write_text("\n".join(lines)+"\n",encoding="utf-8")
PY
  command -v termux-reload-settings >/dev/null 2>&1 && termux-reload-settings >/dev/null 2>&1 || true
}

install_openconnector_runtime(){
  progress 28 dependencies "Memastikan runtime Plugin lokal"
  local app="$ROOT/openconnector" marker="$ROOT/data/openconnector_revision" source="$TMP/openconnector" healthy=0
  if [[ -f "$app/package.json" && -f "$app/src/server/index.ts" && -d "$app/node_modules" && "$(cat "$marker" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]]; then
    (cd "$app" && node scripts/ensure-generated.ts >/dev/null 2>>"$LOG") && healthy=1 || true
  fi
  if [[ "$healthy" == 0 ]]; then
    git init -q "$source"; git -C "$source" remote add origin https://github.com/oomol-lab/open-connector.git
    git -C "$source" fetch -q --depth 1 origin "$OPENCONNECTOR_COMMIT"; git -C "$source" checkout -q --detach FETCH_HEAD
    (cd "$source" && npm install --omit=dev --workspaces=false --no-audit --no-fund && node scripts/ensure-generated.ts) >>"$LOG" 2>&1
    test -f "$source/src/server/index.ts"; test -f "$source/src/providers/registry.generated.ts"; rm -rf "$source/.git" "$ROOT/openconnector.prev"
    [[ -d "$app" ]] && mv "$app" "$ROOT/openconnector.prev"; mv "$source" "$app"
  fi
  if [[ ! -s "$ROOT/data/openconnector-encryption.key" ]]; then python - <<'PY' >"$ROOT/data/openconnector-encryption.key"
import secrets
print(secrets.token_urlsafe(48))
PY
    chmod 600 "$ROOT/data/openconnector-encryption.key"
  fi
  printf '%s\n' "$OPENCONNECTOR_COMMIT" >"$marker"
}

validate_archive(){ python - "$1" <<'PY'
import hashlib,pathlib,sys,tarfile
p=pathlib.Path(sys.argv[1]); expected="502df5c11809b027ec118b3209adb3a4d14ffa441b570b8da02083dc9f2b20f9"
actual=hashlib.sha256(p.read_bytes()).hexdigest()
if actual != expected: raise SystemExit(f"snapshot sha256 {actual} != {expected}")
with tarfile.open(p,"r:") as archive:
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
  cat >"$PREFIX/bin/furina-openconnector" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"; APP="$ROOT/openconnector"; PID="$ROOT/run/openconnector.pid"; LOG="$ROOT/logs/openconnector.log"; URL="http://127.0.0.1:3000/v1/health"
healthy(){ curl -fsS --max-time 3 "$URL" >/dev/null 2>&1; }
running(){ [[ -f "$PID" ]] && p="$(cat "$PID" 2>/dev/null || true)" && [[ "$p" =~ ^[0-9]+$ ]] && kill -0 "$p" >/dev/null 2>&1; }
stop_runtime(){ if running; then kill "$(cat "$PID")" >/dev/null 2>&1 || true; fi; rm -f "$PID"; }
repair(){ (cd "$APP" && npm install --omit=dev --workspaces=false --no-audit --no-fund && node scripts/ensure-generated.ts) >>"$LOG" 2>&1; }
start_runtime(){
  healthy && return 0; stop_runtime; test -f "$APP/src/server/index.ts"; test -s "$ROOT/data/openconnector-encryption.key"
  mkdir -p "$ROOT/run" "$ROOT/logs" "$ROOT/data/openconnector"; key="$(cat "$ROOT/data/openconnector-encryption.key")"
  (cd "$APP"; exec env NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000 OOMOL_CONNECT_ORIGIN=http://127.0.0.1:3000 OOMOL_CONNECT_DATA_DIR="$ROOT/data/openconnector" OOMOL_CONNECT_ENCRYPTION_KEY="$key" node "$APP/src/server/index.ts") >>"$LOG" 2>&1 & echo "$!" >"$PID"
  for _ in $(seq 1 120); do healthy && return 0; running || break; sleep .25; done
  stop_runtime; return 4
}
case "${1:-start}" in
  start) start_runtime || { repair; start_runtime; };;
  stop) stop_runtime;; restart) stop_runtime; start_runtime;;
  repair) stop_runtime; repair; start_runtime;;
  status) healthy && { echo ready; exit 0; }; echo offline; exit 1;;
  logs) tail -n 100 "$LOG" 2>/dev/null || true;;
  *) echo "usage: furina-openconnector {start|stop|restart|repair|status|logs}" >&2; exit 2;;
esac
SH
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
  chmod 755 "$PREFIX/bin/furina" "$PREFIX/bin/furina-real" "$PREFIX/bin/furina-hub" "$PREFIX/bin/furina-update" "$PREFIX/bin/furina-openconnector"
}

write_snapshot_manifest(){ python - "$1" "$2" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); files={}
for top in ("core","bridge"):
    for p in sorted((root/top).rglob("*")):
        rel=p.relative_to(root).as_posix()
        if not p.is_file() or "__pycache__" in p.parts or p.suffix==".pyc" or rel.startswith("bridge/.gradle/") or rel.startswith("bridge/app/build/"): continue
        files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
out.write_text(json.dumps({"schema":1,"bundle_id":"furina-2026.08.22-rc67-rc55","files":files},sort_keys=True)+"\n",encoding="utf-8")
PY
}

installation_healthy(){
  [[ "$(core_version)" == "$VERSION" && "$(revision)" == "$DEPENDENCY_REVISION" ]] || return 1
  [[ -f "$ROOT/data/snapshot-manifest-r37.json" && -f "$ROOT/openconnector/src/server/index.ts" && -d "$ROOT/openconnector/node_modules" ]] || return 1
  [[ "$(cat "$ROOT/data/openconnector_revision" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]] || return 1
  command -v furina >/dev/null 2>&1 && command -v furina-openconnector >/dev/null 2>&1 || return 1
  grep -Eq '^allow-external-apps=true$' "$HOME/.termux/termux.properties" 2>/dev/null || return 1
  python - "$ROOT" "$ROOT/data/snapshot-manifest-r37.json" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); data=json.load(open(sys.argv[2],encoding="utf-8"))
assert data.get("bundle_id")=="furina-2026.08.22-rc67-rc55" and data.get("files")
for rel,expected in data["files"].items():
    p=root/rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected: raise SystemExit(1)
PY
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
if installation_healthy; then
  install_launchers; printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"; sync_apk
  write_state done no_update done 100 "Tidak ada pembaruan terbaru. Partner Core dan FurinaHub sudah selaras."
  printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'; exit 0
fi
progress 5 checking "Memeriksa full snapshot Furina"
install_dependencies
enable_termux_integration
install_openconnector_runtime
progress 36 download "Mengunduh snapshot Core dan bridge yang utuh"
fetch_url "$STABLE_RELEASE/$SNAPSHOT_ASSET" "$TMP/snapshot.tar" || fetch_url "$HUB_RELEASE/$SNAPSHOT_ASSET" "$TMP/snapshot.tar"
validate_archive "$TMP/snapshot.tar"
progress 56 staging "Mengekstrak snapshot ke staging"
mkdir -p "$TMP/staged-root"; tar -xf "$TMP/snapshot.tar" -C "$TMP/staged-root"
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
write_snapshot_manifest "$TMP/staged-root" "$TMP/snapshot-manifest-r37.json"
progress 84 commit "Mengaktifkan snapshot secara atomik"
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"; COMMIT_STARTED=1
if [[ -d "$ROOT/core" ]]; then HAD_CORE=1; mv "$ROOT/core" "$CORE_BACKUP"; fi
if [[ -d "$ROOT/bridge" ]]; then HAD_BRIDGE=1; mv "$ROOT/bridge" "$BRIDGE_BACKUP"; fi
mv "$TMP/staged-root/core" "$ROOT/core"; mv "$TMP/staged-root/bridge" "$ROOT/bridge"
[[ "$(core_version)" == "$VERSION" ]]; install_launchers; COMMIT_STARTED=0
progress 93 finalize "Menyimpan identitas bundle"
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"; printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"
chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null || true
mv "$TMP/snapshot-manifest-r37.json" "$ROOT/data/snapshot-manifest-r37.json"; chmod 600 "$ROOT/data/snapshot-manifest-r37.json"
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"
progress 97 bridge "Menawarkan FurinaHub RC55 satu kali"; sync_apk
write_state done updated done 100 "Pembaruan berhasil. Furina dimulai sebagai pasangan dengan baseline memori yang bersih."
printf 'PROGRESS 100 Pembaruan berhasil\n'
