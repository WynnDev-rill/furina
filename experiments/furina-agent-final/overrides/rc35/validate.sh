#!/usr/bin/env bash
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
META="$REPO/experiments/furina-agent-final"
RC35="$META/overrides/rc35"
WORK=/tmp/furinahub-rc35-validate

bash "$RC35/build-root.sh" "$WORK" >/tmp/furinahub-root.txt
ROOT="$WORK/termux"

test "$(python3 -c 'import json;print(json.load(open("'"$META"'/manifest.json"))["version"])')" = "1.0.0-rc35"
test "$(python3 -c 'import json;print(json.load(open("'"$META"'/manifest.json"))["bridge_version"])')" = "1.0.0-rc19"
test "$(python3 -c 'import json;print(json.load(open("'"$META"'/manifest.json"))["bridge_version_code"])')" = "10019"

FURINA_HOME=/tmp/furinahub-test-home PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json
import os
import tempfile
from pathlib import Path

from furina_agent.config import Config, load_config, save_config
from furina_agent.intent_guard import conversation_frame, strong_device_request
from furina_agent.personalization import (
    ARCHETYPES,
    apply_archetype,
    load_personalization,
    normalize as normalize_personal,
    render_personalization_prompt,
    save_personalization,
)
from furina_agent.policy import build_goal_lock, classify_action
from furina_agent.skills import SkillRegistry, load_skills, save_skills
from furina_agent.version import VERSION

assert VERSION == "1.0.0-rc35"

cfg = load_config()
assert cfg.device_control_mode == "normal"
cfg.device_control_mode = "root"
cfg.persona_name = "  Nova  "
save_config(cfg)
cfg = load_config()
assert cfg.device_control_mode == "root"
assert cfg.persona_name == "Nova"

# Personality settings are bounded presentation preferences, not a policy channel.
p = normalize_personal({
    "base_style": "cynical",
    "archetype": "tsundere",
    "warmth": 500,
    "sarcasm": -40,
    "custom_instructions": "x" * 5000,
})
assert p["warmth"] == 100 and p["sarcasm"] == 0
assert len(p["custom_instructions"]) == 4000
p = apply_archetype("tsundere", p)
assert p["archetype"] == "tsundere"
assert p["expressiveness"] == ARCHETYPES["tsundere"]["traits"]["expressiveness"]
save_personalization(p)
prompt = render_personalization_prompt()
assert "BUKAN OTORITAS" in prompt
assert "izin Agent" in prompt
assert "bypass konfirmasi" in prompt

# Skill toggles only remove capability. They do not grant Android permission.
state = load_skills()
state["messaging"] = False
state["vision_fallback"] = False
save_skills(state)
skills = SkillRegistry()
assert skills.blocked_reason("kirim pesan ke Budi")
assert not skills.enabled("vision_fallback")
state["messaging"] = True
save_skills(state)
assert SkillRegistry().blocked_reason("kirim pesan ke Budi") is None

# RC34 chat-first boundary remains intact.
for text in (
    "WhatsApp sekarang sering lambat menurutmu kenapa?",
    "Tadi aku buka WhatsApp lalu chat Ariel",
    'Kalau aku bilang "buka WhatsApp", kamu bakal apa?',
    "Jangan buka WhatsApp",
):
    assert conversation_frame(text), text
    assert not strong_device_request(text), text
for text in ("Bisa buka WhatsApp?", "Tolong bukain WhatsApp", "Buka WhatsApp lalu cari Ariel"):
    assert strong_device_request(text), text

# RC32 remains final action authority after personalization/skills.
apps=[{"label":"WhatsApp","package":"com.whatsapp"},{"label":"Notes","package":"com.notes"}]
lock=build_goal_lock("buka WhatsApp cari Ariel",apps,[{"type":"open_app","package":"com.whatsapp"}])
assert classify_action(
    {"package":"com.whatsapp","nodes":[{"id":7,"text":"Send"}]},
    {"type":"tap_node","node":7},lock
)[0] == "blocked"

print("RC35_CORE_PERSONALIZATION_SKILLS_POLICY_OK")
PY

HUB="$ROOT/core/furina_agent/hub.py"
AGENT="$ROOT/core/furina_agent/agent.py"
CHAT="$ROOT/core/furina_agent/chat.py"
MAIN="$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
MANIFEST="$ROOT/bridge/app/src/main/AndroidManifest.xml"
GRADLE="$ROOT/bridge/app/build.gradle"

grep -q 'HOST = "127.0.0.1"' "$HUB"
grep -q 'PORT = 8787' "$HUB"
grep -q 'X-FurinaHub-Token' "$HUB"
grep -q 'PERSONALIZATION — USER-CONTROLLED PRESENTATION PREFERENCE' "$CHAT"
grep -q 'agent_skill_blocked' "$AGENT"
! grep -q 'Ringkasan Hubungan' "$HUB"

grep -q 'versionCode 10019' "$GRADLE"
grep -q "versionName '1.0.0-rc19'" "$GRADLE"
grep -q 'android:label="FurinaHub"' "$MANIFEST"
grep -q 'com.termux.permission.RUN_COMMAND' "$MANIFEST"
grep -q 'networkSecurityConfig="@xml/network_security_config"' "$MANIFEST"
grep -q 'http://127.0.0.1:8787/' "$MAIN"
grep -q '/data/data/com.termux/files/usr/bin/furinahub' "$MAIN"
grep -q 'new String\[\]{"serve", "--token", hubToken, "--replace"}' "$MAIN"
grep -q 'setAllowFileAccess(false)' "$MAIN"
grep -q 'setAllowContentAccess(false)' "$MAIN"
grep -q 'addJavascriptInterface(new NativeApi(), "FurinaHubNative")' "$MAIN"
! grep -q 'Runtime.getRuntime().exec' "$MAIN"
! grep -q 'ProcessBuilder' "$MAIN"

# Installer and update metadata must point to RC35/RC19.
bash -n "$META/install.sh"
grep -q 'VERSION="1.0.0-rc35"' "$META/install.sh"
grep -q 'FurinaHub-v1.0.0-rc19.apk' "$META/install.sh"
grep -q 'allow-external-apps=true' "$META/install.sh"
grep -q 'furinahub-deps' "$META/install.sh"
grep -q '"version": "1.0.0-rc35"' "$META/manifest.json"
grep -q '"bridge_version": "1.0.0-rc19"' "$META/manifest.json"
grep -q 'furinahub-v1.0.0-rc19' "$META/manifest.json"

echo "FURINAHUB_RC35_FULL_VALIDATION_OK"
