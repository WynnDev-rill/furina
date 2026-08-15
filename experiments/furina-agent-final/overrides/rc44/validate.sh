#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux
bash "$ROOT/overrides/rc43/validate.sh"
python3 "$HERE/apply.py" "$STAGE" "$HERE"
python3 "$HERE/audit-extra.py" "$STAGE"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
FURINA_HOME="$TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
import tempfile
from pathlib import Path
from furina_agent.version import VERSION
from furina_agent.hub import Runtime
from furina_agent.direct_control import _SENSITIVE
from furina_agent.memory import MemoryStore

assert VERSION == "1.0.0-rc44"
assert Runtime._connector_is_read_action("github.get_issue")
assert Runtime._connector_is_read_action("drive.lookupFile")
assert not Runtime._connector_is_read_action("gmail.sendEmail")
assert not Runtime._connector_is_read_action("github.search_and_delete")
assert not Runtime._connector_is_read_action("drive.update_file")
assert _SENSITIVE.search("tekan Call")
assert _SENSITIVE.search("klik Izinkan")
assert _SENSITIVE.search("tap Confirm")

store=MemoryStore(Path(tempfile.mkdtemp())/"memory.db")
second=store.create_conversation("kedua")
third=store.create_conversation("ketiga")
store.switch_conversation(third)
assert store.delete_conversation(second)==third
assert store.active_conversation_id()==third
print("FURINAHUB_CORE_RC44_BEHAVIOR_OK")
PY

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
hub=(root/"core/furina_agent/hub.py").read_text(encoding="utf-8")
routing=(root/"core/furina_agent/routing.py").read_text(encoding="utf-8")
direct=(root/"core/furina_agent/direct_control.py").read_text(encoding="utf-8")
memory=(root/"core/furina_agent/memory.py").read_text(encoding="utf-8")
version=(root/"core/furina_agent/version.py").read_text(encoding="utf-8")
assert 'VERSION = "1.0.0-rc44"' in version
for marker in (
    '"bridge_target": "1.0.0-rc28"',
    'all_actions = self._connector_action_items',
    'file unduhan bukan GGUF yang valid',
    'self.store.add_message("user", text)',
    'self.store.add_message("assistant", answer or "Selesai.")',
    '"jobs": active_jobs',
    'semantic_steps=semantic_steps',
):
    assert marker in hub, marker
assert 'shutil.which("furina")' in routing
assert 'Model lokal belum aktif atau tidak dapat dimulai.' in routing
assert 'call|dial|telepon' in direct
assert 'if value != active:' in memory
print("FURINAHUB_CORE_RC44_REGRESSION_OK")
PY

python3 -m compileall -q "$STAGE/core/furina_agent"
