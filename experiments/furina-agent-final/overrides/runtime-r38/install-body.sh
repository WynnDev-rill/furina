#!/data/data/com.termux/files/usr/bin/bash
set -eEuo pipefail

FURINA_RUNTIME_CONTRACT="furina-runtime/v4-channel-snapshot"
VERSION="1.0.0-rc68"
DEPENDENCY_REVISION="2026.08.23-r38"
BUNDLE_ID="furina-2026.08.23-rc68-rc56"
ROOT="$HOME/.furina-agent"
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
STABLE_RELEASE="https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable"
OPENCONNECTOR_COMMIT="d478400141c33bb5ddf823e09b293e9d7154da97"
STATUS_PATH="$ROOT/run/furinahub-update.json"
LOCKDIR="$ROOT/run/update.lock"
SOURCE="${FURINA_UPDATE_SOURCE:-termux}"
TMP="$(mktemp -d)"
LOG="$ROOT/logs/update-r38-furinahub.log"
STAGE="checking"; PERCENT=0; LOCK_OWNED=0; COMMIT_STARTED=0; HAD_CORE=0; HAD_BRIDGE=0
CORE_BACKUP="$ROOT/core.pre-r38"; BRIDGE_BACKUP="$ROOT/bridge.pre-r38"
APK_ONLY=0; APK_OFFERED=0
for arg in "$@"; do [[ "$arg" == "--apk-only" ]] && APK_ONLY=1; done

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
payload={"schema":6,"state":state,"result":result,"stage":stage,"percent":int(percent),"message":message,"source":source,"target_version":target,"target_revision":target_rev,"installed_core_version":installed,"dependency_revision":revision,"bundle_id":"furina-2026.08.23-rc68-rc56","updated_at":time.time(),"restart_required":False}
tmp=path.with_name(path.name+".new"); tmp.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8"); os.chmod(tmp,0o600); os.replace(tmp,path)
PY
}
progress(){ PERCENT="$1"; STAGE="$2"; shift 2; write_state running "" "$STAGE" "$PERCENT" "$*"; printf 'PROGRESS %d %s\n' "$PERCENT" "$*"; return 0; }

rollback(){
  [[ "$COMMIT_STARTED" == 1 ]] || return 0
  rm -rf "$ROOT/core" "$ROOT/bridge"
  [[ "$HAD_CORE" == 1 && -d "$CORE_BACKUP" ]] && mv "$CORE_BACKUP" "$ROOT/core"
  [[ "$HAD_BRIDGE" == 1 && -d "$BRIDGE_BACKUP" ]] && mv "$BRIDGE_BACKUP" "$ROOT/bridge"
}
cleanup(){ [[ "$LOCK_OWNED" == 1 && -d "$LOCKDIR" ]] && rm -rf "$LOCKDIR"; rm -rf "$TMP"; }
failure(){
  local rc=$?
  trap - ERR
  rollback || true
  write_state error error "$STAGE" "$PERCENT" "Pembaruan gagal pada tahap $STAGE. Instalasi aktif dipertahankan; jalankan furina update lagi."
  printf 'ERROR %s update gagal; instalasi aktif dipertahankan\n' "$STAGE" >&2
  tail -n 24 "$LOG" 2>/dev/null >&2 || true
  exit "$rc"
}
trap cleanup EXIT
trap failure ERR

fetch_url(){
  local url="$1" out="$2" code
  rm -f "$out"
  code="$(curl -L --silent --show-error --connect-timeout 12 --max-time 240 --retry 4 --retry-delay 2 --retry-all-errors -o "$out" -w '%{http_code}' -H 'User-Agent: Furina-Snapshot-Updater/2' -H 'Cache-Control: no-cache' -H 'Pragma: no-cache' "$url" 2>/dev/null || true)"
  [[ "$code" == 200 && -s "$out" ]]
}

acquire(){
  mkdir -p "$ROOT/run"
  while ! mkdir "$LOCKDIR" 2>/dev/null; do
    owner="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"
    [[ -n "$owner" && -d "/proc/$owner" ]] || { rm -rf "$LOCKDIR"; continue; }
    sleep 2
  done
  printf '%s\n' "$$" >"$LOCKDIR/pid"; LOCK_OWNED=1
}

fetch_target_bundle(){
  local out="$1"
  for attempt in 1 2 3 4 5 6; do
    if fetch_url "$STABLE_RELEASE/bundle.json?attempt=$attempt" "$out"; then
      if python - "$out" "$BUNDLE_ID" "$VERSION" <<'PY'
import json,sys
p,bundle,version=sys.argv[1:]
d=json.load(open(p,encoding="utf-8"))
schema=int(d.get("schema",1))
if schema not in (1,2): raise SystemExit(1)
if d.get("bundle_id") != bundle or d.get("core_version") != version: raise SystemExit(1)
if not d.get("snapshot_asset") or not d.get("snapshot_sha256"): raise SystemExit(1)
if not d.get("apk_url") or not d.get("apk_sha256"): raise SystemExit(1)
print("ok")
PY
      then return 0; fi
    fi
    sleep $((attempt*2))
  done
  return 75
}

