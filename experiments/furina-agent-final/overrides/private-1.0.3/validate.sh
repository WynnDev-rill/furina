#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.2/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.3/apply.py" "$ROOT"

python3 -m py_compile \
  "$ROOT/core/furina_agent/config.py" \
  "$ROOT/core/furina_agent/persona.py" \
  "$ROOT/core/furina_agent/companion.py" \
  "$ROOT/core/furina_agent/chat.py" \
  "$ROOT/core/furina_agent/routing.py" \
  "$ROOT/core/furina_agent/local_runtime.py" \
  "$ROOT/core/furina_agent/tui.py" \
  "$ROOT/core/furina_agent/hub.py"

grep -Fq 'VERSION = "1.0.3"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10061' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.3'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'furina-2026.08.24-private-1.0.3' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for p in core.glob('*.py'): ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
config=(core/'config.py').read_text(); persona=(core/'persona.py').read_text(); companion=(core/'companion.py').read_text(); chat=(core/'chat.py').read_text(); runtime=(core/'local_runtime.py').read_text(); tui=(core/'tui.py').read_text(); hub=(core/'hub.py').read_text()
assert 'config_revision: int = 7' in config
assert 'context_size: int = 4096' in config
assert 'server_priority: int = 0' in config
assert 'LOCAL_FAST_PATH_V3_MIGRATION' in config
assert 'def build_local_system_prompt' in persona
assert 'LOCAL_FAST_PATH_V3' in chat
assert 'char_budget=700' in chat and 'budget = 1100' in chat
assert 'recent_limit = 6 if profile.name' in chat and 'else 4' in chat
assert 'idle >= 120.0' in chat and '_background_active' in chat
assert 'LOCAL_FAST_CHAT_ROUTER' in companion and 'max_tokens=80' in companion
assert 'safe: bool = False' in runtime and 'retrying safe CPU baseline' in runtime
assert 'if ctx == 6144' in runtime and 'ctx = 4096' in runtime
assert 'server_priority' in runtime and '> 0' in runtime
assert 'pkg, "install", "-y", "llama-cpp"' in runtime
assert 'LOCAL_FAST_PATH_CHAT_PREWARM' in tui
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r43"' in hub
print('FURINA_PRIVATE_1_0_3_STATIC_OK')
PY

# Repair the exact on-device stale state observed after 1.0.2: config revision 6
# with context 6144 and unprivileged priority 1.
TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT
mkdir -p "$TMP_HOME/data"
cat >"$TMP_HOME/config.json" <<'JSON'
{"config_revision":6,"context_size":6144,"threads":5,"server_priority":1,"max_tokens":2048,"response_continuations":4,"routing_mode":"local"}
JSON
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
c=load_config()
assert c.config_revision==7, c
assert c.context_size==4096, c.context_size
assert c.server_priority==0, c.server_priority
assert c.max_tokens==2048 and c.response_continuations==4
print('FURINA_103_STALE_CONFIG_REPAIRED')
PY

# Ordinary conversation must not call the model just to classify intent.
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.companion import CompanionSession
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
class FakeLLM:
    def __init__(self): self.calls=0
    def chat(self,*a,**k): self.calls+=1; raise AssertionError('hi must not call classifier LLM')
llm=FakeLLM(); s=CompanionSession(load_config(),MemoryStore(),llm)
i=s.classify('hi')
assert i.mode=='chat' and llm.calls==0
print('FURINA_103_CHAT_CLASSIFIER_FAST_PATH_OK')
PY

# The local prompt stays bounded even when history and stored memory are long.
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
from furina_agent.response import choose_profile
class Dummy: pass
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore()
for i in range(12):
    store.add_message('user' if i%2==0 else 'assistant', ('riwayat-%d '%i)+('x'*1800))
for i in range(10):
    try: store.add_memory(('memory-%d '%i)+('y'*900),'fact',0.8,confidence=0.8,source='test')
    except TypeError: store.add_memory(('memory-%d '%i)+('y'*900),'fact',0.8)
chat=FurinaChat(cfg,store,Dummy())
profile=choose_profile('hi',store)
msgs=chat._messages('hi',profile)
chars=sum(len(str(m.get('content',''))) for m in msgs)
assert chars < 7200, chars
assert len(msgs) <= 8, len(msgs)
assert 'KONTROL ANDROID' not in msgs[0]['content']
assert 'CONTOH RITME' not in msgs[0]['content']
print('FURINA_103_LOCAL_PROMPT_BOUNDED',chars,len(msgs))
PY

echo FURINA_PRIVATE_1_0_3_VALIDATION_OK
