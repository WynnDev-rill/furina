#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CLIENT="$HERE/update_client.py"

bash "$ROOT/overrides/android-rc57/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 -m py_compile "$CLIENT"

TMP="$(mktemp -d /tmp/furina-r39.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/archive" "$TMP/home/.furina-agent/data" "$TMP/prefix/bin"
printf 'user-data-survives\n' >"$TMP/home/.furina-agent/data/keep.txt"
cp -a "$STAGE/core" "$STAGE/bridge" "$TMP/archive/"
find "$TMP/archive" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$TMP/archive" -type f -name '*.pyc' -delete
rm -rf "$TMP/archive/bridge/.gradle" "$TMP/archive/bridge/app/build"
tar --sort=name --mtime='UTC 2026-08-23 00:00:00' --owner=0 --group=0 --numeric-owner \
  -cf "$TMP/furina-core-bridge-rc69-rc57.tar" -C "$TMP/archive" core bridge
printf 'fixture apk rc57\n' >"$TMP/FurinaHub-v1.0.0-rc57.apk"

python3 - "$CLIENT" "$TMP" <<'PY'
import hashlib,json,pathlib,sys
client=pathlib.Path(sys.argv[1]).resolve(); tmp=pathlib.Path(sys.argv[2]).resolve()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
snapshot=tmp/'furina-core-bridge-rc69-rc57.tar'; apk=tmp/'FurinaHub-v1.0.0-rc57.apk'
channel={
  'schema':1,
  'protocol':'furina-update/1',
  'bundle_id':'furina-2026.08.23-rc69-rc57',
  'core':{'version':'1.0.0-rc69','revision':'2026.08.23-r39','url':snapshot.as_uri(),'sha256':sha(snapshot),'size':snapshot.stat().st_size},
  'apk':{'version':'1.0.0-rc57','version_code':10057,'package':'com.wynndev.furinaagentbridge','url':apk.as_uri(),'sha256':sha(apk),'size':apk.stat().st_size},
  'client':{'version':'1.0.0','url':client.as_uri(),'sha256':sha(client),'size':client.stat().st_size},
}
(tmp/'channel.json').write_text(json.dumps(channel),encoding='utf-8')
print('FURINA_R39_FIXTURE_READY')
PY

HOME="$TMP/home" FURINA_HOME="$TMP/home/.furina-agent" PREFIX="$TMP/prefix" FURINA_TEST_MODE=1 \
  python3 "$CLIENT" update --channel-file "$TMP/channel.json"

test "$(cat "$TMP/home/.furina-agent/data/keep.txt")" = user-data-survives
grep -Fq 'VERSION = "1.0.0-rc69"' "$TMP/home/.furina-agent/core/furina_agent/version.py"
grep -Fq "versionName '1.0.0-rc57'" "$TMP/home/.furina-agent/bridge/app/build.gradle"
test -s "$TMP/home/.furina-agent/updater/update_client.py"
test -x "$TMP/prefix/bin/furina-update"
test "$(cat "$TMP/home/.furina-agent/data/pending_apk_bundle")" = furina-2026.08.23-rc69-rc57
test ! -e "$TMP/home/.furina-agent/data/furinahub_apk_bundle"

HOME="$TMP/home" FURINA_HOME="$TMP/home/.furina-agent" PREFIX="$TMP/prefix" FURINA_TEST_MODE=1 \
  python3 "$TMP/home/.furina-agent/updater/update_client.py" confirm-apk wrong-bundle
test ! -e "$TMP/home/.furina-agent/data/furinahub_apk_bundle"
HOME="$TMP/home" FURINA_HOME="$TMP/home/.furina-agent" PREFIX="$TMP/prefix" FURINA_TEST_MODE=1 \
  python3 "$TMP/home/.furina-agent/updater/update_client.py" confirm-apk furina-2026.08.23-rc69-rc57
test "$(cat "$TMP/home/.furina-agent/data/furinahub_apk_bundle")" = furina-2026.08.23-rc69-rc57

# Second update is a fast no-op: no snapshot replay, no plugin reinstall, no APK redownload.
rm -f "$TMP/home/FurinaHub-v1.0.0-rc57.apk"
HOME="$TMP/home" FURINA_HOME="$TMP/home/.furina-agent" PREFIX="$TMP/prefix" FURINA_TEST_MODE=1 \
  python3 "$TMP/home/.furina-agent/updater/update_client.py" update --channel-file "$TMP/channel.json" \
  | tee "$TMP/second.log"
grep -Fq 'Tidak ada pembaruan terbaru' "$TMP/second.log"
test ! -e "$TMP/home/FurinaHub-v1.0.0-rc57.apk"

python3 - "$CLIENT" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(encoding='utf-8')
assert 'PROTOCOL = "furina-update/1"' in text
assert 'installed_is_current' in text
assert 'commit_snapshot' in text
assert 'maybe_reexec' in text
assert 'safe_extract' in text
assert 'pending_apk_bundle' in text
assert 'runtime-r38' not in text
print('FURINA_R39_SINGLE_PIPELINE_STATIC_OK')
PY
printf '%s\n' FURINA_RUNTIME_R39_VALIDATION_OK
