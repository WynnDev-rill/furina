#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.9/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.19"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_119_OPT_IN_RELATIONSHIP' "$ROOT/core/furina_agent/persona.py"
grep -Fq 'FURINA_TERMUX_119_OPT_IN_RELATIONSHIP_DOMAIN' "$ROOT/core/furina_agent/relationship_v4.py"
grep -Fq 'FURINA_TERMUX_119_BEHAVIORAL_TRAIT_ENGINE' "$ROOT/core/furina_agent/personality.py"
grep -Fq 'FURINA_TERMUX_119_FULL_LOCAL_ARCHIVE' "$ROOT/core/furina_agent/memory.py"
grep -Fq 'FURINA_TERMUX_119_COMPANION_ENGINE' "$ROOT/core/furina_agent/chat.py"
grep -Fq 'FURINA_TERMUX_119_ADVANCED_SETTINGS' "$ROOT/core/furina_agent/tui.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import json
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.hub_settings import defaults, load_hub_settings, save_hub_settings
from furina_agent.memory import MemoryStore
from furina_agent.personality import TRAIT_ACTION_CARDS_119, TRAIT_IDS, compile_contextual_personality, contextual_traits
from furina_agent.response import choose_profile
from furina_agent.relationship_v4 import RelationshipEngine

assert len(TRAIT_ACTION_CARDS_119)==20 and set(TRAIT_ACTION_CARDS_119)==set(TRAIT_IDS)
assert all({'core','close','play','conflict','avoid'} <= set(card) for card in TRAIT_ACTION_CARDS_119.values())
assert defaults()['partner_mode'] is False and defaults()['full_local_memory'] is False

store=MemoryStore(); store.create_session_conversation('settings')
tables={x[0] for x in store._conn().execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert {'full_memory_archive','relationship_ledger_119'} <= tables
assert RelationshipEngine(store).snapshot()['relationship']['id']=='companion'

# Default is an honest non-romantic companion, even when romantic-coded traits
# are selected. The behavior contract must give concrete actions, not vectors.
ctx={'store':store,'profile':'CASUAL','relationship':{},'partner_mode':False}
plain=compile_contextual_personality(['yandere','hiyakasudere'],'aku kangen kamu',context=ctx)
assert 'MODE PASANGAN NONAKTIF' in plain and 'jangan mengaku pacar/pasangan' in plain
assert 'TINDAKAN TRAIT UNTUK GILIRAN INI' in plain and 'Yandere:' in plain and 'Hiyakasudere:' in plain

# Two traits remain present. Ten traits use a stable anchor plus situational and
# coverage slots; underused traits appear over a run instead of being starved.
two=contextual_traits(['tsundere','oneesan'],'aku capek',context={'store':store,'profile':'CLOSE','relationship':{}})
assert two==['tsundere','oneesan'],two
ten=list(TRAIT_IDS[:10]); seen=set()
for i in range(36):
    selected=contextual_traits(ten,'obrolan santai '+str(i),context={'store':store,'profile':'CASUAL','relationship':{}})
    assert 2 <= len(selected) <= 4 and selected[0]==ten[0],selected
    seen.update(selected)
assert len(seen)>=8,(seen,ten)

# Every one of the 20 selections produces a concrete action in every supported
# situation; no trait exists only as metadata/vector knowledge.
scenarios=(
    ('obrolan santai', 'CASUAL', {}),
    ('aku sedih dan lelah', 'CLOSE', {}),
    ('wkwk godain aku', 'CASUAL', {}),
    ('bukan itu, jangan begitu', 'CASUAL', {'friction':.55}),
)
for trait_id in TRAIT_IDS:
    for text,profile,relationship in scenarios:
        rendered=compile_contextual_personality([trait_id],text,context={'store':store,'profile':profile,'relationship':relationship,'partner_mode':False})
        card=TRAIT_ACTION_CARDS_119[trait_id]
        assert 'TINDAKAN TRAIT UNTUK GILIRAN INI' in rendered and any(card[key] in rendered for key in ('core','close','play','conflict'))

# Mode pasangan changes behavior, relationship context, and CLOSE rhythm only
# through the explicit setting.
state=load_hub_settings(); state['personality_traits']=['tsundere','oneesan']; save_hub_settings(state)
cfg=load_config(); cfg.routing_mode='local'; cfg.persona_name='Furina'; cfg.user_nickname='Wynn'
chat=FurinaChat(cfg,store,object())
system=chat._messages('aku sedih hari ini',choose_profile('aku sedih hari ini',store))[0]['content']
assert 'bukan pasangan romantis' in system and 'MODE PASANGAN NONAKTIF' in system
assert 'seperti pasangan yang mengenal user' not in choose_profile('aku sedih',store).instruction
state=load_hub_settings(); state['partner_mode']=True; save_hub_settings(state)
romance=chat._messages('aku kangen kamu',choose_profile('aku kangen kamu',store))[0]['content']
assert 'pasangan romantis (opt-in)' in romance and 'MODE PASANGAN AKTIF' in romance
assert RelationshipEngine(store).snapshot()['relationship']['id']=='partner'

# Full memory is off by default: normal working messages exist, raw archive and
# cross-session recall do not. Enabling captures exact user+assistant text and
# makes only relevant archive snippets retrievable.
state=load_hub_settings(); state['full_local_memory']=False; save_hub_settings(state)
off_store=MemoryStore(); off_store.create_session_conversation('off')
off_store.add_message('user','Kode rahasia kebun adalah nila tujuh.')
assert off_store._conn().execute('SELECT count(*) FROM full_memory_archive').fetchone()[0]==0
assert off_store.search_conversation_context('kode rahasia kebun',4)==[]

state=load_hub_settings(); state['full_local_memory']=True; save_hub_settings(state)
archive=MemoryStore(); archive.create_session_conversation('arsip lama')
user_id=archive.add_message('user','Kode rahasia kebun adalah nila tujuh.')
assistant_id=archive.add_message('assistant','Baik, nila tujuh adalah kode kebunmu.')
rows=archive._conn().execute('SELECT message_id,role,content FROM full_memory_archive ORDER BY id').fetchall()
assert [(x['message_id'],x['role'],x['content']) for x in rows[-2:]]==[
    (user_id,'user','Kode rahasia kebun adalah nila tujuh.'),(assistant_id,'assistant','Baik, nila tujuh adalah kode kebunmu.')]
archive.create_session_conversation('sekarang')
user_hits=archive.search_conversation_context('apa kode rahasia kebun?',4)
assistant_hits=archive.search_full_archive('kode kebun nila',2,roles=('assistant',))
assert user_hits and user_hits[0]['role']=='user',user_hits
assert assistant_hits and assistant_hits[0]['role']=='assistant',assistant_hits
assert archive.search_conversation_context('topik sama sekali berbeda meteorologi',4)==[]

# Relationship ledger is opt-in and bounded to explicit relational evidence.
state=load_hub_settings(); state['partner_mode']=False; save_hub_settings(state)
assert archive.record_relationship_moment('aku sayang kamu','aku juga',user_id) is None
state=load_hub_settings(); state['partner_mode']=True; save_hub_settings(state)
assert archive.record_relationship_moment('aku sayang kamu','aku juga',user_id)
assert archive.relationship_moments(3)[0]['kind']=='affection'

print('FURINA_TERMUX_119_BEHAVIORAL_ROMANCE_MEMORY_REGRESSION_OK')
PY

echo FURINA_TERMUX_119_VALIDATION_OK
