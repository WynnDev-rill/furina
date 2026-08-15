#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STAGE=/tmp/furina-agent-rc34-validate/termux

bash "$ROOT/overrides/rc46/validate.sh"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py"
PYTHONPATH="$STAGE/core" FURINA_HOME=/tmp/furinahub-rc47-test python3 - <<'PY'
from furina_agent.hub_settings import DEFAULT_SKILLS, SKILL_META
from furina_agent.direct_control import DirectDeviceControl, _SCREEN_READ, _APP_FIND, _FORM_FILL

new = {
    "app_launcher", "quick_navigation", "semantic_tap", "smart_scroll", "focused_typing",
    "local_reminders", "screen_reader", "app_finder", "form_fill", "workflow_macros",
}
assert new <= set(DEFAULT_SKILLS)
assert new <= set(SKILL_META)
assert all(DEFAULT_SKILLS[k] is True for k in new)
assert _SCREEN_READ.match("baca layar")
assert _APP_FIND.match("cari aplikasi WhatsApp")
assert _FORM_FILL.match("isi kolom Nama dengan Wynn")

obj = object.__new__(DirectDeviceControl)
obj._resolve_app = lambda name, exact=False: "com.example.app"
assert obj._macro_action("buka aplikasi Example") == ("control", {"type": "open_app", "package": "com.example.app"})
assert obj._macro_action("scroll bawah")[1]["type"] == "scroll_best"
assert obj._macro_action("tekan Lanjut")[1] == {"type": "tap_text", "target": "Lanjut"}
assert obj._macro_action("ketik halo")[1] == {"type": "set_text_best", "text": "halo"}
print("FURINAHUB_RC47_SKILLS_REGRESSION_OK")
PY

python3 - "$HERE/install-body.sh" <<'PY'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text(encoding='utf-8')
assert 'EXISTING_INSTALL=0' in text
assert 'FURINAHUB_CORE_ONLY="$EXISTING_INSTALL"' in text
assert 'if [[ "${FURINAHUB_CORE_ONLY:-0}" != "1" ]]; then ensure_rc29_apk_file; fi' in text
assert 'APK tidak diubah; update APK dilakukan dari menu Update FurinaHub.' in text
fast=text.index('if [[ "$CURRENT" == "$VERSION" && "$CURRENT_REVISION" == "$DEPENDENCY_REVISION" ]]')
legacy=text.index('fetch "$RC46_BODY_URL"')
assert fast < legacy
assert 'Core dan runtime sudah terbaru' in text
assert 'CURRENT="$(installed_version 2>/dev/null || true)"' in text
assert 'CURRENT_REVISION="$(cat "$ROOT/data/dependency_revision" 2>/dev/null || true)"' in text
print('FURINAHUB_RC47_UPDATE_OWNERSHIP_OK')
PY

grep -q 'VERSION = "1.0.0-rc47"' "$STAGE/core/furina_agent/version.py"
grep -q '"bridge_target": "1.0.0-rc30"' "$STAGE/core/furina_agent/hub.py"
echo FURINAHUB_CORE_RC47_VALIDATE_OK
