#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.8/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.18"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_118_IDENTITY_KERNEL' "$ROOT/core/furina_agent/persona.py"
grep -Fq 'FURINA_TERMUX_118_RESPONSE_RHYTHM' "$ROOT/core/furina_agent/response.py"
grep -Fq 'FURINA_TERMUX_118_TRAIT_STATE_CONTROLLER' "$ROOT/core/furina_agent/personality.py"
grep -Fq 'FURINA_TERMUX_118_EVIDENCE_LINKED_MEMORY' "$ROOT/core/furina_agent/memory.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.hub_settings import defaults
from furina_agent.memory import MemoryStore
from furina_agent.personality import TRAIT_IDS, contextual_traits
from furina_agent.response import choose_profile, register_previous_outcome

store=MemoryStore()
tables={r[0] for r in store._conn().execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert {'memory_candidates','memory_candidate_evidence','belief_candidates','belief_candidate_evidence','memory_evidence','memory_links'} <= tables
columns={r[1] for r in store._conn().execute('PRAGMA table_info(memories)')}
assert 'source_message_id' in columns
assert defaults()['personality_traits']==[], defaults()['personality_traits']

# The screenshot regression: a short casual opinion must never become DEEP,
# a numbered two-sided essay, or receive a large continuation budget.
question='apa pendapatmu tentang orang yang mudah jatuh cinta dengan cewek yang baik sedikit ke dia?'
profile=choose_profile(question,store)
assert profile.name=='CASUAL' and profile.max_tokens<=180,profile
assert 'Target 2 beats' in profile.instruction and 'daftar bernomor' in profile.instruction
emotion=choose_profile('aku capek karena bug ini gagal terus',store)
assert emotion.name=='CLOSE',emotion
deep=choose_profile('lakukan analisis menyeluruh dan bandingkan semua strategi ini',store)
assert deep.name=='DEEP' and deep.max_tokens>=900,deep

# Generic words about a project are not feedback on the previous answer.
store.record_route('CASUAL','feedback:test')
register_previous_outcome(store,'model ini bagus tetapi build-nya gagal')
outcome=store._conn().execute("SELECT outcome FROM response_routes WHERE context_key='feedback:test'").fetchone()[0]
assert outcome=='neutral',outcome

# Trait selection remains stable in the same conversational mode and all 20
# choices remain available without being dumped into one response.
first=contextual_traits(TRAIT_IDS,'obrolan santai',context={'profile':'CASUAL','relationship':{}})
second=contextual_traits(TRAIT_IDS,'lanjut',context={'profile':'CASUAL','previous_profile':'CASUAL','previous_traits':first,'relationship':{}})
assert 1 <= len(first) <= 4 and set(first)&set(second),(first,second)

# Explicit facts are admitted immediately with their source message. A weak AI
# inference stays a candidate until a different user message supports it.
msg=store.add_message('user','Mulai sekarang jawab ringkas dan langsung ke inti.')
memory_id=store.add_memory('Mulai sekarang jawab ringkas dan langsung ke inti','preference',.92,confidence=.95,source='explicit',source_message_id=msg,source_evidence='Mulai sekarang jawab ringkas dan langsung ke inti.')
row=store._conn().execute('SELECT source_message_id FROM memories WHERE id=?',(memory_id,)).fetchone()
assert int(row[0])==msg
weak1=store.add_message('user','Aku membahas cuaca hari ini.')
assert store.add_memory('Pengguna menyukai astronomi','fact',.7,confidence=.7,source='user_evidence',source_message_id=weak1,source_evidence='cuaca hari ini') is None
assert not store._conn().execute("SELECT 1 FROM memories WHERE text='Pengguna menyukai astronomi'").fetchone()
weak2=store.add_message('user','Aku kembali membahas cuaca besok.')
accepted=store.add_memory('Pengguna menyukai astronomi','fact',.7,confidence=.7,source='user_evidence',source_message_id=weak2,source_evidence='cuaca besok')
assert accepted and store._conn().execute('SELECT count(*) FROM memory_candidate_evidence').fetchone()[0]==2
assert store.upsert_belief('preference','Pengguna lebih suka malam',.70,source='user_evidence',source_message_id=weak1,source_evidence='cuaca hari ini') is None
belief_id=store.upsert_belief('preference','Pengguna lebih suka malam',.70,source='user_evidence',source_message_id=weak2,source_evidence='cuaca besok')
assert belief_id and store._conn().execute('SELECT count(*) FROM belief_candidate_evidence').fetchone()[0]==2

# Preference correction keeps provenance and creates a lightweight relation.
old_msg=store.add_message('user','Aku lebih suka jawaban yang panjang dan rinci.')
old_id=store.add_memory('Aku lebih suka jawaban yang panjang dan rinci','preference',.85,confidence=.92,source='explicit',source_message_id=old_msg,source_evidence='Aku lebih suka jawaban yang panjang dan rinci.')
new_msg=store.add_message('user','Sekarang aku lebih suka jawaban yang ringkas dan rinci.')
new_id=store.add_memory('Sekarang aku lebih suka jawaban yang ringkas dan rinci','preference',.92,confidence=.94,source='explicit',source_message_id=new_msg,source_evidence='Sekarang aku lebih suka jawaban yang ringkas dan rinci.')
assert store._conn().execute("SELECT 1 FROM memory_links WHERE from_id=? AND to_id=? AND relation='replaces'",(new_id,old_id)).fetchone()

cfg=load_config(); cfg.routing_mode='local'
chat=FurinaChat(cfg,store,object())
messages=chat._messages(question,choose_profile(question,store))
system=messages[0]['content']
assert 'IDENTITY KERNEL' in system and 'RESPONSE RHYTHM — CASUAL' in system
assert 'Pertanyaan opini kasual bukan permintaan esai' in system

class FakeLLM:
    def __init__(self): self.calls=[]
    def prewarm_local(self): pass
    def chat(self,messages,**kwargs):
        self.calls.append(kwargs)
        return 'Menurutku itu lebih menunjukkan dia cepat memberi makna pada perhatian kecil. Manis, tapi dia tetap perlu membedakan ketulusan dari keramahan biasa.'

runtime_store=MemoryStore(); runtime_store.create_session_conversation('ritme')
fake=FakeLLM(); runtime=FurinaChat(cfg,runtime_store,fake)
runtime.respond(question)
assert fake.calls and fake.calls[0]['max_tokens']<=180,fake.calls
print('FURINA_TERMUX_118_NATURAL_MEMORY_REGRESSION_OK')
PY

echo FURINA_TERMUX_118_VALIDATION_OK
