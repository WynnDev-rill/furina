#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.2.0/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.20"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_120_SYNTHESIZED_PERSONALITY' "$ROOT/core/furina_agent/personality.py"
grep -Fq 'FURINA_TERMUX_120_EVIDENCE_MEMORY' "$ROOT/core/furina_agent/memory.py"
grep -Fq 'FURINA_TERMUX_120_DIALOGUE_DECISION_ENGINE' "$ROOT/core/furina_agent/chat.py"
grep -Fq 'FURINA_TERMUX_120_TEMPO_BOUNDARY' "$ROOT/core/furina_agent/response.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.hub_settings import load_hub_settings, save_hub_settings
from furina_agent.memory import MemoryStore
from furina_agent.personality import (
    TRAIT_ACTION_CARDS_V2_120, TRAIT_IDS, _initiative_contract_120,
    _language_contract_120, compile_contextual_personality, contextual_traits,
    detect_tempo_120, emotional_state_v2_120, synthesize_trait_profile_120,
)
from furina_agent.response import choose_profile

# Trait Action Cards v2 cover all contexts, including romance, while the
# synthesis is order-independent and never rotates among selected traits.
assert len(TRAIT_ACTION_CARDS_V2_120)==20 and set(TRAIT_ACTION_CARDS_V2_120)==set(TRAIT_IDS)
assert all({'core','close','play','conflict','romance','avoid'} <= set(card) for card in TRAIT_ACTION_CARDS_V2_120.values())
pair_a=synthesize_trait_profile_120(['tsundere','oneesan'])
pair_b=synthesize_trait_profile_120(['oneesan','tsundere'])
assert pair_a['signature']==pair_b['signature'] and pair_a['traits']==pair_b['traits']==['tsundere','oneesan']
assert pair_a['interactions'] and 'Perhatian dewasa' in pair_a['interactions'][0]

store=MemoryStore(); store.create_session_conversation('synthesis')
ctx={'store':store,'profile':'CLOSE','relationship':{},'partner_mode':False}
pair=compile_contextual_personality(['tsundere','oneesan'],'aku capek',ctx)
assert 'PROFIL GABUNGAN STABIL' in pair and 'TINDAKAN GABUNGAN:' in pair
assert 'Semua facet membentuk SATU watak' in pair and '- Tsundere:' not in pair and '- Onee-san' not in pair
ten=list(TRAIT_IDS[:10])
assert contextual_traits(ten,'santai',context=ctx)==ten
first=compile_contextual_personality(ten,'obrolan biasa',ctx)
second=compile_contextual_personality(ten,'wkwk bercanda',ctx)
assert synthesize_trait_profile_120(ten)['signature'] in first and synthesize_trait_profile_120(ten)['signature'] in second
assert all(label in first for label in synthesize_trait_profile_120(ten)['labels'])

# Conflict outranks CLOSE, emotions transition with state, and the tempo,
# silence-aware follow-up, language, and boundary policies are concrete.
conflict=compile_contextual_personality(['hiyakasudere','deredere'],'aku sedih, tapi jangan begitu',ctx)
assert 'situation=conflict' in conflict and 'Hentikan godaan' in conflict
emotion=emotional_state_v2_120('aku capek dan sedih',ctx)
assert emotion['state']=='protective'
assert detect_tempo_120('jawab ringkas saja')['beats']<=2
boundary=detect_tempo_120('jangan bercanda, jawab langsung saja')
assert boundary['boundary'] and boundary['followup']=='avoid'
assert 'jangan code-switch' in _language_contract_120('menurutmu bagaimana?')
assert 'bahasa Inggris' in _language_contract_120('Please analyze this architecture thoroughly and give me the tradeoffs.')
assert 'bahasa Jepang' in _language_contract_120('この設計を詳しく分析してください。')
initiative=_initiative_contract_120('jangan goda, jawab saja',ctx,boundary,pair_a)
assert 'jangan membuka' in initiative

# Full-memory derivatives are opt-in. Citations preserve exact message IDs,
# current claims supersede old ones, episodes group evidence, graph edges are
# conservative, and weak recall abstains.
settings=load_hub_settings(); settings['full_local_memory']=False; save_hub_settings(settings)
off=MemoryStore(); off.create_session_conversation('off')
off_id=off.add_message('user','Aku tinggal di Babat.')
assert off.record_claims('Aku tinggal di Babat.',off_id)==[]

