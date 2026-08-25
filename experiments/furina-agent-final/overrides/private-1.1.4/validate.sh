#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.3/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.4/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py
grep -Fq 'VERSION = "1.1.13"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_FINAL_114_AUTHORITATIVE_BUNDLE_STATE' "$ROOT/core/furina_agent/hub.py"
state_home="$(mktemp -d)"
HOME="$state_home" FURINA_HOME="$state_home" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json
from pathlib import Path
from furina_agent.config import HOME
(HOME / 'data').mkdir(parents=True, exist_ok=True)
(HOME / 'data' / 'dependency_revision').write_text('stale-r62\n')
(HOME / 'data' / 'bundle_id').write_text('stale-bundle\n')
(HOME / 'data' / 'installed_bundle.json').write_text(json.dumps({
  'bundle_id':'furina-2026.08.25-private-1.1.13',
  'core_version':'1.1.13',
  'core_revision':'2026.08.25-r63',
}))
from furina_agent.hub import Runtime
snapshot=Runtime().system_snapshot()
assert snapshot['bundle_synced'] is True, snapshot
assert snapshot['bundle_id'].endswith('1.1.13'), snapshot
assert snapshot['dependency_revision']=='2026.08.25-r63', snapshot
print('FURINA_FINAL_114_CORE_STATE_OK')
PY
python3 - "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java" <<'PY'
import sys
text=open(sys.argv[1],encoding='utf-8').read()
assert 'state.optBoolean("bundle_synced", false)' in text
assert 'APK FurinaHub belum dipasang' not in text
assert 'confirmInstalledApkIfAllowed();' in text
assert 'if (granted) confirmInstalledApkIfAllowed();' in text
print('FURINA_FINAL_114_ANDROID_STATE_OK')
PY
tmp_client="$(mktemp)"
python3 "$PROJECT/overrides/runtime-private-1.1.4/build_client.py" "$PROJECT/overrides/runtime-r39/update_client.py" "$tmp_client"
python3 - "$tmp_client" <<'PY'
import importlib.util,json,tempfile
from pathlib import Path
import sys
spec=importlib.util.spec_from_file_location('client',sys.argv[1]); client=importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
with tempfile.TemporaryDirectory() as raw:
    root=Path(raw)/'home/.furina-agent'; root.mkdir(parents=True)
    client._furina_114_install_core=lambda *args,**kwargs: False
    channel={'bundle_id':'furina-2026.08.25-private-1.1.13','core':{'version':'1.1.13','revision':'2026.08.25-r63'}}
    assert client.install_core(root,channel,Path(raw),None,force=False) is False
    assert (root/'data/dependency_revision').read_text().strip()=='2026.08.25-r63'
    assert (root/'data/bundle_id').read_text().strip()==channel['bundle_id']
print('FURINA_FINAL_114_UPDATER_STATE_OK')
PY
echo FURINA_FINAL_114_VALIDATION_OK