install_dependencies(){
  progress 18 dependencies "Memastikan dependency Termux"
  local packages=()
  command -v python >/dev/null 2>&1 || packages+=(python)
  command -v curl >/dev/null 2>&1 || packages+=(curl)
  command -v git >/dev/null 2>&1 || packages+=(git)
  command -v node >/dev/null 2>&1 || packages+=(nodejs-lts)
  if (( ${#packages[@]} )); then pkg install -y "${packages[@]}" >>"$LOG" 2>&1; fi
  if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<22||(a===22&&b<13))process.exit(1);import("node:sqlite").then(x=>process.exit(x.DatabaseSync?0:1)).catch(()=>process.exit(1))' >/dev/null 2>&1; then
    pkg install -y nodejs-lts >>"$LOG" 2>&1
  fi
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
  progress 24 dependencies "Memastikan runtime Plugin lokal"
  local app="$ROOT/openconnector" marker="$ROOT/data/openconnector_revision" source="$TMP/openconnector" healthy=0
  if [[ -f "$app/package.json" && -f "$app/src/server/index.ts" && -d "$app/node_modules" && "$(cat "$marker" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]]; then
    (cd "$app" && node scripts/ensure-generated.ts >/dev/null 2>>"$LOG") && healthy=1 || true
  fi
  if [[ "$healthy" == 0 ]]; then
    git init -q "$source"; git -C "$source" remote add origin https://github.com/oomol-lab/open-connector.git
    git -C "$source" fetch -q --depth 1 origin "$OPENCONNECTOR_COMMIT"; git -C "$source" checkout -q --detach FETCH_HEAD
    (cd "$source" && npm install --omit=dev --workspaces=false --no-audit --no-fund && node scripts/ensure-generated.ts) >>"$LOG" 2>&1
    test -f "$source/src/server/index.ts"; test -f "$source/src/providers/registry.generated.ts"
    rm -rf "$source/.git" "$ROOT/openconnector.prev"
    [[ -d "$app" ]] && mv "$app" "$ROOT/openconnector.prev"
    mv "$source" "$app"
  fi
  if [[ ! -s "$ROOT/data/openconnector-encryption.key" ]]; then
    python - <<'PY' >"$ROOT/data/openconnector-encryption.key"
import secrets
print(secrets.token_urlsafe(48))
PY
    chmod 600 "$ROOT/data/openconnector-encryption.key"
  fi
  printf '%s\n' "$OPENCONNECTOR_COMMIT" >"$marker"
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
  healthy && return 0
  stop_runtime
  test -f "$APP/src/server/index.ts"; test -s "$ROOT/data/openconnector-encryption.key"
  mkdir -p "$ROOT/run" "$ROOT/logs" "$ROOT/data/openconnector"
  key="$(cat "$ROOT/data/openconnector-encryption.key")"
  (cd "$APP"; exec env NODE_ENV=production NODE_NO_WARNINGS=1 HOST=127.0.0.1 PORT=3000 OOMOL_CONNECT_ORIGIN=http://127.0.0.1:3000 OOMOL_CONNECT_DATA_DIR="$ROOT/data/openconnector" OOMOL_CONNECT_ENCRYPTION_KEY="$key" node "$APP/src/server/index.ts") >>"$LOG" 2>&1 & echo "$!" >"$PID"
  for _ in $(seq 1 120); do healthy && return 0; running || break; sleep .25; done
  stop_runtime; return 4
}
case "${1:-start}" in
  start) start_runtime || { repair; start_runtime; };;
  stop) stop_runtime;;
  restart) stop_runtime; start_runtime;;
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
curl -fsSL --retry 4 --retry-all-errors -H 'Cache-Control: no-cache' "$URL?ts=$(date +%s)" -o "$TARGET"
grep -Fq 'FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"' "$TARGET"
chmod 700 "$TARGET"
exec bash "$TARGET" --update "$@"
SH
  cat >"$PREFIX/bin/furina-update-apk" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
export FURINA_UPDATE_SOURCE=termux
exec furina-update --apk-only
SH
  cat >"$PREFIX/bin/furina-apk-confirm" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$HOME/.furina-agent"
EXPECTED="furina-2026.08.23-rc68-rc56"
[[ "${1:-}" == "$EXPECTED" ]] || exit 0
mkdir -p "$ROOT/data"
printf '%s\n' "$EXPECTED" >"$ROOT/data/furinahub_apk_bundle"
chmod 600 "$ROOT/data/furinahub_apk_bundle" 2>/dev/null || true
SH
  cat >"$PREFIX/bin/furina" <<'SH'
#!/data/data/com.termux/files/usr/bin/bash
# FURINA_FULL_SNAPSHOT_WRAPPER_V2
set -euo pipefail
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
if [[ "${1:-}" == update ]]; then shift; exec "$PREFIX/bin/furina-update" "$@"; fi
exec "$PREFIX/bin/furina-real" "$@"
SH
  chmod 755 "$PREFIX/bin/furina" "$PREFIX/bin/furina-real" "$PREFIX/bin/furina-hub" "$PREFIX/bin/furina-update" "$PREFIX/bin/furina-update-apk" "$PREFIX/bin/furina-apk-confirm" "$PREFIX/bin/furina-openconnector"
}

validate_archive(){
  python - "$1" "$2" <<'PY'
import hashlib,pathlib,sys,tarfile
p=pathlib.Path(sys.argv[1]); expected=sys.argv[2].lower()
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

validate_stage(){
  local stage="$1"
  python - "$stage" <<'PY'
import pathlib,sys
root=pathlib.Path(sys.argv[1])
version=(root/"core/furina_agent/version.py").read_text(encoding="utf-8")
build=(root/"bridge/app/build.gradle").read_text(encoding="utf-8")
main=(root/"bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java").read_text(encoding="utf-8")
page=(root/"bridge/app/src/main/assets/furinahub/index.html").read_text(encoding="utf-8")
assert 'VERSION = "1.0.0-rc68"' in version
assert "versionCode 10056" in build and "versionName '1.0.0-rc56'" in build
assert "furina-2026.08.23-rc68-rc56" in main
assert 'EXPECTED_CORE_VERSION = "1.0.0-rc68"' in main
assert 'data-view="relationship"' not in page
assert 'id="relationship"' in page
for p in (root/"core/furina_agent").glob("*.py"):
    compile(p.read_text(encoding="utf-8"),str(p),"exec")
print("FURINA_R38_STAGE_OK")
PY
}

write_snapshot_manifest(){
  python - "$1" "$2" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); files={}
for top in ("core","bridge"):
    for p in sorted((root/top).rglob("*")):
        rel=p.relative_to(root).as_posix()
        if not p.is_file() or "__pycache__" in p.parts or p.suffix==".pyc" or rel.startswith("bridge/.gradle/") or rel.startswith("bridge/app/build/"): continue
        files[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
out.write_text(json.dumps({"schema":1,"bundle_id":"furina-2026.08.23-rc68-rc56","files":files},sort_keys=True)+"\n",encoding="utf-8")
PY
}

installation_healthy(){
  [[ "$(core_version)" == "$VERSION" && "$(revision)" == "$DEPENDENCY_REVISION" ]] || return 1
  [[ -f "$ROOT/data/snapshot-manifest-r38.json" && -f "$ROOT/openconnector/src/server/index.ts" && -d "$ROOT/openconnector/node_modules" ]] || return 1
  [[ "$(cat "$ROOT/data/openconnector_revision" 2>/dev/null || true)" == "$OPENCONNECTOR_COMMIT" ]] || return 1
  command -v furina >/dev/null 2>&1 && command -v furina-apk-confirm >/dev/null 2>&1 || return 1
  grep -Eq '^allow-external-apps=true$' "$HOME/.termux/termux.properties" 2>/dev/null || return 1
  python - "$ROOT" "$ROOT/data/snapshot-manifest-r38.json" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]); data=json.load(open(sys.argv[2],encoding="utf-8"))
if data.get("bundle_id")!="furina-2026.08.23-rc68-rc56": raise SystemExit(1)
for rel,expected in data.get("files",{}).items():
    p=root/rel
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected: raise SystemExit(1)
PY
}

