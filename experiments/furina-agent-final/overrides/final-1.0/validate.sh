#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc54-validate/termux
TMP="$(mktemp -d /tmp/furina-private-final.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

bash "$ROOT/overrides/android-rc57/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 "$ROOT/overrides/android-final/apply.py" "$STAGE"
python3 "$ROOT/overrides/runtime-final/build_client.py" \
  "$ROOT/overrides/runtime-r39/update_client.py" "$TMP/furina-update.py"
python3 -m py_compile "$TMP/furina-update.py"

grep -Fq 'VERSION = "1.0.0"' "$STAGE/core/furina_agent/version.py"
grep -Fq "versionName '1.0.0'" "$STAGE/bridge/app/build.gradle"
grep -Fq 'versionCode 10058' "$STAGE/bridge/app/build.gradle"
grep -Fq 'furina-2026.08.23-private-1.0.0' "$STAGE/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
! grep -Fq 'Core aktif' "$STAGE/bridge/app/src/main/assets/furinahub/index.html"
! grep -Fq 'data-view="relationship"' "$STAGE/bridge/app/src/main/assets/furinahub/index.html"
grep -Fq 'queue.Queue(maxsize=64)' "$STAGE/core/furina_agent/chat.py"
grep -Fq 'shutil.which("furina-update")' "$STAGE/core/furina_agent/cli.py"

mkdir -p "$TMP/snapshot"
cp -a "$STAGE/core" "$STAGE/bridge" "$TMP/snapshot/"
find "$TMP/snapshot" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$TMP/snapshot" -type f -name '*.pyc' -delete
rm -rf "$TMP/snapshot/bridge/.gradle" "$TMP/snapshot/bridge/app/build"
tar -cf "$TMP/furina-core-bridge-private-1.0.0.tar" -C "$TMP/snapshot" core bridge
printf 'private-final-apk-test\n' >"$TMP/FurinaHub-v1.0.0.apk"
SNAP_SHA="$(sha256sum "$TMP/furina-core-bridge-private-1.0.0.tar" | awk '{print $1}')"
SNAP_SIZE="$(stat -c '%s' "$TMP/furina-core-bridge-private-1.0.0.tar")"
APK_SHA="$(sha256sum "$TMP/FurinaHub-v1.0.0.apk" | awk '{print $1}')"
APK_SIZE="$(stat -c '%s' "$TMP/FurinaHub-v1.0.0.apk")"
CLIENT_SHA="$(sha256sum "$TMP/furina-update.py" | awk '{print $1}')"
CLIENT_SIZE="$(stat -c '%s' "$TMP/furina-update.py")"
export TMP SNAP_SHA SNAP_SIZE APK_SHA APK_SIZE CLIENT_SHA CLIENT_SIZE
python3 - <<'PY'
import json,os
from pathlib import Path
p=Path(os.environ['TMP'])
uri=lambda x:(p/x).resolve().as_uri()
channel={
 'schema':1,'protocol':'furina-update/1','bundle_id':'furina-2026.08.23-private-1.0.0',
 'core':{'version':'1.0.0','revision':'2026.08.23-r40','url':uri('furina-core-bridge-private-1.0.0.tar'),'sha256':os.environ['SNAP_SHA'],'size':int(os.environ['SNAP_SIZE'])},
 'apk':{'version':'1.0.0','version_code':10058,'package':'com.wynndev.furinaagentbridge','url':uri('FurinaHub-v1.0.0.apk'),'sha256':os.environ['APK_SHA'],'size':int(os.environ['APK_SIZE'])},
 'client':{'version':'1.1.0','url':uri('furina-update.py'),'sha256':os.environ['CLIENT_SHA'],'size':int(os.environ['CLIENT_SIZE'])},
}
(p/'channel.json').write_text(json.dumps(channel),encoding='utf-8')
PY

TEST_HOME="$TMP/home"
TEST_PREFIX="$TMP/prefix"
mkdir -p "$TEST_HOME" "$TEST_PREFIX/bin"
export HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME/.furina-agent" PREFIX="$TEST_PREFIX"

FURINA_TEST_MODE=1 FURINA_FORCE_TUI=1 python3 "$TMP/furina-update.py" update --channel-file "$TMP/channel.json" >"$TMP/interactive.log"
grep -Fq 'Furina' "$TMP/interactive.log"
grep -Fq 'By Wynn' "$TMP/interactive.log"
grep -Fq '100%' "$TMP/interactive.log"
grep -Fq 'VERSION = "1.0.0"' "$FURINA_HOME/core/furina_agent/version.py"
test -x "$PREFIX/bin/furina-update"

FURINA_TEST_MODE=1 python3 "$TMP/furina-update.py" confirm-apk furina-2026.08.23-private-1.0.0
FURINA_TEST_MODE=1 FURINAHUB_MACHINE_PROGRESS=1 python3 "$TMP/furina-update.py" update --channel-file "$TMP/channel.json" >"$TMP/noop.log"
grep -Fq 'PROGRESS 100 Tidak ada pembaruan terbaru' "$TMP/noop.log"
! grep -Fq 'Menyiapkan runtime Plugin' "$TMP/noop.log"

sed -i 's/VERSION = "1.0.0"/VERSION = "broken"/' "$FURINA_HOME/core/furina_agent/version.py"
FURINA_TEST_MODE=1 FURINAHUB_MACHINE_PROGRESS=1 python3 "$TMP/furina-update.py" repair --channel-file "$TMP/channel.json" >"$TMP/repair.log"
grep -Fq 'VERSION = "1.0.0"' "$FURINA_HOME/core/furina_agent/version.py"
grep -Fq 'PROGRESS 100' "$TMP/repair.log"

echo FURINA_PRIVATE_FINAL_VALIDATION_OK
