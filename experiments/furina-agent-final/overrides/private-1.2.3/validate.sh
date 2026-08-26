#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.2.2/validate.sh"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.22"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_122_ARROW_TRAINING' "$ROOT/core/furina_agent/tui.py"
grep -Fq 'FURINA_TERMUX_122_ADAPTIVE_TRAINING' "$ROOT/core/furina_agent/training_room.py"
grep -Fq 'FURINA_TERMUX_122_IDENTITY_NEUTRAL' "$ROOT/core/furina_agent/persona.py"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import ast
import json
import os
from pathlib import Path

from furina_agent.config import load_config, save_config
from furina_agent.hub_settings import load_hub_settings, save_hub_settings
from furina_agent.persona import build_local_system_prompt, build_system_prompt
from furina_agent.training_room import (
    MAX_DECISIONS, TrainingSession, load_training_state,
    runtime_preference_contract, save_training_state, training_progress,
)


class FakeLLM:
    def __init__(self): self.calls=[]
    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return json.dumps({"a":"Aku di sini. Kita pelankan dulu.","b":"Hm, sini. Ceritakan bagian yang paling berat."})


home=Path(os.environ['FURINA_HOME'])
state_path=home/'data/training-122.json'
cfg=load_config(); cfg.persona_name='Aster'; save_config(cfg)
settings=load_hub_settings(); settings['assistant_name']='Aster'; settings['partner_mode']=False; settings['personality_traits']=['hangat']; save_hub_settings(settings)

# Names are labels, never a source of fictional biography. Both local and
# online prompt builders use the same identity-neutral final kernel.
blocked=('genshin','fontaine','hydro archon','focalors','oratrice','teyvat','paimon','traveler')
for prompt in (build_system_prompt('Aster','Wynn'),build_local_system_prompt('Aster','Wynn')):
    low=prompt.lower()
    assert 'namamu adalah aster' in low
    assert 'tidak memiliki latar bawaan' in low
    assert not any(token in low for token in blocked)

# Partner mode OFF is strict even when the selected curriculum category is
# named Mode pasangan. The active name is used without any fixed character.
fake=FakeLLM(); session=TrainingSession('partner',fake,state_path=state_path,seed='off')
pair=session.generate(); system=fake.calls[-1][0][0]['content']; prompt=fake.calls[-1][0][1]['content']
assert 'MODE PASANGAN NONAKTIF' in prompt and 'companion non-romantis' in prompt
assert 'Nama aktif: Aster' in prompt and 'jawaban Aster' in system
assert 'Furina terpilih' not in prompt and 'Wynn' not in prompt
assert not any(token in (system+'\n'+prompt).lower() for token in blocked)

# A learned choice is abstracted, then injected into the very next Training
# Room generation. Only the chosen response stays briefly in this simulated
# story for continuity; the rejected response never becomes context or memory.
session.choose('a'); learned_pair=pair
contract=runtime_preference_contract(state_path)
assert learned_pair.user_text not in contract
assert learned_pair.response_a not in contract and learned_pair.response_b not in contract
session.generate(); next_prompt=fake.calls[-1][0][1]['content']
assert 'PREFERENSI TRAINING ROOM' in next_prompt
assert learned_pair.user_text in next_prompt and learned_pair.response_a in next_prompt
assert learned_pair.response_b not in next_prompt
assert 'Terapkan preferensi lama yang relevan pada KEDUA kandidat' in next_prompt

# Toggling relationship mode affects the next generated candidates without
# recreating the TrainingSession.
settings=load_hub_settings(); settings['partner_mode']=True; save_hub_settings(settings)
session.reroll(); session.generate(); partner_prompt=fake.calls[-1][0][1]['content']
assert 'MODE PASANGAN AKTIF' in partner_prompt
assert 'pasangan romantis user yang sudah terjalin' in partner_prompt
assert 'termasuk pada kategori selain Mode pasangan' in partner_prompt

# Detailed examples stay bounded, while aggregate progress remains accurate
# after more than 300 choices.
state=load_training_state(state_path)
state['counts']={'natural':{'directness':{'langsung dan spontan':350}}}
state['decisions']=[{'n':i} for i in range(MAX_DECISIONS+25)]
save_training_state(state,state_path)
assert len(load_training_state(state_path)['decisions'])==MAX_DECISIONS
assert training_progress(state_path)['total']==350

# The response decision UI uses the same arrow/Enter chooser as other Termux
# menus. No raw A/B key reader remains in the active Training Room function.
tui_path=Path(__import__('furina_agent.training_room').training_room.__file__).with_name('tui.py')
tui_source=tui_path.read_text(encoding='utf-8'); tree=ast.parse(tui_source)
fn=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_training_room_122'][-1]
segment=ast.get_source_segment(tui_source,fn)
assert '_choose("Pilih respons", ["Respons A", "Respons B", "Buat ulang", "Selesai"]' in segment
assert 'read_training_key' not in segment
assert '_training_room_121 = _training_room_122' in tui_source

print('FURINA_TERMUX_122_ADAPTIVE_TRAINING_RUNTIME_OK')
PY

echo FURINA_TERMUX_122_VALIDATION_OK
