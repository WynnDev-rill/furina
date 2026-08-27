#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.2.4/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.24"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_124_THREE_SOCIAL_CURRICULA' "$ROOT/core/furina_agent/training_room.py"
grep -Fq 'markup=False' "$ROOT/core/furina_agent/tui.py"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import ast
import json
import os
from pathlib import Path

from furina_agent.config import load_config, save_config
from furina_agent.hub_settings import load_hub_settings, save_hub_settings
from furina_agent.training_room import (
    CATEGORIES, TrainingSession, load_training_state,
    runtime_preference_contract, save_training_state,
)


class FakeLLM:
    def __init__(self):
        self.calls=[]
        self.branch_count=0

    def chat(self, messages, **kwargs):
        system=messages[0]['content']; prompt=messages[1]['content']
        self.calls.append((system,prompt,kwargs))
        if 'SATU ucapan user simulasi berikutnya' in prompt:
            self.branch_count += 1
            return json.dumps({'user':f'Cabang sosial {self.branch_count} setelah jawaban terpilih.'})
        if 'Buat SATU topik baru' in prompt:
            return json.dumps({'title':'Topik sosial baru','opening':'Aku memberi sinyal yang belum jelas.','arc':'nada berubah mengikuti pilihan'})
        return json.dumps({
            'a':'[tenang] Aku menangkap dua kemungkinan; aku tidak akan buru-buru menyimpulkan.',
            'b':'Aku akan mengambil satu langkah kecil, lalu melihat reaksimu.',
        })


home=Path(os.environ['FURINA_HOME'])
cfg=load_config(); cfg.persona_name='Aster'; save_config(cfg)
settings=load_hub_settings(); settings['assistant_name']='Aster'; settings['partner_mode']=True; save_hub_settings(settings)

expected={
    'initiative':'Inisiatif yang tepat',
    'ambiguous_tone':'Nada ambigu & sarkasme',
    'mixed_emotion':'Emosi campuran',
}
assert len(CATEGORIES)==9
for category_id,label in expected.items():
    category=CATEGORIES[category_id]
    assert category['label']==label
    assert len(category['dimensions'])==3
    assert len(category['scenes'])==3
    assert all(len(turns)==5 for title,turns in category['scenes'])

# Each selected curriculum generates viable A/B choices through the same
# partner-aware adaptive Story Engine and persists abstract preferences.
for category_id in expected:
    path=home/f'data/{category_id}.json'
    llm=FakeLLM(); session=TrainingSession(category_id,llm,state_path=path,seed=category_id)
    pair=session.generate()
    assert pair.category_id==category_id and pair.response_a!=pair.response_b
    prompt=llm.calls[-1][1]
    assert 'MODE PASANGAN AKTIF' in prompt
    session.choose('a')
    contract=runtime_preference_contract(path)
    assert CATEGORIES[category_id]['label'] in contract
    assert pair.user_text not in contract and pair.response_a not in contract

# Branch transcript is persisted with an unfinished topic. Reopening the room
# reconstructs the chosen path and never crashes at transcript[-1].
resume_path=home/'data/resume.json'
first_llm=FakeLLM(); first=TrainingSession('initiative',first_llm,state_path=resume_path,seed='resume-a')
first_pair=first.generate(); first.choose('a')
saved=load_training_state(resume_path)
active=saved['active_topics']['initiative']
assert active['next_turn']==1
assert active['branch_transcript'][-1]==[first_pair.user_text,first_pair.response_a]
second_llm=FakeLLM(); resumed=TrainingSession('initiative',second_llm,state_path=resume_path,seed='resume-b')
second_pair=resumed.generate()
branch_prompts=[prompt for system,prompt,kwargs in second_llm.calls if 'SATU ucapan user simulasi berikutnya' in prompt]
assert second_pair.turn_index==1 and branch_prompts
assert first_pair.response_a in branch_prompts[-1]
assert first_pair.response_b not in branch_prompts[-1]

# Migration also reconstructs a 1.1.23 unfinished topic that predates the new
# branch_transcript field, using its sandbox decisions only.
legacy_path=home/'data/legacy-resume.json'
legacy=load_training_state(legacy_path)
topic={
    'id':'seed:initiative:malam-yang-terlalu-sunyi','category':'initiative',
    'title':'Malam yang terlalu sunyi','opening':'Aku tidak punya topik khusus malam ini.',
    'seed_turns':list(CATEGORIES['initiative']['scenes'][0][1]),'arc':'alur seed bercabang',
    'source':'seed','dimension':'timing','next_turn':1,'created_at':1,
}
legacy['active_topics']['initiative']=topic
legacy['decisions'].append({
    'category':'initiative','topic_id':topic['id'],'scene':topic['title'],'turn':0,
    'dimension':'timing','chosen_pole':'mengambil inisiatif sekarang',
    'rejected_pole':'menunggu sinyal user lebih jelas','simulated_user':topic['opening'],
    'chosen':'Aku tetap di sini dan membuka satu topik kecil.','rejected':'Aku akan menunggu.',
    'created_at':1,
})
save_training_state(legacy,legacy_path)
legacy_llm=FakeLLM(); legacy_session=TrainingSession('initiative',legacy_llm,state_path=legacy_path,seed='legacy')
legacy_pair=legacy_session.generate()
legacy_branches=[prompt for system,prompt,kwargs in legacy_llm.calls if 'SATU ucapan user simulasi berikutnya' in prompt]
assert legacy_pair.turn_index==1 and legacy_branches
assert 'Aku tetap di sini dan membuka satu topik kecil.' in legacy_branches[-1]

# Model text is rendered literally. Rich tags or malformed brackets generated
# by a model cannot alter or hide the Training Room terminal UI.
training_path=Path(__import__('furina_agent.training_room').training_room.__file__)
tui_source=training_path.with_name('tui.py').read_text(encoding='utf-8')
tree=ast.parse(tui_source)
fn=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_training_room_123'][-1]
segment=ast.get_source_segment(tui_source,fn)
assert segment.count('markup=False')>=3
assert 'height=12' in segment
assert '_choose("Pilih respons"' in segment and '_choose("Kenapa keduanya tidak cocok?"' in segment

# The sandbox boundary remains structural after adding three categories.
training_source=training_path.read_text(encoding='utf-8')
imports='\n'.join(ast.get_source_segment(training_source,n) or '' for n in ast.walk(ast.parse(training_source)) if isinstance(n,(ast.Import,ast.ImportFrom)))
assert 'MemoryStore' not in imports and 'FurinaChat' not in imports

print('FURINA_TERMUX_124_THREE_SOCIAL_CURRICULA_RUNTIME_OK')
PY

python3 - "$PROJECT" <<'PY'
import sys
from pathlib import Path
project=Path(sys.argv[1])
for current,previous in (('private-1.2.2','private-1.2.1'),('private-1.2.3','private-1.2.2'),('private-1.2.4','private-1.2.3'),('private-1.2.5','private-1.2.4')):
    source=(project/'overrides'/current/'validate.sh').read_text(encoding='utf-8')
    expected=f'bash "$PROJECT/overrides/{previous}/validate.sh" "$ROOT"'
    assert expected in source,(current,expected)
print('FURINA_TERMUX_124_CUSTOM_STAGE_FORWARDING_OK')
PY

echo FURINA_TERMUX_124_VALIDATION_OK
