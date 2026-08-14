#!/usr/bin/env bash
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
META="$REPO/experiments/furina-agent-final"
RC20="$META/overrides/android-rc20"
BASE_COMMIT="059090cc295beb274d162e62e9ea133402ff70e3"
BASE_WORK=/tmp/furinahub-rc35-pinned
ROOT=/tmp/furina-agent-rc34-validate/termux

rm -rf "$BASE_WORK"
git worktree add --detach "$BASE_WORK" "$BASE_COMMIT" >/dev/null
cleanup(){ git worktree remove --force "$BASE_WORK" >/dev/null 2>&1 || true; }
trap cleanup EXIT

(
  cd "$BASE_WORK"
  bash experiments/furina-agent-final/overrides/rc35/validate.sh
)

python3 "$RC20/apply.py" "$ROOT" "$RC20"

MAIN="$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
ASSET="$ROOT/bridge/app/src/main/assets/furinahub/index.html"
MANIFEST="$ROOT/bridge/app/src/main/AndroidManifest.xml"
GRADLE="$ROOT/bridge/app/build.gradle"

test -f "$MAIN" && test -f "$ASSET"
grep -q 'versionCode 10020' "$GRADLE"
grep -q "versionName '1.0.0-rc20'" "$GRADLE"
grep -q 'com.termux.permission.RUN_COMMAND' "$MANIFEST"
grep -q 'loadBundledShell();' "$MAIN"
grep -q 'probeSavedCore();' "$MAIN"
grep -q 'requestPermissions(new String\[\]{RUN_COMMAND}' "$MAIN"
grep -q 'connectionStatus()' "$MAIN"
grep -q 'connectCore()' "$MAIN"
grep -q 'coreRequest(String requestId' "$MAIN"
grep -q 'loadDataWithBaseURL' "$MAIN"
grep -q 'setAllowFileAccess(false)' "$MAIN"
grep -q 'setAllowContentAccess(false)' "$MAIN"
! grep -q 'ensureHub()' "$MAIN"

grep -q 'Hubungkan ke Termux' "$ASSET"
grep -q 'FurinaHub tetap dapat dibuka meski Core Termux sedang mati' "$ASSET"
grep -q 'prefers-reduced-motion' "$ASSET"
grep -q 'min-width:44px' "$ASSET"
grep -q 'Agent & Skill' "$ASSET"
grep -q 'Personalisasi' "$ASSET"
! grep -q 'Ringkasan Hubungan' "$ASSET"
! grep -q 'http://127.0.0.1:8787' "$ASSET"

python3 - "$META/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding='utf-8'))
assert m['version']=='1.0.0-rc35'
assert m['bridge_version']=='1.0.0-rc20'
assert int(m['bridge_version_code'])==10020
assert m['bridge_release_base'].endswith('/furinahub-v1.0.0-rc20')
PY

bash -n "$META/install.sh"
bash -n "$META/overrides/rc35/install-body.sh"
grep -q 'HUB_VERSION="1.0.0-rc20"' "$META/install.sh"
grep -q 'HUB_VERSION="1.0.0-rc20"' "$META/overrides/rc35/install-body.sh"
grep -q "version_code.*10020\|version_code')==10020\|version_code'\])==10020" "$META/overrides/rc35/install-body.sh" || grep -q "version_code'])==10020" "$META/overrides/rc35/install-body.sh"

python3 - "$META/install.sh" "$META/overrides/rc35/install-body.sh" <<'PY'
import hashlib,pathlib,re,sys
bootstrap=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
body=pathlib.Path(sys.argv[2]).read_bytes()
actual=hashlib.sha1(f'blob {len(body)}\0'.encode()+body).hexdigest()
m=re.search(r'^BODY_BLOB="([0-9a-f]+)"$',bootstrap,re.M)
assert m and m.group(1)==actual,(m.group(1) if m else None,actual)
print('FURINAHUB_RC20_INSTALLER_BINDING_OK')
PY

python3 - "$MAIN" <<'PY'
from pathlib import Path
import re,sys
s=Path(sys.argv[1]).read_text(encoding='utf-8')
m=re.search(r'protected void onCreate\(Bundle savedInstanceState\) \{(.*?)\n    \}',s,re.S)
assert m
body=m.group(1)
assert 'loadBundledShell();' in body
assert 'probeSavedCore();' in body
assert 'startCoreConnection();' not in body
assert 'beginConnect();' not in body
print('FURINAHUB_RC20_NO_AUTO_TERMUX_START_OK')
PY

echo "FURINAHUB_ANDROID_RC20_FULL_VALIDATION_OK"