sync_apk(){
  [[ "$SOURCE" == "termux" ]] || return 0
  local marker="$ROOT/data/furinahub_apk_bundle" out="$HOME/FurinaHub-v1.0.0-rc56.apk" url sha
  [[ "$(cat "$marker" 2>/dev/null || true)" == "$BUNDLE_ID" ]] && return 0
  read -r url sha < <(python - "$TMP/bundle.json" "$BUNDLE_ID" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
if d.get("bundle_id")!=sys.argv[2]: raise SystemExit(1)
print(d["apk_url"],d["apk_sha256"])
PY
  )
  progress 94 bridge "Mengunduh FurinaHub RC56"
  fetch_url "$url" "$TMP/FurinaHub.apk"
  echo "$sha  $TMP/FurinaHub.apk" | sha256sum -c - >/dev/null
  cp "$TMP/FurinaHub.apk" "$out"; chmod 600 "$out"
  progress 97 bridge "Membuka installer FurinaHub RC56"
  if command -v termux-open >/dev/null 2>&1; then
    termux-open --content-type application/vnd.android.package-archive "$out" >/dev/null 2>&1 || true
  fi
  APK_OFFERED=1
  # Do not mark the bundle installed here. Launching Android's installer is not
  # proof of installation. RC56 confirms itself through furina-apk-confirm.
  printf '%s\n' "APK siap di $out. Status baru dikonfirmasi setelah FurinaHub RC56 benar-benar dijalankan." >>"$LOG"
}

