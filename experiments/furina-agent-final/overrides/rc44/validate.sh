#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux
bash "$ROOT/overrides/rc43/validate.sh"
python3 "$HERE/apply.py" "$STAGE" "$HERE"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
FURINA_HOME="$TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
from furina_agent.version import VERSION
from furina_agent.hub import Runtime
assert VERSION == "1.0.0-rc44"
assert Runtime._connector_is_read_action("github.get_issue")
assert Runtime._connector_is_read_action("drive.lookupFile")
assert not Runtime._connector_is_read_action("gmail.sendEmail")
assert not Runtime._connector_is_read_action("github.search_and_delete")
assert not Runtime._connector_is_read_action("drive.update_file")
print("FURINAHUB_CORE_RC44_CLASSIFIER_OK")
PY

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/"core/furina_agent/hub.py").read_text(encoding="utf-8")
version=(root/"core/furina_agent/version.py").read_text(encoding="utf-8")
assert 'VERSION = "1.0.0-rc44"' in version
for marker in (
    '"bridge_target": "1.0.0-rc28"',
    'all_actions = self._connector_action_items',
    'file unduhan bukan GGUF yang valid',
    'self.store.add_message("user", text)',
    'self.store.add_message("assistant", answer or "Selesai.")',
    '"jobs": active_jobs',
):
    assert marker in hub, marker
print("FURINAHUB_CORE_RC44_REGRESSION_OK")
PY

python3 -m compileall -q "$STAGE/core/furina_agent"
