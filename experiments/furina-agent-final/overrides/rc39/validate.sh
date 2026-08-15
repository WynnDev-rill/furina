#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc37/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$ROOT/overrides/rc38/apply.py" "$STAGE" "$ROOT/overrides/rc38"
python3 "$HERE/apply.py" "$STAGE" "$HERE"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
FURINA_HOME="$TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
from pathlib import Path
import tempfile

from furina_agent.memory import MemoryStore
from furina_agent.version import VERSION
from furina_agent.companion import CompanionSession

assert VERSION == "1.0.0-rc39"
store = MemoryStore(Path(tempfile.mkdtemp()) / "memory.db")
first = store.active_conversation_id()
store.add_message("user", "Percakapan pertama")
second = store.create_conversation()
assert second != first and store.message_count() == 0
store.add_message("user", "Percakapan kedua")
assert store.list_conversations()[0]["title"] == "Percakapan kedua"
store.switch_conversation(first)
assert store.recent_messages()[-1]["content"] == "Percakapan pertama"
store.delete_conversation(first)
assert store.active_conversation_id() == second

class FakeLLM:
    def chat(self, *args, **kwargs):
        return '{"mode":"chat","confidence":0.99,"goal":"","steps":[]}'

session = CompanionSession.__new__(CompanionSession)
session.store = store
session.llm = FakeLLM()
session._installed_apps = lambda: [{"label":"YouTube","package":"com.google.android.youtube"}]
intent = session.classify("Buka YouTube dan cari channel MrBeast")
assert intent.mode == "device", intent
assert intent.steps and intent.steps[0]["type"] == "open_app", intent.steps
print("FURINAHUB_RC39_CONVERSATIONS_DEVICE_OK")
PY

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
hub = (root / "core/furina_agent/hub.py").read_text(encoding="utf-8")
for marker in ('/api/conversations', 'body.get("image")', 'llm.vision', 'conversation_id=?'):
    assert marker in hub, marker
print("FURINAHUB_RC39_API_OK")
PY

python3 - <<'PY'
import hashlib, json, pathlib, re
root = pathlib.Path("experiments/furina-agent-final")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
assert manifest["version"] == "1.0.0-rc39"
assert manifest["bridge_version"] == "1.0.0-rc23"
assert manifest["bridge_version_code"] == 10023
bootstrap = (root / "install.sh").read_text(encoding="utf-8")
body_path = root / "overrides/rc39/install-body.sh"
body = body_path.read_bytes()
blob = lambda data: hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
match = re.search(r'^BODY_BLOB="([0-9a-f]{40})"$', bootstrap, re.M)
assert match and match.group(1) == blob(body), (match.group(1) if match else None, blob(body))
bindings = {
    "RC39_APPLY_BLOB": "apply.py", "RC39_HUB_BLOB": "hub.py",
    "RC39_DIRECT_BLOB": "direct_control.py", "RC39_MEMORY_BLOB": "memory.py",
    "RC39_COMPANION_BLOB": "companion.py",
}
body_text = body.decode()
for key, name in bindings.items():
    expected = blob((root / "overrides/rc39" / name).read_bytes())
    assert f'{key}="{expected}"' in bootstrap, (key, expected)
    assert f'{key}="{expected}"' in body_text, (key, expected)
print("FURINAHUB_RC39_INSTALLER_BINDINGS_OK")
PY

python3 -m compileall -q "$STAGE/core/furina_agent"
bash -n experiments/furina-agent-final/install.sh experiments/furina-agent-final/overrides/rc39/install-body.sh
