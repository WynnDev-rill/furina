#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
BASE=/tmp/furina-agent-rc53-validate/termux
STAGE=/tmp/furina-agent-rc66-validate/termux

HOME="${HOME:-/tmp/furina-validation-home}" FURINA_HOME="${FURINA_HOME:-$HOME}" bash "$ROOT/overrides/android-rc53/validate.sh"
rm -rf "$STAGE"
mkdir -p "$(dirname "$STAGE")"
cp -a "$BASE" "$STAGE"
python3 "$HERE/apply.py" "$STAGE"
python3 -m py_compile "$HERE/apply.py" "$HERE/relationship_v3.py"

RC66_TEST_HOME="$(mktemp -d /tmp/furina-rc66-home.XXXXXX)"
FURINA_HOME="$RC66_TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
import os
import time
from pathlib import Path

from furina_agent import cli
from furina_agent.lite_full import ProductWorkspace
from furina_agent.memory import MemoryStore
from furina_agent.naturalness import naturalize
from furina_agent.persona import build_system_prompt
from furina_agent.relationship_v3 import RelationshipEngine

store = MemoryStore()
workspace = ProductWorkspace(store)
workspace.change_focus({"action": "add", "text": "Data lama tetap ada", "when": ""})
engine = RelationshipEngine(store)

base = engine.snapshot()
assert base["mode"]["id"] == "close"
assert base["state"]["stage"] and base["state"]["tone"]
try:
    engine.update_preferences({"relationship_mode": "romantic"})
except ValueError:
    pass
else:
    raise AssertionError("romantic mode bypassed adult confirmation")

romantic = engine.update_preferences({
    "adult_confirmed": True,
    "relationship_mode": "romantic",
    "pace": "direct",
    "affection_style": "expressive",
    "initiative": "balanced",
    "ritual": "reconnect",
    "shared_note": "Kami menyukai percakapan yang jujur dan tidak dibuat-buat.",
})
assert romantic["mode"]["id"] == "romantic"
engine.change_moment({"action": "add", "note": "Kami tertawa saat Furina salah menyebut judul lagu.", "source_ref": "test:message:1"})
snapshot = engine.snapshot()
assert len(snapshot["moments"]) == 1
context = engine.context("Aku kangen kamu")
assert "Mode ROMANTIS aktif" in context
assert "RELATIONSHIP-FIRST CONTRACT" in context
assert "hanya Furina" in context
assert len(context) <= 4300
assert len(workspace.focus_list()) == 1, "legacy Focus data must survive the product reorientation"
assert "ARAH PRODUK RELATIONSHIP-FIRST" in build_system_prompt()
assert naturalize("Tolong jangan tinggalkan aku") == "aku tidak akan menahanmu"

started = time.perf_counter()
for _ in range(1000):
    assert engine.context("Aku kangen kamu")
assert time.perf_counter() - started < 2.0, "relationship prompt packet is unexpectedly slow"

mock_installer = Path(os.environ["FURINA_HOME"]) / "mock-installer.sh"
mock_installer.write_text(
    '#!/data/data/com.termux/files/usr/bin/bash\n'
    'FURINA_INSTALLER_ID="furinahub-core-bootstrap-v2"\n'
    'FURINA_RUNTIME_CONTRACT="furina-runtime/v2"\n',
    encoding="utf-8",
)
cli._RECOVERY_URLS = (mock_installer.as_uri(),)
recovery_target = cli._download_recovery_installer()
assert recovery_target == cli.RUN_DIR / "furina-recover.sh"
assert recovery_target.is_file() and recovery_target.parent != Path("/tmp")
print("FURINA_RC66_RELATIONSHIP_RUNTIME_OK")
PY

python3 - "$STAGE" <<'PY'
from pathlib import Path
import ast
import sys

core = Path(sys.argv[1]) / "core" / "furina_agent"
for name in ("chat.py", "hub.py", "tui.py", "cli.py", "persona.py", "naturalness.py", "relationship_v3.py"):
    ast.parse((core / name).read_text(encoding="utf-8"))
chat = (core / "chat.py").read_text(encoding="utf-8")
hub = (core / "hub.py").read_text(encoding="utf-8")
tui = (core / "tui.py").read_text(encoding="utf-8")
cli = (core / "cli.py").read_text(encoding="utf-8")
relationship = (core / "relationship_v3.py").read_text(encoding="utf-8")
assert "RELATIONSHIP CORE V3:" in chat and "self.relationship.context(user_text)" in chat
assert all(route in hub for route in ("/api/relationship", "/api/relationship/preferences", "/api/relationship/moments"))
final_tui = tui[tui.rfind("def _lite_relationship(console):"):]
assert "Furina Lite · Kita" in final_tui and "Fokus & Reminder" not in final_tui
assert "from .cli import cmd_recover, cmd_repair, cmd_update" in final_tui
assert "_lite_update_recovery(console)" in final_tui
assert "def cmd_recover" in cli and 'sub.add_parser("recover")' in cli
assert 'RUN_DIR / "furina-recover.sh"' in cli and 'Path("/tmp")' not in cli
assert ".llm" not in relationship and "streak" in relationship and "satu-satunya" in relationship
print("FURINA_RC66_STATIC_OK")
PY

printf '%s\n' FURINA_RC66_VALIDATION_OK
