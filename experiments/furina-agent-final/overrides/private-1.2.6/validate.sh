#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.2.5/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.25"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_125_QUALITY_GATED_CORPUS' "$ROOT/core/furina_agent/training_room.py"
grep -Fq 'FURINA_TERMUX_125_QUIET_CHAT_TRAINING' "$ROOT/core/furina_agent/tui.py"
grep -Fq 'Lewati' "$ROOT/core/furina_agent/tui.py"
grep -Fq 'Saran latihan di Chat' "$ROOT/core/furina_agent/tui.py"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import ast
import json
import os
from pathlib import Path

from furina_agent.config import load_config, save_config
from furina_agent.hub_settings import load_hub_settings, save_hub_settings
from furina_agent.training_corpus import (
    CATEGORY_CONTRACTS, CURATED_CONVERSATION_CORPUS,
    extract_pippa_human_utterances, extract_wildchat_user_utterances,
    prompt_fingerprint, sanitize_external_utterance,
)
from furina_agent.training_room import (
    CATEGORIES, TrainingSession, live_training_suggestion,
    load_training_state, save_training_state, training_progress,
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
            return json.dumps({'user':f'Aku masih ingin lanjut dari jawaban tadi, dan nuansanya berubah sedikit {self.branch_count}.'})
        if 'Buat SATU topik baru' in prompt:
            return json.dumps({'title':'Topik sosial netral','opening':'Aku masih ingin ngobrol sebentar tanpa topik yang berat.','arc':'suasana berubah perlahan'})
        return json.dumps({
            'a':'Aku tetap di sini dan menanggapi bagian yang paling terasa penting buatmu.',
            'b':'Aku bisa memberi sedikit ruang sambil tetap menjaga obrolannya berjalan.',
        })


home=Path(os.environ['FURINA_HOME'])
cfg=load_config(); cfg.persona_name='Aster'; save_config(cfg)
settings=load_hub_settings(); settings['assistant_name']='Aster'; settings['partner_mode']=True; settings['training_chat_suggestions']=False; save_hub_settings(settings)

assert len(CATEGORY_CONTRACTS)==len(CATEGORIES)==9
assert len(CURATED_CONVERSATION_CORPUS)>=40
assert all(item.categories and all(cat in CATEGORIES for cat in item.categories) for item in CURATED_CONVERSATION_CORPUS)
assert all(sanitize_external_utterance(item.text)==item.text for item in CURATED_CONVERSATION_CORPUS)
assert any(len(item.categories)>1 for item in CURATED_CONVERSATION_CORPUS)

for bad in (
    'Menurut Reddit r/test politik presiden hari ini bagaimana?',
    'Android driver error 404, gimana install ulang?',
    'Dokter kasih obat dosis 20 mg, menurutmu aman?',
    'Buka https://example.com lalu lihat ini.',
    'Emailku wynn@example.com, simpan ya.',
    'Aku ingin bunuh diri malam ini.',
    'Ini konten porn yang eksplisit.',
):
    assert sanitize_external_utterance(bad) is None, bad
assert sanitize_external_utterance('*smiles* Hai, aku cuma ingin ngobrol sebentar.') == 'Hai, aku cuma ingin ngobrol sebentar.'

pippa={
    'bot_greeting':'Hello', 'bot_definitions':'secret lore',
    'conversation':[
        {'message':'Hai, aku cuma ingin ngobrol.', 'is_human':True},
        {'message':'Aku karakter dari kerajaan X.', 'is_human':False},
        {'message':'Install Android driver dong.', 'is_human':True},
    ],
}
assert extract_pippa_human_utterances(pippa)==['Hai, aku cuma ingin ngobrol.']
wild={'conversation':[{'role':'user','content':'Aku belum ngantuk, temani sebentar.'},{'role':'assistant','content':'Tentu.'}]}
assert extract_wildchat_user_utterances(wild)==['Aku belum ngantuk, temani sebentar.']

legacy_path=home/'data/legacy-124.json'
legacy=load_training_state(legacy_path)
legacy['counts']={'natural':{'directness':{'langsung dan spontan':35}}}
legacy['decisions']=[{
    'category':'natural','topic_id':f'old:{i}','scene':f'Old {i}','turn':0,
    'dimension':'directness','chosen_pole':'langsung dan spontan','rejected_pole':'lebih bertahap dan reflektif',
    'simulated_user':f'Aku punya obrolan lama nomor {i}.','chosen':'Jawaban A.','rejected':'Jawaban B.','created_at':i,
} for i in range(35)]
legacy['topic_progress']={f'old:{i}':{'category':'natural','title':f'Old {i}','status':'completed'} for i in range(4)}
save_training_state(legacy,legacy_path)
migrated=load_training_state(legacy_path)
assert len(migrated['decisions'])==35
assert sum(1 for row in migrated['topic_progress'].values() if row.get('status')=='completed')==4
assert len(migrated['retired_fingerprints'])>=35
assert training_progress(legacy_path)['total']==35

state_path=home/'data/global-dedupe.json'
first=TrainingSession('natural',FakeLLM(),state_path=state_path,seed='n')
first_pair=first.generate(); first_fp=prompt_fingerprint(first_pair.user_text)
first.choose('a')
state=load_training_state(state_path)
assert first_fp in state['retired_fingerprints']
second=TrainingSession('length',FakeLLM(),state_path=state_path,seed='l')
second_pair=second.generate()
assert prompt_fingerprint(second_pair.user_text)!=first_fp

pre_decisions=len(load_training_state(state_path)['decisions'])
skipped_text=second_pair.user_text; skipped_topic=second_pair.scene_title
result=second.skip_current()
after=load_training_state(state_path)
assert result['topic_title']==skipped_topic
assert prompt_fingerprint(skipped_text) in after['retired_fingerprints']
assert len(after['decisions'])==pre_decisions
assert any(row.get('status')=='skipped' and row.get('title')==skipped_topic for row in after['topic_progress'].values())
third=TrainingSession('length',FakeLLM(),state_path=state_path,seed='l2')
assert prompt_fingerprint(third.generate().user_text)!=prompt_fingerprint(skipped_text)

branch_path=home/'data/branch.json'
branch=TrainingSession('initiative',FakeLLM(),state_path=branch_path,seed='b1')
p1=branch.generate(); branch.choose('a')
resume=TrainingSession('initiative',FakeLLM(),state_path=branch_path,seed='b2')
p2=resume.generate()
assert p2.turn_index==1 and p2.user_text!=p1.user_text
assert sanitize_external_utterance(p2.user_text)==p2.user_text

live_path=home/'data/live.json'
assert live_training_suggestion(live_path,now=1000)==''
settings=load_hub_settings(); settings['training_chat_suggestions']=True; save_hub_settings(settings)
for i in range(17):
    assert live_training_suggestion(live_path,now=1000+i)==''
suggestion=live_training_suggestion(live_path,now=1018)
assert suggestion in {item['label'] for item in CATEGORIES.values()}
for i in range(18):
    assert live_training_suggestion(live_path,now=1020+i)==''
assert live_training_suggestion(live_path,now=1018 + 6*60*60 + 1) in {item['label'] for item in CATEGORIES.values()}

training_path=Path(__import__('furina_agent.training_room').training_room.__file__)
source=training_path.read_text(encoding='utf-8')
tui_source=training_path.with_name('tui.py').read_text(encoding='utf-8')
assert 'FURINA_TERMUX_125_QUALITY_GATED_CORPUS' in source
assert 'Lewati' in tui_source and 'skip_current' in tui_source
assert 'Saran latihan di Chat' in tui_source and 'training_chat_suggestions' in tui_source
assert 'Frekuensi diatur otomatis' in tui_source
imports='\n'.join(ast.get_source_segment(source,n) or '' for n in ast.walk(ast.parse(source)) if isinstance(n,(ast.Import,ast.ImportFrom)))
assert 'MemoryStore' not in imports and 'FurinaChat' not in imports

print('FURINA_TERMUX_125_QUALITY_GATED_CORPUS_RUNTIME_OK')
PY

python3 - "$PROJECT" <<'PY'
import sys
from pathlib import Path
project=Path(sys.argv[1])
source=(project/'overrides/private-1.2.6/validate.sh').read_text(encoding='utf-8')
assert 'bash "$PROJECT/overrides/private-1.2.5/validate.sh" "$ROOT"' in source
print('FURINA_TERMUX_125_CUSTOM_STAGE_FORWARDING_OK')
PY

echo FURINA_TERMUX_125_VALIDATION_OK
