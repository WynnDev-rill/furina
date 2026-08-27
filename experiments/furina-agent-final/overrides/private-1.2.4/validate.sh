#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.2.3/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.23"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_123_DIRECTED_STORY_CURRICULUM' "$ROOT/core/furina_agent/training_room.py"
grep -Fq 'FURINA_TERMUX_123_REASONED_REROLL_STORIES' "$ROOT/core/furina_agent/tui.py"

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
    CATEGORIES, REROLL_REASONS_123, TOPIC_TURNS_123, TrainingSession,
    _adaptive_dimension_123, _seed_id_123, load_training_state,
    runtime_preference_contract, save_training_state, training_progress,
)


class FakeLLM:
    def __init__(self):
        self.calls=[]
        self.blueprints=0
        self.branches=0

    def chat(self, messages, **kwargs):
        system=messages[0]['content']; prompt=messages[1]['content']
        self.calls.append((system,prompt,kwargs))
        if 'Buat SATU topik baru' in prompt:
            self.blueprints += 1
            return json.dumps({
                'title':f'Topik dinamis {self.blueprints}',
                'opening':f'Pembuka baru {self.blueprints}.',
                'arc':'keputusan kecil mengubah suasana',
            })
        if 'SATU ucapan user simulasi berikutnya' in prompt:
            self.branches += 1
            return json.dumps({'user':f'Cabang {self.branches}: aku menanggapi jawaban yang kupilih tadi.'})
        return json.dumps({'a':'Aku menangkap maksudmu. Kita lihat bagian ini dulu.','b':'Hm, sini. Ceritakan bagian yang paling terasa.'})


home=Path(os.environ['FURINA_HOME'])
cfg=load_config(); cfg.persona_name='Aster'; save_config(cfg)
settings=load_hub_settings(); settings['assistant_name']='Aster'; settings['partner_mode']=True; save_hub_settings(settings)

# Existing 1.1.22 decisions migrate into completed topic state. Returning to
# the category must not reopen a five-turn seed that was already answered.
migration_path=home/'data/migration.json'
first_title, first_turns=CATEGORIES['partner']['scenes'][0]
state=load_training_state(migration_path)
state['decisions']=[{
    'category':'partner','scene':first_title,'turn':turn,'dimension':'affection',
    'chosen_pole':'afeksi tersirat dan spesifik','rejected_pole':'afeksi terbuka dan langsung',
    'simulated_user':first_turns[turn],'chosen':'x','rejected':'y','created_at':1,
} for turn in range(TOPIC_TURNS_123)]
save_training_state(state,migration_path)
fake=FakeLLM(); migrated=TrainingSession('partner',fake,state_path=migration_path,seed='migration')
pair=migrated.generate()
assert pair.scene_title != first_title
migrated_state=load_training_state(migration_path)
assert migrated_state['topic_progress'][_seed_id_123('partner',first_title)]['status']=='completed'

# R asks for and persists an explicit reason. It teaches a negative constraint,
# but does not count as A/B, advance the story, or complete the topic.
state_path=home/'data/training-123.json'
fake=FakeLLM(); session=TrainingSession('natural',fake,state_path=state_path,seed='directed')
pair=session.generate(); original_title=pair.scene_title
before=training_progress(state_path)['total']
result=session.reject_pair('generic')
after=training_progress(state_path)['total']
state=load_training_state(state_path)
assert result['label']==REROLL_REASONS_123['generic']
assert before==after==0
assert state['negative_feedback']['natural'][pair.dimension]['generic']==1
assert state['active_topics']['natural']['next_turn']==0
rerolled=session.generate()
last_prompt=fake.calls[-1][1]
assert 'hindari terlalu generik (1x)' in last_prompt
assert rerolled.scene_title==original_title and rerolled.turn_index==0

# A chosen answer branches the following simulated user turn. The rejected
# answer is never injected into the branch context.
chosen=rerolled.response_a; rejected=rerolled.response_b
session.choose('a')
session.generate()
branch_calls=[prompt for system,prompt,kwargs in fake.calls if 'SATU ucapan user simulasi berikutnya' in prompt]
assert branch_calls and chosen in branch_calls[-1] and rejected not in branch_calls[-1]

# Finish the current topic. A fresh session resumes with a different topic;
# completed topics are persistent rather than cycling modulo three scenes.
for _ in range(TOPIC_TURNS_123-1):
    if session.current is None:
        session.generate()
    completion=session.choose('a')
assert completion['topic_completed'] is True
finished=load_training_state(state_path)
assert finished['topic_progress'][_seed_id_123('natural',original_title)]['status']=='completed'
assert 'natural' not in finished['active_topics']
fresh=TrainingSession('natural',FakeLLM(),state_path=state_path,seed='fresh')
fresh_pair=fresh.generate()
assert fresh_pair.scene_title != original_title

# Adaptive curriculum targets the least-observed dimension instead of rotating
# blindly. Counts remain aggregate and existing preference contracts survive.
adaptive=load_training_state(state_path)
adaptive['counts']['natural']={
    'directness':{'langsung dan spontan':9,'lebih bertahap dan reflektif':8},
    'texture':{'kasual dengan tekstur percakapan':7,'rapi dan tenang':7},
    'affection':{},
}
save_training_state(adaptive,state_path)
assert _adaptive_dimension_123('natural',load_training_state(state_path))=='affection'
assert runtime_preference_contract(state_path)

# When all 18 built-in seeds are complete, the engine creates a new blueprint
# on demand and includes recent titles in the anti-repetition instruction.
dynamic_path=home/'data/dynamic.json'
dynamic_state=load_training_state(dynamic_path)
for category_id, category in CATEGORIES.items():
    for title, turns in category['scenes']:
        dynamic_state['topic_progress'][_seed_id_123(category_id,title)]={
            'category':category_id,'title':title,'status':'completed','source':'seed'
        }
dynamic_state['recent_topics']=[{'category':'natural','title':'Hujan di halte','id':'old'}]
save_training_state(dynamic_state,dynamic_path)
dynamic_llm=FakeLLM(); dynamic=TrainingSession('natural',dynamic_llm,state_path=dynamic_path,seed='unbounded')
dynamic_pair=dynamic.generate()
assert dynamic_pair.scene_title.startswith('Topik dinamis')
blueprint_prompts=[prompt for system,prompt,kwargs in dynamic_llm.calls if 'Buat SATU topik baru' in prompt]
assert blueprint_prompts and 'Hujan di halte' in blueprint_prompts[-1]
assert 'DILARANG diulang' in blueprint_prompts[-1]

# Training remains structurally isolated: no MemoryStore/chat history import,
# and the active TUI exposes reasoned R plus arrow/Enter selection via _choose.
training_path=Path(__import__('furina_agent.training_room').training_room.__file__)
training_source=training_path.read_text(encoding='utf-8')
tree=ast.parse(training_source)
imports='\n'.join(ast.get_source_segment(training_source,n) or '' for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom)))
assert 'MemoryStore' not in imports and 'FurinaChat' not in imports
tui_source=training_path.with_name('tui.py').read_text(encoding='utf-8')
assert '["Respons A", "Respons B", "R · Buat ulang", "Selesai"]' in tui_source
assert '_choose("Kenapa keduanya tidak cocok?"' in tui_source
assert '_training_room_121 = _training_room_123' in tui_source

print('FURINA_TERMUX_123_DIRECTED_STORY_RUNTIME_OK')
PY

echo FURINA_TERMUX_123_VALIDATION_OK
