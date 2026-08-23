#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/android-rc56/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
bash -n "$HERE/install-body.sh"

python3 - "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import sys
t=Path(sys.argv[1]).read_text(encoding='utf-8')
required=(
    'FURINA_RUNTIME_CONTRACT="furina-runtime/v4-channel-snapshot"',
    'VERSION="1.0.0-rc68"',
    'DEPENDENCY_REVISION="2026.08.23-r38"',
    'BUNDLE_ID="furina-2026.08.23-rc68-rc56"',
    'fetch_target_bundle',
    'validate_archive',
    'validate_stage',
    'snapshot-manifest-r38.json',
    'furina-update-apk',
    'furina-apk-confirm',
)
assert all(x in t for x in required)
assert 'printf \'%s\\n\' "$BUNDLE_ID" >"$marker"' not in t
assert 'Do not mark the bundle installed here' in t
print('FURINA_RUNTIME_R38_STATIC_OK')
PY

# Reconstruct the release snapshot from the same validated RC68/RC56 tree.
TMP="$(mktemp -d /tmp/furina-r38-validate.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
cp -a "$STAGE/core" "$STAGE/bridge" "$TMP/"
find "$TMP" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$TMP" -type f -name '*.pyc' -delete
rm -rf "$TMP/bridge/.gradle" "$TMP/bridge/app/build"
tar --sort=name --mtime='UTC 2026-08-23 00:00:00' --owner=0 --group=0 --numeric-owner -cf "$TMP/furina-core-bridge-rc68-rc56.tar" -C "$TMP" core bridge
python3 - "$TMP/furina-core-bridge-rc68-rc56.tar" <<'PY'
import pathlib,tarfile,sys
p=pathlib.Path(sys.argv[1])
with tarfile.open(p,'r:') as a:
    names=a.getnames()
    assert 'core/furina_agent/version.py' in names
    assert 'bridge/app/build.gradle' in names
print('FURINA_RUNTIME_R38_SNAPSHOT_BUILD_OK')
PY

# Fast-path fixture proves APK installer launch is not treated as installation.
FIX="$TMP/fixture"
mkdir -p "$FIX/home/.furina-agent/core/furina_agent" "$FIX/home/.furina-agent/bridge" \
         "$FIX/home/.furina-agent/data" "$FIX/home/.furina-agent/run" "$FIX/home/.furina-agent/logs" \
         "$FIX/home/.furina-agent/openconnector/src/server" "$FIX/home/.furina-agent/openconnector/node_modules" \
         "$FIX/home/.termux" "$FIX/bin" "$FIX/prefix/bin"
printf 'VERSION = "1.0.0-rc68"\n' >"$FIX/home/.furina-agent/core/furina_agent/version.py"
printf '%s\n' '2026.08.23-r38' >"$FIX/home/.furina-agent/data/dependency_revision"
printf '%s\n' 'd478400141c33bb5ddf823e09b293e9d7154da97' >"$FIX/home/.furina-agent/data/openconnector_revision"
printf 'x\n' >"$FIX/home/.furina-agent/openconnector/src/server/index.ts"
printf 'allow-external-apps=true\n' >"$FIX/home/.termux/termux.properties"
printf '{"bundle_id":"furina-2026.08.23-rc68-rc56","files":{}}\n' >"$FIX/home/.furina-agent/data/snapshot-manifest-r38.json"
printf 'fixture-apk\n' >"$FIX/apk"
APK_SHA="$(sha256sum "$FIX/apk" | awk '{print $1}')"
cat >"$FIX/bundle.json" <<JSON
{"schema":2,"bundle_id":"furina-2026.08.23-rc68-rc56","core_version":"1.0.0-rc68","dependency_revision":"2026.08.23-r38","bridge_version":"1.0.0-rc56","bridge_version_code":10056,"package_name":"com.wynndev.furinaagentbridge","apk_url":"https://fixture/FurinaHub.apk","apk_sha256":"$APK_SHA","snapshot_asset":"furina-core-bridge-rc68-rc56.tar","snapshot_sha256":"$(sha256sum "$TMP/furina-core-bridge-rc68-rc56.tar" | awk '{print $1}')"}
JSON
cat >"$FIX/bin/curl" <<SH
#!/usr/bin/env bash
set -euo pipefail
out=""
url="\${@: -1}"
args=("\$@")
for ((i=0;i<\${#args[@]};i++)); do
  [[ "\${args[i]}" == "-o" ]] && out="\${args[i+1]}"
done
[[ -n "\$out" ]]
if [[ "\$url" == *bundle.json* ]]; then cp "$FIX/bundle.json" "\$out"; printf 200
elif [[ "\$url" == *FurinaHub.apk* ]]; then cp "$FIX/apk" "\$out"; printf 200
else exit 22
fi
SH
cat >"$FIX/bin/termux-open" <<SH
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"$FIX/open.log"
SH
cat >"$FIX/prefix/bin/furina" <<'SH'
#!/usr/bin/env bash
exit 0
SH
cat >"$FIX/prefix/bin/furina-apk-confirm" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod 755 "$FIX/bin/"* "$FIX/prefix/bin/"*
HOME="$FIX/home" PREFIX="$FIX/prefix" PATH="$FIX/prefix/bin:$FIX/bin:$PATH" FURINA_UPDATE_SOURCE=termux FURINAHUB_MACHINE_PROGRESS=1 \
  bash "$HERE/install-body.sh" >/dev/null
test "$(wc -l <"$FIX/open.log")" -eq 1
test ! -e "$FIX/home/.furina-agent/data/furinahub_apk_bundle"
HOME="$FIX/home" PREFIX="$FIX/prefix" PATH="$FIX/prefix/bin:$FIX/bin:$PATH" "$FIX/prefix/bin/furina-apk-confirm" wrong-bundle
test ! -e "$FIX/home/.furina-agent/data/furinahub_apk_bundle"
HOME="$FIX/home" PREFIX="$FIX/prefix" PATH="$FIX/prefix/bin:$FIX/bin:$PATH" "$FIX/prefix/bin/furina-apk-confirm" furina-2026.08.23-rc68-rc56
test "$(cat "$FIX/home/.furina-agent/data/furinahub_apk_bundle")" = furina-2026.08.23-rc68-rc56
HOME="$FIX/home" PREFIX="$FIX/prefix" PATH="$FIX/prefix/bin:$FIX/bin:$PATH" FURINA_UPDATE_SOURCE=termux FURINAHUB_MACHINE_PROGRESS=1 \
  bash "$HERE/install-body.sh" >/dev/null
test "$(wc -l <"$FIX/open.log")" -eq 1
printf '%s\n' FURINA_RUNTIME_R38_APK_CONFIRMATION_OK