settings=load_hub_settings(); settings['full_local_memory']=True; settings['personality_traits']=['tsundere','oneesan']; save_hub_settings(settings)
memory=MemoryStore(); memory.create_session_conversation('arsip lama')
old_id=memory.add_message('user','Aku tinggal di Babat dan proyek Furina sedang error.')
memory.record_claims('Aku tinggal di Babat dan proyek Furina sedang error.',old_id)
episode_id=memory.record_evidence_episode('Aku tinggal di Babat dan proyek Furina sedang error.','Kita periksa.',old_id)
entities=memory.record_memory_graph('Aku tinggal di Babat dan proyek Furina sedang error.',old_id)
memory.add_message('assistant','Kita periksa Furina secara langsung.')
assert episode_id and entities
assert memory.active_claims('aku tinggal di mana')[0]['value']=='Babat'
assert memory.search_evidence_episodes('error proyek Furina')[0]['citation']==f'msgs#{old_id}'
graph=memory.search_memory_graph('proyek Furina')
assert graph and graph[0]['to_label']=='Furina' and graph[0]['citation']==f'msg#{old_id}'

memory.create_session_conversation('sekarang')
archive=memory.search_full_archive('tinggal Babat',4,roles=('user',))
assert archive and archive[0]['message_id']==old_id and f'msg#{old_id}' in archive[0]['content']
new_id=memory.add_message('user','Sekarang aku tinggal di Surabaya.')
memory.record_claims('Sekarang aku tinggal di Surabaya.',new_id)
claims=memory.active_claims('aku tinggal di mana')
assert len(claims)==1 and claims[0]['value']=='Surabaya' and claims[0]['replaces_id']
assert memory.search_full_archive('tinggal Babat',4,roles=('user',))==[]
packet=memory.memory_packet('kamu ingat aku tinggal di mana?')
assert packet['decision']=='grounded' and packet['claims'][0]['value']=='Surabaya' and packet['episodes']==[]
assert memory.memory_packet('kamu ingat kode roketku?')['decision']=='abstain'

# Opinion continuity is Furina's own prior position, never evidence about user.
question='menurutmu desain sederhana atau penuh fitur?'
opinion=memory.opinion_context(question)
assert opinion and not opinion['existing']
memory.record_opinion(question,'Aku memilih desain sederhana karena fitur yang tidak terpakai hanya menambah beban.',new_id)
old_opinion=memory.opinion_context(question)
assert old_opinion['existing'] and 'memilih desain sederhana' in old_opinion['position']

# The selected behavior systems reach the real prompt and real token budget.
cfg=load_config(); cfg.routing_mode='local'; cfg.persona_name='Furina'; cfg.user_nickname='Wynn'
chat=FurinaChat(cfg,memory,object())
profile=choose_profile('kamu ingat kode roketku?',memory)
messages=chat._messages('kamu ingat kode roketku?',profile)
system=messages[0]['content']
for token in ('BEHAVIOR CONTRACT V2','DIALOGUE DECISION','ANTI-KLISE','MEMORY DECISION: abstain','PROFIL GABUNGAN STABIL'):
    assert token in system,token
assert [x['role'] for x in messages].count('user')==1
assert choose_profile('hai',memory).max_tokens<=90

# The maximum selection remains a single bounded synthesis in the actual
# generation prompt, and deep Indonesian phrasing reaches the deep budget.
settings=load_hub_settings(); settings['personality_traits']=list(TRAIT_IDS); save_hub_settings(settings)
deep_text='Tolong dianalisis menyeluruh mengapa arsitektur memori proyek ini gagal dan berikan keputusan.'
deep_profile=choose_profile(deep_text,memory)
deep_system=chat._messages(deep_text,deep_profile)[0]['content']
assert deep_profile.name=='DEEP' and deep_profile.max_tokens>500
assert len(deep_system)<16000
assert all(label in deep_system for label in synthesize_trait_profile_120(TRAIT_IDS)['labels'])
assert 'jangan memilih, merotasi, atau menirukan satu sifat secara terpisah' in deep_system

print('FURINA_TERMUX_120_SYNTHESIS_DIALOGUE_MEMORY_REGRESSION_OK')
PY

echo FURINA_TERMUX_120_VALIDATION_OK
