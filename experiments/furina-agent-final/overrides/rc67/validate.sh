#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
bash "$ROOT/overrides/android-rc54/validate.sh"
STAGE=/tmp/furina-agent-rc54-validate/termux
python3 "$HERE/apply.py" "$STAGE"
TEST_HOME="$(mktemp -d /tmp/furina-rc67-home.XXXXXX)"
trap 'rm -rf "$TEST_HOME"' EXIT
FURINA_HOME="$TEST_HOME" PYTHONPATH="$STAGE/core" python3 - <<'PY'
from furina_agent.config import load_config, save_config
from furina_agent.memory import MemoryStore
from furina_agent.relationship_v4 import RelationshipEngine

cfg=load_config(); cfg.persona_name="Furina"; cfg.user_nickname="Rill"; save_config(cfg)
store=MemoryStore(); engine=RelationshipEngine(store); snap=engine.snapshot()
assert snap["relationship"]["id"] == "partner"
assert snap["baseline"]["fresh"] is True
assert snap["baseline"]["facts"] == ["Namaku Furina.", "Nama pasanganku Rill.", "Aku sedang berbicara dengan pasanganku."]
conn=store._conn()
assert conn.execute("select count(*) from memories").fetchone()[0] == 0
assert conn.execute("select count(*) from messages").fetchone()[0] == 0
assert conn.execute("select count(*) from furina_shared_moments").fetchone()[0] == 0
assert "pasanganmu" in engine.context("hai").lower()
store.add_memory("Rill suka hujan", "preference")
assert engine.snapshot()["baseline"]["fresh"] is False
assert conn.execute("select count(*) from memories").fetchone()[0] == 1
engine.update_preferences({"pace":"slow", "affection_style":"gentle"})
assert engine.snapshot()["relationship"]["label"] == "Pasangan"
print("FURINA_RC67_FRESH_PARTNER_RUNTIME_OK")
PY
python3 - <<'PY'
from pathlib import Path
root=Path('/tmp/furina-agent-rc54-validate/termux/core/furina_agent')
text='\n'.join((root/x).read_text() for x in ('chat.py','hub.py','tui.py','persona.py','relationship_v4.py'))
assert 'relationship_v3' not in text
assert 'Mode hubungan' not in text
assert 'VERSION = "1.0.0-rc67"' in (root/'version.py').read_text()
print('FURINA_RC67_STATIC_OK')
PY
printf '%s\n' FURINA_RC67_VALIDATION_OK
