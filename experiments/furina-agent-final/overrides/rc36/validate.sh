#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BASE_WORK=/tmp/furinahub-rc20-release-base
BASE_COMMIT=25123b82c03e32c52ce51ce09910dc003369999f
rm -rf "$BASE_WORK"
git worktree add --detach "$BASE_WORK" "$BASE_COMMIT" >/dev/null
cleanup(){ git worktree remove --force "$BASE_WORK" >/dev/null 2>&1 || true; }
trap cleanup EXIT
mkdir -p /tmp/furina-validation-home
(
  cd "$BASE_WORK"
  HOME=/tmp/furina-validation-home bash experiments/furina-agent-final/overrides/android-rc20/validate.sh
)
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$HERE/apply.py" "$STAGE" "$HERE"
FURINA_HOME=/tmp/furinahub-rc36-home PYTHONPATH="$STAGE/core" python3 - <<'PY'
import tempfile
from pathlib import Path
from furina_agent.version import VERSION
from furina_agent.hub_settings import defaults, effective_device_mode, normalize

assert VERSION == "1.0.0-rc36"
state = defaults()
state["device_control_mode"] = "root"
state["agent_skills"]["privileged_controls"] = True
assert effective_device_mode(state) == "normal"
state["device_access"]["root"]["verified"] = True
assert effective_device_mode(state) == "root"
assert normalize({"connectors":{"base_url":"https://evil.invalid"}})["connectors"]["base_url"].startswith("http://127.0.0.1:")

from furina_agent.hub import Runtime
runtime = Runtime()
assert runtime.bootstrap()["bridge_target"] == "1.0.0-rc21"
assert runtime._connector_is_read_action("github.get_current_user")
assert not runtime._connector_is_read_action("gmail.send_email")
src = Path(runtime.__class__.__module__.replace(".", "/"))
print("FURINAHUB_CORE_RC36_VALIDATED")
PY
