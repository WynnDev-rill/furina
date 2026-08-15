#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc37/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$HERE/apply.py" "$STAGE" "$HERE"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
FURINA_HOME="$TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
import json
from furina_agent.direct_control import DirectDeviceControl
from furina_agent.config import CONFIG_PATH
from furina_agent.hub import Runtime
from furina_agent.hub_settings import effective_device_mode, load_hub_settings, save_hub_settings
from furina_agent.version import VERSION

assert VERSION == "1.0.0-rc38"

class FakeBridge:
    def __init__(self): self.calls = []
    def health(self): return {"foreground": "com.example", "accessibility": True}
    def control(self, payload):
        self.calls.append(payload)
        return {"ok": True, "message": "Shizuku siap", "mode": payload.get("mode")}
    def control_status(self):
        return {"ok": True, "shizuku_available": True, "shizuku_ready": True,
                "root_ready": False, "detail": "Shizuku API bridge siap"}

runtime = Runtime()
runtime.session.bridge = FakeBridge()
runtime.rebuild = lambda: None
saved = runtime.save_settings({
    "hub": {"device_control_mode": "shizuku"},
    "core": {"device_control_mode": "shizuku"},
})
assert saved["hub"]["device_control_mode"] == "shizuku"
assert json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["device_control_mode"] == "shizuku"
result = runtime.probe_device_mode({"mode": "shizuku"})
assert result["device"]["effective_mode"] == "shizuku", result
assert runtime.session.bridge.calls[-1]["type"] == "prepare_shizuku"
assert result["skills"]["privileged_controls"] is True

# Perubahan langsung dari Termux harus kembali terlihat di FurinaHub.
raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
raw["device_control_mode"] = "root"
CONFIG_PATH.write_text(json.dumps(raw), encoding="utf-8")
public = runtime.public_settings()
assert public["core"]["device_control_mode"] == "root"
assert public["hub"]["device_control_mode"] == "root"

settings = load_hub_settings()
settings["device_control_mode"] = "shizuku"
settings["agent_skills"]["privileged_controls"] = True
settings["device_access"]["shizuku"]["verified"] = False
assert effective_device_mode(settings) == "normal"
settings["device_access"]["shizuku"]["verified"] = True
assert effective_device_mode(settings) == "shizuku"
save_hub_settings(settings)
class Config:
    device_control_mode = "shizuku"
control = DirectDeviceControl(Config(), None, runtime.session.bridge)
assert control._mode() == "shizuku"
print("FURINAHUB_RC38_SYNC_SHIZUKU_OK")
PY

python3 - <<'PY'
import hashlib, json, pathlib, re
root = pathlib.Path("experiments/furina-agent-final")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
assert manifest["version"] == "1.0.0-rc38"
assert manifest["bridge_version"] == "1.0.0-rc22"
assert manifest["bridge_version_code"] == 10022
bootstrap = (root / "install.sh").read_text(encoding="utf-8")
body_path = root / "overrides/rc38/install-body.sh"
body = body_path.read_bytes()
blob = lambda data: hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
match = re.search(r'^BODY_BLOB="([0-9a-f]{40})"$', bootstrap, re.M)
assert match and match.group(1) == blob(body), (match.group(1) if match else None, blob(body))
bindings = {"RC38_APPLY_BLOB": "apply.py", "RC38_HUB_BLOB": "hub.py",
            "RC38_DIRECT_BLOB": "direct_control.py"}
body_text = body.decode()
for key, name in bindings.items():
    expected = blob((root / "overrides/rc38" / name).read_bytes())
    assert f'{key}="{expected}"' in bootstrap
    assert f'{key}="{expected}"' in body_text
print("FURINAHUB_RC38_INSTALLER_BINDINGS_OK")
PY

bash -n experiments/furina-agent-final/install.sh experiments/furina-agent-final/overrides/rc38/install-body.sh
