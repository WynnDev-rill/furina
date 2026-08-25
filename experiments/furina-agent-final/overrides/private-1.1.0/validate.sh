#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.9/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$HERE/fixup.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.1.0/apply.py" "$ROOT"

python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.1.6"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10074' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.1.6'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.1.6"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq '2026.08.25-r56' "$ROOT/core/furina_agent/hub.py"
grep -Fq 'furina-2026.08.25-private-1.1.6' "$ROOT/core/furina_agent/hub.py"

STAGE_ROOT="$ROOT" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'; app=root/'bridge/app'; html=app/'src/main/assets/furinahub/index.html'; main=app/'src/main/java/com/wynndev/furinaagentbridge/MainActivity.java'
from furina_agent.personality import TRAITS, TRAIT_IDS, normalize_traits, compile_personality, conversation_pacing
expected=('tsundere','yandere','kuudere','dandere','deredere','himedere','kamidere','sadodere','mayadere','bakadere','hajidere','darudere','shundere','utsudere','bodere','hiyakasudere','nyandere','oujodere','genki','oneesan')
assert TRAIT_IDS==expected, TRAIT_IDS
assert len(TRAITS)==20 and len({x.id for x in TRAITS})==20
assert all(x.label and len(x.description)>=35 for x in TRAITS)
assert normalize_traits([])==[]
assert normalize_traits(expected)==list(expected)
for combo in (expected, ('tsundere','deredere'), ('kuudere','genki'), ('yandere','oneesan','oujodere'), ('sadodere','hiyakasudere','dandere','darudere')):
    prompt=compile_personality(combo)
    assert len(prompt)<2600, len(prompt)
    low=prompt.casefold()
    for trait in TRAITS:
        assert trait.label.casefold() not in low, (trait.label,prompt)
assert 'skenario' in conversation_pacing('p').casefold()
assert 'jawab inti' in conversation_pacing('apakah daun berwarna merah?').casefold()
print('FURINA_110_TRAIT_COMPILER_OK')

chat=(core/'chat.py').read_text(); hub=(core/'hub.py').read_text(); tui=(core/'tui.py').read_text(); hs=(core/'hub_settings.py').read_text(); persona=(core/'persona.py').read_text(); dialog=(core/'dialogue_state.py').read_text(); page=html.read_text(); java=main.read_text()
assert 'FURINA_PERSONALITY_SCHEMA_V3' in hs and 'personality_traits' in hs
assert 'FURINA_TUI_PERSONALIZATION_110' in tui and 'Personalisasi' in tui
assert 'FURINA_TUI_TOPLEVEL_PERSONALIZATION_113' in tui
assert 'elif choice == "Personalisasi":\n            _private_personalization_116(console)' in tui
assert 'FURINA_TUI_PERSONALITY_MENU_116' in tui and '_personality_key_116' in tui
assert 'time.monotonic() + 0.55' in tui and 'malformed escape sequences are ignored' in tui
assert '[white]{line}[/]' in tui and 'Gagal menyimpan' in tui
assert 'FURINA_CHAT_110' in chat and 'conversation_pacing' in chat
assert 'FURINA_PERSONA_110' in persona
assert 'assistant_reference' in dialog and 'BALASAN FURINA LAMA: tidak diperlukan' in dialog
assert 'Runtime._queue_auto_title = _queue_auto_title_110' in hub
node=next(n for n in ast.parse(hub).body if isinstance(n,ast.FunctionDef) and n.name=='_queue_auto_title_110')
segment='\n'.join(hub.splitlines()[node.lineno-1:node.end_lineno])
assert 'llm.chat' not in segment and 'Thread(' not in segment
assert 'action == "select"' in hub and 'action == "online"' in hub and 'furinahub-local-prewarm' in hub
assert 'personalityTraitGrid110' in page and 'togglePersonality110' in page
assert "action:'select',catalog_id:catalogId" in page and "action:'online'" in page
for forbidden in ('checkAllUpdates(', 'refreshAppUpdate(', 'syncUnifiedUpdateStatus(', "'/api/update/core'", "'/api/update/status'", 'customInstructions', 'trait_labels'):
    assert forbidden not in page, forbidden
assert 'furina update' in page
assert 'bridgeUpdater = new BridgeUpdater' not in java
assert 'bridgeUpdater.onResume()' not in java
assert 'handler.post(this::startCoreRecoveryUpdate)' not in java
assert 'Pembaruan dikelola melalui Termux: furina update' in java
print('FURINA_110_STATIC_SURFACE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT
mkdir -p "$TMP_HOME/data"
FURINA_HOME="$TMP_HOME" STAGE_ROOT="$ROOT" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.hub_settings import defaults, load_hub_settings, save_hub_settings, personalization_prompt
from furina_agent.personality import TRAIT_IDS
s=defaults(); s['personality_traits']=list(TRAIT_IDS); save_hub_settings(s)
r=load_hub_settings(); assert r['personality_traits']==list(TRAIT_IDS), r['personality_traits']
p=personalization_prompt(r); assert '20 facet aktif' in p and 'Tsundere' not in p and 'Yandere' not in p
r['personality_traits']=[]; save_hub_settings(r); assert load_hub_settings()['personality_traits']==[]
print('FURINA_110_SHARED_PERSONALITY_ROUNDTRIP_OK')
PY

FURINA_HOME="$TMP_HOME" STAGE_ROOT="$ROOT" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.chat import FurinaChat
from furina_agent.response import choose_profile
from furina_agent.hub_settings import load_hub_settings, save_hub_settings
class DummyLLM: pass
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore(); state=load_hub_settings(); state['personality_traits']=['tsundere','deredere','kuudere']; save_hub_settings(state)
store.add_message('user','halo'); store.add_message('assistant','UNIQUE_OLD_PATTERN dunia aneh playful furious panggilan kosong')
chat=FurinaChat(cfg,store,DummyLLM()); profile=choose_profile('apakah daun berwarna merah?',store); msgs=chat._messages('apakah daun berwarna merah?',profile)
assert len(msgs)==2 and msgs[-1]['role']=='user'
system=msgs[0]['content']; assert 'UNIQUE_OLD_PATTERN' not in system, system
assert 'PERSONAL EXPRESSION' in system and 'Tsundere' not in system and 'Playfulness=' not in system
msgs2=chat._messages('maksud?',profile); assert 'UNIQUE_OLD_PATTERN' in msgs2[0]['content'] and 'clarification_target' in msgs2[0]['content']
msgs3=chat._messages('p',profile); assert 'UNIQUE_OLD_PATTERN' not in msgs3[0]['content']
cfg.routing_mode='online'; online=chat._messages('halo',profile)[0]['content']; assert 'PERSONAL EXPRESSION' in online and 'Tsundere' not in online
print('FURINA_110_GROUNDED_PATTERN_RESET_OK')
PY

FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent import local_models
ids=[x['id'] for x in local_models.CATALOG]
assert ids==['wifugpt-1.7b-q4km','qwen3-1.7b-heretic-q5km','qwen3-4b-2507-uncensored-q4km'],ids
print('FURINA_110_THREE_MODEL_CATALOG_OK')
PY

grep -Fq '/api/chat/progress' "$ROOT/bridge/app/src/main/assets/furinahub/index.html"
grep -Fq 'sendMessage' "$ROOT/bridge/app/src/main/assets/furinahub/index.html"

echo FURINA_PRIVATE_1_1_0_VALIDATION_OK
