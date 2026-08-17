#!/usr/bin/env bash
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
META="$REPO/experiments/furina-agent-final"
BASE_WORK=/tmp/furinahub-rc43-base
ROOT=/tmp/furina-agent-rc34-validate/termux
BASE_COMMIT="118ced8b64858a2448ecd01d15c098049a1ec32e"
rm -rf "$BASE_WORK"
git worktree add --detach "$BASE_WORK" "$BASE_COMMIT" >/dev/null
cleanup() { git worktree remove --force "$BASE_WORK" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# The historical base commit predates the offline RC17 hotfix. Copy the
# verified current transform pair into the detached fixture so validation
# never depends on raw.githubusercontent.com being reachable.
cp "$META/overrides/apply-core-rc17.py" "$BASE_WORK/experiments/furina-agent-final/overrides/apply-core-rc17.py"
cp "$META/overrides/apply-core-rc17-hotfix.py" "$BASE_WORK/experiments/furina-agent-final/overrides/apply-core-rc17-hotfix.py"

( cd "$BASE_WORK" && FURINA_HOME=/tmp/furinahub-rc34-base-home bash experiments/furina-agent-final/overrides/rc34/validate.sh )
for rc in rc35 rc36 rc37 rc38 rc39 rc40 rc41 rc42 rc43; do
  python3 "$META/overrides/$rc/apply.py" "$ROOT" "$META/overrides/$rc"
done

TEST_HOME="$(mktemp -d)"
FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json, tempfile
from pathlib import Path
from furina_agent.memory import MemoryStore
from furina_agent.version import VERSION

assert VERSION == "1.0.0-rc43"
store = MemoryStore(Path(tempfile.mkdtemp()) / "memory.db")
mid = store.add_message("user", "Apa isi gambar ini?", attachment={"kind":"image","id":"a"*32,"name":"test.jpg","mime":"image/jpeg"})
row = store._conn().execute("SELECT attachment_json FROM messages WHERE id=?", (mid,)).fetchone()
assert json.loads(row[0])["kind"] == "image"
print("FURINAHUB_CORE_RC43_MEMORY_OK")
PY

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
hub = (Path(sys.argv[1]) / "core/furina_agent/hub.py").read_text(encoding="utf-8")
for marker in ('/api/connectors/plugins', 'MODEL_CATALOG', 'plugin_confirmation', 'FURINAHUB_MACHINE_PROGRESS', 'vision_translation', 'mime=mime', '_wake_connector_runtime', 'Komponen Plugin belum terpasang'):
    assert marker in hub, marker
print("FURINAHUB_CORE_RC43_API_OK")
PY

python3 -m compileall -q "$ROOT/core/furina_agent"
