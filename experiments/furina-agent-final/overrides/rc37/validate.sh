#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc36/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$HERE/apply.py" "$STAGE" "$HERE"
FURINA_HOME=/tmp/furinahub-rc37-home PYTHONPATH="$STAGE/core" python3 - <<'PY'
import tempfile
from pathlib import Path
from furina_agent.version import VERSION
from furina_agent.hub_settings import defaults, effective_device_mode, normalize

assert VERSION == "1.0.0-rc37"
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
with tempfile.TemporaryDirectory() as tmp:
    log = Path(tmp) / "update.log"
    log.write_text("\x1b[31m× Memeriksa dependency terkelola\x1b[0m\nE: repository sedang tidak tersedia\nLog: /tmp/x\n", encoding="utf-8")
    detail = runtime._update_failure_detail(log)
    assert "repository sedang tidak tersedia" in detail and "\x1b" not in detail
src = Path(runtime.__class__.__module__.replace(".", "/"))
print("FURINAHUB_CORE_RC37_VALIDATED")
PY

python3 - "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import sys

body = Path(sys.argv[1]).read_text(encoding="utf-8")
section = body.split("reconcile_dependencies() {", 1)[1].split("\nenable_termux_integration()", 1)[0]
assert section.index("if dependency_health") < section.index("pkg install")
for marker in (
    "packages+=(python)", "packages+=(curl)", "pkg update -y",
    "Dependency python, curl, dan rich sudah sehat; repository tidak disentuh.",
    "dependency_health ||",
):
    assert marker in section, marker
print("FURINAHUB_RC37_DEPENDENCY_REPAIR_VALIDATED")
PY
