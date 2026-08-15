#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/rc36/validate.sh"
STAGE=/tmp/furina-agent-rc34-validate/termux
python3 "$HERE/apply.py" "$STAGE" "$HERE"

python3 - "$STAGE" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
asset = root / "bridge/app/src/main/assets/furinahub/index.html"
java = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
gradle = root / "bridge/app/build.gradle"
html = asset.read_text(encoding="utf-8")
body = java.read_text(encoding="utf-8")
for marker in ("statuschip chat-hidden", "openMessageMenu", "newConversation", "pickAttachment", "probeDeviceMode", "OpenConnector", "addMemoryPrompt", "configureProvider"):
    assert marker in html, marker
assert "Core aktif" in html
assert "statuschip chat-hidden" in html
for marker in ("ACTION_OPEN_DOCUMENT", "MAX_ATTACHMENT_BYTES", "onAttachmentPicked", "setAllowContentAccess(false)"):
    assert marker in body, marker
assert "versionCode 10021" in gradle.read_text(encoding="utf-8")
print("FURINAHUB_ANDROID_RC21_VALIDATED")
PY

python3 - <<'PY'
import hashlib, json, pathlib, re
root = pathlib.Path("experiments/furina-agent-final")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
assert manifest["version"] == "1.0.0-rc36"
assert manifest["bridge_version"] == "1.0.0-rc21"
assert manifest["bridge_version_code"] == 10021
bootstrap = (root / "install.sh").read_text(encoding="utf-8")
body_path = root / "overrides/rc36/install-body.sh"
body = body_path.read_bytes()
blob = lambda data: hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
match = re.search(r'^BODY_BLOB="([0-9a-f]{40})"$', bootstrap, re.M)
assert match and match.group(1) == blob(body), (match.group(1) if match else None, blob(body))
bindings = {
    "RC36_APPLY_BLOB": "apply.py",
    "RC36_SETTINGS_BLOB": "hub_settings.py",
    "RC36_HUB_BLOB": "hub.py",
}
body_text = body.decode()
for key, name in bindings.items():
    expected = blob((root / "overrides/rc36" / name).read_bytes())
    assert f'{key}="{expected}"' in bootstrap
    assert f'{key}="{expected}"' in body_text
print("FURINAHUB_RC36_INSTALLER_BINDINGS_OK")
PY

bash -n experiments/furina-agent-final/install.sh experiments/furina-agent-final/overrides/rc36/install-body.sh
