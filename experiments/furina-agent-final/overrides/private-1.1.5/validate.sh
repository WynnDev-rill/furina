#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"; PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.4/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.5/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py
grep -Fq 'VERSION = "1.1.14"' "$ROOT/core/furina_agent/version.py"
python3 - "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java" <<'PY'
import sys
text=open(sys.argv[1],encoding='utf-8').read()
assert 'handler.post(this::notifyShellConnection);' in text
assert 'setConnection("mismatch"' not in text
assert 'versionCode 10082' not in text  # Java must not own Gradle version
print('FURINA_FINAL_115_PAIRING_NOT_BLOCKED_OK')
PY
grep -Fq 'versionCode 10082' "$ROOT/bridge/app/build.gradle"
state_home="$(mktemp -d)"
HOME="$state_home" FURINA_HOME="$state_home" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json
from furina_agent.config import HOME
(HOME / 'data').mkdir(parents=True, exist_ok=True)
(HOME / 'data' / 'installed_bundle.json').write_text(json.dumps({
  'bundle_id':'furina-2026.08.25-private-1.1.14',
  'core_version':'1.1.14',
  'core_revision':'2026.08.25-r64',
}))
from furina_agent.hub import Runtime
snapshot=Runtime().system_snapshot()
assert snapshot['bundle_synced'] is True, snapshot
assert snapshot['bridge_target']=='1.1.14', snapshot
assert snapshot['dependency_revision']=='2026.08.25-r64', snapshot
print('FURINA_FINAL_115_CORE_STATE_OK')
PY
echo FURINA_FINAL_115_VALIDATION_OK
