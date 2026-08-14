#!/usr/bin/env bash
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
META="$REPO/experiments/furina-agent-final"
RC35="$META/overrides/rc35"
BASE_COMMIT="118ced8b64858a2448ecd01d15c098049a1ec32e"
BASE_WORK=/tmp/furinahub-rc34-base
ROOT=/tmp/furina-agent-rc34-validate/termux

rm -rf "$BASE_WORK"
git worktree add --detach "$BASE_WORK" "$BASE_COMMIT" >/dev/null
cleanup() {
  git worktree remove --force "$BASE_WORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

(
  cd "$BASE_WORK"
  bash experiments/furina-agent-final/overrides/rc34/validate.sh
)

test -d "$ROOT/core/furina_agent"
python3 "$RC35/apply.py" "$ROOT" "$RC35"
python3 -m compileall -q "$ROOT/core/furina_agent"

TEST_HOME=/tmp/furinahub-rc35-home
rm -rf "$TEST_HOME"
mkdir -p "$TEST_HOME"

FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from pathlib import Path
from types import SimpleNamespace
import tempfile

from furina_agent.version import VERSION
from furina_agent.hub_settings import (
    PRESETS, defaults, normalize, personalization_prompt,
    skill_allows_action, effective_device_mode,
)
from furina_agent.intent_guard import conversation_frame, strong_device_request
from furina_agent.policy import build_goal_lock, classify_action
from furina_agent.hub_web import HTML

assert VERSION == "1.0.0-rc35"
assert "tsundere" in PRESETS and "adaptive" in PRESETS
assert "Ringkasan Hubungan" not in HTML
assert "Personalisasi" in HTML and "Skill Agent" in HTML
assert "Update & Diagnostik" in HTML

s=defaults()
assert s["assistant_name"] == "Furina"
assert s["base_style"] == "adaptive"
assert s["device_control_mode"] == "normal"
assert skill_allows_action("open_app", s)
s["agent_skills"]["android_navigation"] = False
assert not skill_allows_action("open_app", s)
s["agent_skills"]["android_navigation"] = True
s["device_control_mode"] = "root"
assert effective_device_mode(s) == "normal"
s["agent_skills"]["privileged_controls"] = True
assert effective_device_mode(s) == "root"

p=normal = normalize({"base_style":"tsundere","characteristics":{"sarcasm":999,"warmth":-9}})
assert p["characteristics"]["sarcasm"] == 100
assert p["characteristics"]["warmth"] == 0
prompt=personalization_prompt(p)
assert "EXPRESSION BIAS" in prompt
assert "tidak pernah memberi izin kontrol perangkat" in prompt
assert "persona kaku" in prompt

assert conversation_frame("WhatsApp sekarang sering lambat menurutmu kenapa?")
assert not strong_device_request("WhatsApp sekarang sering lambat menurutmu kenapa?")
assert strong_device_request("Bisa buka WhatsApp?")

apps=[{"label":"WhatsApp","package":"com.whatsapp"}]
lock=build_goal_lock("buka WhatsApp cari Ariel",apps,[{"type":"open_app","package":"com.whatsapp"}])
assert classify_action(
    {"package":"com.whatsapp","nodes":[{"id":9,"text":"Send"}]},
    {"type":"tap_node","node":9}, lock
)[0] == "blocked"

import furina_agent.tool_runtime as tr
src=Path(tr.__file__).read_text(encoding="utf-8")
assert "agent_skill_disabled" in src and "policy_preserved" in src

import furina_agent.agent as agentmod
asrc=Path(agentmod.__file__).read_text(encoding="utf-8")
assert 'skill_enabled("vision_fallback"' in asrc
assert "effective_device_mode" in asrc

import furina_agent.chat as chatmod
csrc=Path(chatmod.__file__).read_text(encoding="utf-8")
assert "personalization_prompt()" in csrc

from furina_agent.hub import HUB_HOST,HUB_PORT
assert HUB_HOST == "127.0.0.1"
assert HUB_PORT == 8787
import furina_agent.hub as hubmod
hsrc=Path(hubmod.__file__).read_text(encoding="utf-8")
assert '/api/update/core' in hsrc and '/api/update/status' in hsrc
assert 'dependency_revision' in hsrc
assert 'shutil.which("furina")' in hsrc

print("RC35_CORE_PERSONALIZATION_SKILLS_POLICY_OK")
PY

# Verify server is loopback-only and serves chat-first UI.
HUB_TEST_TOKEN="rc35-test-token-0123456789abcdef0123456789"
FURINA_HOME="$TEST_HOME/server" PYTHONPATH="$ROOT/core" python3 -m furina_agent.hub --token "$HUB_TEST_TOKEN" >/tmp/furinahub-server.log 2>&1 &
HUB_PID=$!
trap 'kill "$HUB_PID" >/dev/null 2>&1 || true; cleanup' EXIT
for _ in $(seq 1 25); do
  if curl -fsS "http://127.0.0.1:8787/health?access=$HUB_TEST_TOKEN" >/tmp/hub-health.json 2>/dev/null; then break; fi
  sleep 0.2
done
grep -q '"app":"FurinaHub"' /tmp/hub-health.json
if curl -fsS "http://127.0.0.1:8787/" >/dev/null 2>&1; then
  echo "FurinaHub root accepted request without session token" >&2
  exit 1
fi
if curl -fsS "http://127.0.0.1:8787/api/memory" >/dev/null 2>&1; then
  echo "FurinaHub API accepted request without session token" >&2
  exit 1
fi
curl -fsS "http://127.0.0.1:8787/?access=$HUB_TEST_TOKEN" >/tmp/hub.html
grep -q 'id="chat" class="chatview active"' /tmp/hub.html
grep -q 'Personalisasi' /tmp/hub.html
! grep -q 'Ringkasan Hubungan' /tmp/hub.html
kill "$HUB_PID" >/dev/null 2>&1 || true

MANIFEST="$ROOT/bridge/app/src/main/AndroidManifest.xml"
MAIN="$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
GRADLE="$ROOT/bridge/app/build.gradle"
UPDATER="$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/BridgeUpdater.java"

grep -q 'android:label="FurinaHub"' "$MANIFEST"
grep -q 'com.termux.permission.RUN_COMMAND' "$MANIFEST"
grep -q '<package android:name="com.termux"' "$MANIFEST"
grep -q 'android:usesCleartextTraffic="true"' "$MANIFEST"
grep -q 'versionCode 10019' "$GRADLE"
grep -q "versionName '1.0.0-rc19'" "$GRADLE"
grep -q 'http://127.0.0.1:8787/' "$MAIN"
grep -q 'com.termux.RUN_COMMAND' "$MAIN"
grep -q 'setAllowFileAccess(false)' "$MAIN"
grep -q 'setAllowContentAccess(false)' "$MAIN"
grep -q 'FurinaNative' "$MAIN"
grep -q 'appUpdateStatus' "$MAIN"
grep -q 'appUpdateBusy' "$MAIN"
grep -q 'monitorAppUpdate' "$MAIN"
! grep -q 'runFixedTermux(.*sh' "$MAIN"
grep -q 'MANIFEST_URL' "$UPDATER"
grep -q 'furinahub-update-check' "$UPDATER"
grep -q 'furinahub-update-download' "$UPDATER"

python3 - "$META/manifest.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1],encoding="utf-8"))
assert m["version"]=="1.0.0-rc35"
assert m["hub_name"]=="FurinaHub"
assert m["hub_host"]=="127.0.0.1" and int(m["hub_port"])==8787
assert m["dependency_revision"]=="2026.08.14-r1"
assert m["bridge_version"]=="1.0.0-rc19"
assert int(m["bridge_version_code"])==10019
assert m["bridge_release_base"].endswith("/furinahub-v1.0.0-rc19")
PY

bash -n "$META/install.sh"
grep -q 'VERSION="1.0.0-rc35"' "$META/install.sh"
grep -q 'DEPENDENCY_REVISION="2026.08.14-r1"' "$META/install.sh"
grep -q 'allow-external-apps=true' "$META/install.sh"
grep -q 'furina-hub' "$META/install.sh"
grep -q 'FurinaHub.apk' "$META/install.sh"
grep -q 'furinahub_apk_revision' "$META/install.sh"
grep -q 'Keep the currently running FurinaHub UI alive' "$META/install.sh"

for f in apply.py hub_settings.py hub.py hub_web.py MainActivity.java; do
  test -f "$RC35/$f"
done

python3 - "$META/install.sh" "$RC35" <<'PY'
import hashlib,pathlib,re,sys
installer=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')
root=pathlib.Path(sys.argv[2])
keys={
 'APPLY_BLOB':'apply.py',
 'SETTINGS_BLOB':'hub_settings.py',
 'HUB_BLOB':'hub.py',
 'WEB_BLOB':'hub_web.py',
 'MAIN_ACTIVITY_BLOB':'MainActivity.java',
}
def blob(data): return hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
for key,name in keys.items():
    m=re.search(rf'^{key}="([0-9a-f]+)"$',installer,re.M)
    assert m, key
    actual=blob((root/name).read_bytes())
    assert actual==m.group(1),(key,actual,m.group(1))
print('RC35_INSTALLER_BLOB_BINDINGS_OK')
PY

echo "RC35_FURINAHUB_FULL_VALIDATION_OK"
