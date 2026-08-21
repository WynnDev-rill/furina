#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "$FIXTURE"' EXIT
export FIXTURE
mkdir -p "$FIXTURE/home/.furina-agent/core/furina_agent" "$FIXTURE/home/.furina-agent/data" "$FIXTURE/bin"
printf '%s\n' 'VERSION = "1.0.0-rc62"' >"$FIXTURE/home/.furina-agent/core/furina_agent/version.py"
printf '%s\n' '2026.08.21-r32' >"$FIXTURE/home/.furina-agent/data/dependency_revision"
printf '%s\n' 'signed-apk-fixture' >"$FIXTURE/apk"
APK_SHA="$(sha256sum "$FIXTURE/apk" | awk '{print $1}')"
python3 - "$FIXTURE/bundle.json" "$APK_SHA" <<'PY'
import json,sys
json.dump({
  'schema':1,'bundle_id':'furina-2026.08.21-rc62-rc50',
  'core_version':'1.0.0-rc62','dependency_revision':'2026.08.21-r32',
  'bridge_version':'1.0.0-rc50','bridge_version_code':10050,
  'package_name':'com.wynndev.furinaagentbridge',
  'apk_url':'https://github.com/WynnDev-rill/furina/releases/download/furinahub-v1.0.0-rc50/FurinaHub-v1.0.0-rc50.apk',
  'apk_sha256':sys.argv[2],'signer_sha256':'a'*64,
},open(sys.argv[1],'w'))
PY
cat >"$FIXTURE/bin/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
out=""; url="${!#}"
for ((i=1;i<=$#;i++)); do
  if [[ "${!i}" == "-o" ]]; then j=$((i+1)); out="${!j}"; fi
done
if [[ "$url" == 'http://127.0.0.1:8765/health' ]]; then
  printf '%s' '{"bundle_id":"old-bundle"}'
elif [[ "$url" == *'/bundle.json' ]]; then
  cp "$FIXTURE/bundle.json" "$out"; printf '%s' 200
elif [[ "$url" == *'.apk' ]]; then
  cp "$FIXTURE/apk" "$out"; printf '%s' 200
else
  exit 22
fi
SH
cat >"$FIXTURE/bin/termux-open" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FIXTURE/open.log"
SH
chmod 755 "$FIXTURE/bin/curl" "$FIXTURE/bin/termux-open"

for attempt in 1 2; do
  HOME="$FIXTURE/home" PATH="$FIXTURE/bin:$PATH" FURINA_UPDATE_SOURCE=termux \
    FURINAHUB_MACHINE_PROGRESS=1 bash "$HERE/install-body.sh" >/dev/null
done
test "$(wc -l <"$FIXTURE/open.log")" -eq 1
test "$(cat "$FIXTURE/home/.furina-agent/data/bundle_id")" = 'furina-2026.08.21-rc62-rc50'
test "$(cat "$FIXTURE/home/.furina-agent/data/furinahub_apk_bundle")" = 'furina-2026.08.21-rc62-rc50'
test -s "$FIXTURE/home/FurinaHub-v1.0.0-rc50.apk"
printf '%s\n' FURINA_RUNTIME_R32_APK_SYNC_EXACTLY_ONCE_OK
