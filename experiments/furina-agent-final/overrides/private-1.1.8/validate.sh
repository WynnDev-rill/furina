#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"
bash "$PROJECT/overrides/private-1.1.7/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.17"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'FURINA_TERMUX_117_HYBRID_VERSIONED_MEMORY' "$ROOT/core/furina_agent/memory.py"
grep -Fq 'FURINA_TERMUX_117_CONTEXTUAL_FACETS' "$ROOT/core/furina_agent/personality.py"
grep -Fq 'FURINA_TERMUX_117_PUBLIC_CLI_BOUNDARY' "$ROOT/core/furina_agent/cli.py"
grep -Fq 'providers_ready = bool(ProviderSecrets().configured())' "$ROOT/core/furina_agent/tui.py"

TEST_HOME="$(mktemp -d)"
HOME="$TEST_HOME" FURINA_HOME="$TEST_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import math
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.personality import TRAIT_IDS, contextual_traits, compile_contextual_personality
from furina_agent.companion import CompanionSession
from furina_agent.routing import RoutingLLM
from furina_agent.cli import build_parser, collect_doctor_checks

store=MemoryStore()
assert {'message_vectors','memory_versions'} <= {r[0] for r in store._conn().execute("SELECT name FROM sqlite_master WHERE type='table'")}
old=store.create_session_conversation('lama')
store.add_message('user','Aku lebih suka jawaban ringkas dan langsung ke inti.')
new=store.create_session_conversation('baru')
assert old != new
hits=store.search_conversation_context('jawab ringkas',4)
assert hits and 'jawaban ringkas' in hits[-1]['content'],hits
assert store.search_conversation_context('harga mangga di bulan',4)==[]

# Optional embedding rerank must recover a paraphrase with no shared keyword.
store._embed_text=lambda text: [1.0,0.0] if any(x in str(text).casefold() for x in ('ringkas','bertele-tele','singkat')) else [0.0,1.0]
old_row=store._conn().execute("SELECT id,content FROM messages WHERE conversation_id=? AND role='user' ORDER BY id DESC LIMIT 1",(old,)).fetchone()
assert store.index_message_vector(int(old_row['id']),str(old_row['content']))
semantic=store.search_conversation_context('jangan bertele-tele',4)
assert semantic and 'jawaban ringkas' in semantic[-1]['content'],semantic

store.add_memory('Aku lebih suka jawaban yang panjang dan rinci','preference',.8,confidence=.9,source='explicit')
store.add_memory('Sekarang aku lebih suka jawaban yang ringkas dan rinci','preference',.9,confidence=.9,source='explicit')
versions=store._conn().execute("SELECT * FROM memory_versions WHERE entity_type='memory'").fetchall()
assert versions, 'correction must version, not silently overwrite'

active=contextual_traits(TRAIT_IDS,'Ada bug pada model provider di Termux')
assert 2 <= len(active) <= 4 and len(active) < len(TRAIT_IDS)
assert len(compile_contextual_personality(TRAIT_IDS,'Aku sedang sedih')) < 1800

cfg=load_config(); session=CompanionSession(cfg,store,RoutingLLM(cfg))
assert not hasattr(session,'bridge') and not hasattr(session,'agent')
commands=set(build_parser()._subparsers._group_actions[0].choices)
assert not commands & {'pair','connect','screen','apps','screenshot','agent','serve','repair'}
assert {'chat','update','status','doctor','providers'} <= commands
assert all(name not in {'bridge','accessibility'} for name,_,_ in collect_doctor_checks())
print('FURINA_TERMUX_117_MEMORY_PERSONA_BOUNDARY_OK')
PY

echo FURINA_TERMUX_117_VALIDATION_OK