mkdir -p "$ROOT/logs" "$ROOT/data" "$ROOT/run"; : >"$LOG"; acquire
progress 4 checking "Memeriksa channel update Furina"
fetch_target_bundle "$TMP/bundle.json"

if [[ "$APK_ONLY" == 1 ]]; then
  install_launchers
  sync_apk
  if [[ "$APK_OFFERED" == 1 ]]; then
    write_state done updated done 100 "Installer FurinaHub RC56 dibuka. Buka FurinaHub setelah instalasi untuk mengonfirmasi versi."
  else
    write_state done no_update done 100 "FurinaHub RC56 sudah dikonfirmasi terpasang."
  fi
  printf 'PROGRESS 100 %s\n' "$( [[ "$APK_OFFERED" == 1 ]] && echo 'Installer FurinaHub dibuka' || echo 'FurinaHub sudah terbaru' )"
  exit 0
fi

if installation_healthy; then
  install_launchers
  sync_apk
  if [[ "$APK_OFFERED" == 1 ]]; then
    write_state done updated done 100 "Core sudah terbaru. Installer FurinaHub RC56 dibuka dan belum dianggap selesai sampai aplikasi baru dijalankan."
    printf 'PROGRESS 100 Core terbaru; installer FurinaHub dibuka\n'
  else
    write_state done no_update done 100 "Tidak ada pembaruan terbaru. Core RC68, runtime r38, dan FurinaHub RC56 sudah selaras."
    printf 'PROGRESS 100 Tidak ada pembaruan terbaru\n'
  fi
  exit 0
fi

install_dependencies
enable_termux_integration
install_openconnector_runtime

progress 34 download "Mengambil full snapshot RC68/RC56"
read -r snapshot_asset snapshot_sha < <(python - "$TMP/bundle.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1],encoding="utf-8"))
print(d["snapshot_asset"],d["snapshot_sha256"])
PY
)
fetch_url "$STABLE_RELEASE/$snapshot_asset" "$TMP/snapshot.tar"
progress 58 validation "Memverifikasi snapshot dan struktur arsip"
validate_archive "$TMP/snapshot.tar" "$snapshot_sha"
mkdir -p "$TMP/stage"
tar -xf "$TMP/snapshot.tar" -C "$TMP/stage"
validate_stage "$TMP/stage"
write_snapshot_manifest "$TMP/stage" "$TMP/snapshot-manifest-r38.json"

progress 74 commit "Mengaktifkan Core dan Bridge secara atomik"
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"
[[ -d "$ROOT/core" ]] && { mv "$ROOT/core" "$CORE_BACKUP"; HAD_CORE=1; }
[[ -d "$ROOT/bridge" ]] && { mv "$ROOT/bridge" "$BRIDGE_BACKUP"; HAD_BRIDGE=1; }
COMMIT_STARTED=1
mv "$TMP/stage/core" "$ROOT/core"
mv "$TMP/stage/bridge" "$ROOT/bridge"
validate_stage "$ROOT"
install_launchers
printf '%s\n' "$DEPENDENCY_REVISION" >"$ROOT/data/dependency_revision"
printf '%s\n' "$BUNDLE_ID" >"$ROOT/data/bundle_id"
chmod 600 "$ROOT/data/dependency_revision" "$ROOT/data/bundle_id" 2>/dev/null || true
mv "$TMP/snapshot-manifest-r38.json" "$ROOT/data/snapshot-manifest-r38.json"
chmod 600 "$ROOT/data/snapshot-manifest-r38.json"
rm -rf "$CORE_BACKUP" "$BRIDGE_BACKUP"
COMMIT_STARTED=0

sync_apk
if [[ "$APK_OFFERED" == 1 ]]; then
  write_state done updated done 100 "Pembaruan Core RC68/r38 berhasil. Installer FurinaHub RC56 dibuka; aplikasi baru harus dijalankan untuk mengonfirmasi APK."
else
  write_state done updated done 100 "Pembaruan berhasil. Core RC68, runtime r38, dan FurinaHub RC56 sudah selaras."
fi
printf 'PROGRESS 100 Pembaruan berhasil\n'
