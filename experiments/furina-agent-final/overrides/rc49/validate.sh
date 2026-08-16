#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc48/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 "$HERE/harden.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py" "$HERE/harden.py"
python3 -m compileall -q "$STAGE/core/furina_agent"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
FURINA_HOME="$TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
from furina_agent.hub import Runtime
from furina_agent.version import VERSION

assert VERSION == '1.0.0-rc49'
assert Runtime._connector_category({'id':'DEVELOPER_TOOLS','displayName':'Developer Tools'}) == 'Developer Tools'
assert Runtime._connector_category({'ID':'DATA','DISPLAYNAME':'Data'}) == 'Data'
assert Runtime._connector_category(['SCIENCE']) == 'SCIENCE'
# Every documented local auth contract must normalize without UI-specific assumptions.
noauth=Runtime._connector_auth_specs({'auth':[{'type':'no_auth'}]})
assert noauth == [{'type':'no_auth','fields':[]}]
api=Runtime._connector_auth_specs({'auth':[{'type':'api_key','extraFields':[{'key':'region','label':'Region','required':False}]}]})
assert api[0]['type']=='api_key'
assert [f['key'] for f in api[0]['fields']] == ['apiKey','region']
assert api[0]['fields'][0]['secret'] is True
custom=Runtime._connector_auth_specs({'auth':[{'type':'custom_credential','fields':[{'key':'host','label':'Host'},{'key':'password','label':'Password'}]}]})
assert [f['key'] for f in custom[0]['fields']] == ['host','password']
assert custom[0]['fields'][1]['secret'] is True
oauth=Runtime._connector_auth_specs({'auth':[{'type':'oauth2','clientConfigFields':[{'key':'tenant','label':'Tenant','required':False}]}]})
assert [f['key'] for f in oauth[0]['fields']] == ['clientId','clientSecret','tenant']
assert oauth[0]['fields'][1]['required'] is False
# Future/unknown auth contracts are not guessed; they are exposed as unsupported instead of crashing.
unknown=Runtime._connector_auth_specs({'auth':[{'type':'something_future'}]})
assert unknown == []
clean=Runtime._connector_validate_values(api[0], {'apiKey':'  secret  ','region':' id '})
assert clean == {'apiKey':'secret','region':'id'}
try:
    Runtime._connector_validate_values(api[0], {'region':'id'})
except ValueError:
    pass
else:
    raise AssertionError('required API key was not enforced')
print('FURINAHUB_CORE_RC49_AUTH_CONTRACT_OK')
PY

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/'core/furina_agent/hub.py').read_text(encoding='utf-8')
version=(root/'core/furina_agent/version.py').read_text(encoding='utf-8')
assert 'VERSION = "1.0.0-rc49"' in version
for marker in (
    '"bridge_target": "1.0.0-rc32"',
    'def _connector_auth_specs(',
    'def _connector_connections(',
    'lowered.get("displayname")',
    '"connected": connected',
    '"ready": ready',
    '"no_auth": no_auth',
    '"flow": "credential"',
    '"flow": "oauth_setup"',
    '"flow": "oauth_browser"',
    '"authType": mode',
):
    assert marker in hub, marker
print('FURINAHUB_CORE_RC49_REGRESSION_OK')
PY
