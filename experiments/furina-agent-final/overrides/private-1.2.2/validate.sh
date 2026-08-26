#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.2.1/validate.sh"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.21"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_121_TRAINING_ROOM' "$ROOT/core/furina_agent/tui.py"
grep -Fq 'FURINA_TERMUX_121_TRAINING_PREFERENCE_RUNTIME' "$ROOT/core/furina_agent/chat.py"
test -f "$ROOT/core/furina_agent/training_room.py"

TEST_HOME="$(mktemp -d)"
trap 'rm -rf "$TEST_HOME"' EXIT
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import ast
import json
import os
from pathlib import Path

from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.response import choose_profile
from furina_agent.training_room import (
    CATEGORIES, TrainingSession, load_training_state,
    runtime_preference_contract, training_progress,
)


class FakeLLM:
    def __init__(self): self.calls=[]
    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return json.dumps({"a": "Aku menangkap maksudmu. Kita lihat bagian yang paling penting dulu.", "b": "Hm, aku paham. Duduk sebentar—kita urai satu bagian yang benar-benar mengganggumu."})


home=Path(os.environ['FURINA_HOME']); state_path=home/'data/training-test.json'
source=(Path(__import__('furina_agent.training_room').training_room.__file__)).read_text(encoding='utf-8')
tree=ast.parse(source)
assert not any(isinstance(node,(ast.Import,ast.ImportFrom)) and any(alias.name.endswith('memory') for alias in node.names) for node in ast.walk(tree))
assert list(CATEGORIES)==['natural','emotional','partner','playful','length','language']
assert [CATEGORIES[x]['label'] for x in CATEGORIES]==[
  'Respons natural','Respons emosional','Mode pasangan','Bercanda dan menggoda','Panjang jawaban','Bahasa dan kosakata']
assert all(len(item['scenes'])>=3 and all(len(scene[1])==5 for scene in item['scenes']) for item in CATEGORIES.values())

store=MemoryStore(); store.create_session_conversation('real-user-thread')
before_messages=store._conn().execute('SELECT count(*) FROM messages').fetchone()[0]
before_memories=store._conn().execute('SELECT count(*) FROM memories').fetchone()[0]

# Every category runs through the active model facade. Prompts explicitly mark
# the fictional identity, and generating/rerolling never persists a decision.
for category_id in CATEGORIES:
    fake=FakeLLM(); session=TrainingSession(category_id,fake,state_path=state_path,seed='fixed')
    pair=session.generate()
    assert pair.response_a and pair.response_b and pair.response_a!=pair.response_b
    system=fake.calls[0][0][0]['content']
    assert 'TRAINING SANDBOX' in system and 'jangan anggap sebagai user nyata' in system and 'jangan ekstrak fakta/memori' in system
    assert fake.calls[0][1]['role']=='training' and fake.calls[0][1]['json_mode'] is True
    session.reroll(); session.generate()
assert training_progress(state_path)['total']==0

# A choice stores only the preference dataset. The scenario remains absent
# from all real-message and memory tables, and R did not fabricate a vote.
fake=FakeLLM(); session=TrainingSession('emotional',fake,state_path=state_path,seed='stable-seed')
pair=session.generate(); chosen=session.choose('a')
assert chosen['count']==1 and training_progress(state_path)['total']==1
state=load_training_state(state_path)
assert len(state['decisions'])==1 and state['decisions'][0]['simulated_user']==pair.user_text
assert (state_path.stat().st_mode & 0o777)==0o600
assert store._conn().execute('SELECT count(*) FROM messages').fetchone()[0]==before_messages
assert store._conn().execute('SELECT count(*) FROM memories').fetchone()[0]==before_memories
db_text=' '.join(str(x[0] or '') for x in store._conn().execute('SELECT content FROM messages').fetchall())
assert pair.user_text not in db_text

# Runtime receives a bounded abstract rule, never the simulated utterance or
# selected/rejected training transcript. It affects the real chat composer.
contract=runtime_preference_contract(state_path)
assert 'PREFERENSI TRAINING ROOM' in contract and pair.user_text not in contract
assert pair.response_a not in contract and pair.response_b not in contract

# Use the default path for the actual FurinaChat integration.
default_session=TrainingSession('natural',FakeLLM(),seed='runtime')
default_pair=default_session.generate(); default_session.choose('a')
cfg=load_config(); cfg.routing_mode='local'; chat=FurinaChat(cfg,store,object())
system=chat._messages('menurutmu desain ini bagaimana?',choose_profile('menurutmu desain ini bagaimana?',store))[0]['content']
assert 'PREFERENSI TRAINING ROOM' in system
assert default_pair.user_text not in system and default_pair.response_a not in system and default_pair.response_b not in system

# The flow advances five turns, then rotates to a fresh scene without carrying
# the simulated transcript into a real conversation.
flow=TrainingSession('natural',FakeLLM(),state_path=home/'data/flow.json',seed='flow')
titles=[]
for _ in range(6):
    p=flow.generate(); titles.append(p.scene_title); flow.choose('a')
assert titles[:5]==[titles[0]]*5 and titles[5]!=titles[0]

print('FURINA_TERMUX_121_TRAINING_SANDBOX_RUNTIME_OK')
PY

echo FURINA_TERMUX_121_VALIDATION_OK
