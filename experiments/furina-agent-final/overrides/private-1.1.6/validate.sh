#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"; PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.5/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.6/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py
grep -Fq 'VERSION = "1.1.15"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10083' "$ROOT/bridge/app/build.gradle"
python3 - "$ROOT/bridge/app/src/main/assets/furinahub/index.html" <<'PY'
import sys
text=open(sys.argv[1],encoding='utf-8').read()
for token in ('FURINA_FINAL_116_TERMUX_STATE_RENDER','function renderAgent(){}','modelsTermuxState116','personalTermuxState116','id="localModelRows"','id="providerRows"','id="personalityTraitGrid110"'):
    assert token in text, token
assert "document.getElementById('modeSeg').innerHTML" in text  # historical code remains
assert text.rfind('function renderAgent(){}') > text.rfind("document.getElementById('modeSeg').innerHTML")
assert "id==='personalization'||id==='models'" in text
print('FURINA_FINAL_116_DOM_RENDER_OK')
PY
state_home="$(mktemp -d)"
HOME="$state_home" FURINA_HOME="$state_home" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json
from furina_agent.config import HOME
(HOME/'data').mkdir(parents=True,exist_ok=True)
(HOME/'data'/'installed_bundle.json').write_text(json.dumps({'bundle_id':'furina-2026.08.25-private-1.1.15','core_version':'1.1.15','core_revision':'2026.08.25-r65'}))
from furina_agent.hub import Runtime
state=Runtime().public_settings(); system=Runtime().system_snapshot()
assert isinstance(state['model_catalog'],list) and isinstance(state['providers'],list)
assert len(state['personality_traits'])==20
assert system['bundle_synced'] is True,system
print('FURINA_FINAL_116_TERMUX_STATE_OK')
PY
echo FURINA_FINAL_116_VALIDATION_OK
