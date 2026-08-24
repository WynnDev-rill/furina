#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.8/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.9/apply.py" "$ROOT"
python3 -m py_compile "$ROOT"/core/furina_agent/*.py

grep -Fq 'VERSION = "1.0.9"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10067' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.9'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'EXPECTED_CORE_VERSION = "1.0.9"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r49"' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
grep -Fq 'furina-2026.08.24-private-1.0.9' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for p in core.glob('*.py'): ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
models=(core/'local_models.py').read_text(); llm=(core/'llm.py').read_text(); runtime=(core/'local_runtime.py').read_text(); hub=(core/'hub.py').read_text()
for token in ('qwen3-4b-2507-uncensored-q4km','Qwen3 4B Instruct 2507 Uncensored Q4_K_M','6615b7b5184931e4df9c6d0ae9cd29ca9319b73908d4423283d4cc401a12a1cd','HauhauCS/Qwen3-4B-2507-Instruct-Uncensored-HauhauCS-Aggressive'):
    assert token in models,token
assert 'size_hint_bytes' in models and 'def _verified_marker' in models
assert 'Content-Range' in models and 'verify_download(part, item)' in models
assert 'qwen_quality = "qwen3-4b-2507-instruct-uncensored" in model_hint' in llm
assert 'elif qwen_heretic or qwen_quality:' in llm
assert 'cmd.append("--jinja")' in runtime
assert 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r49"' in hub
print('FURINA_PRIVATE_1_0_9_STRUCTURE_OK')
PY

TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
import hashlib, json
from pathlib import Path
from furina_agent import local_models
ids=[x['id'] for x in local_models.CATALOG]
assert ids==['wifugpt-1.7b-q4km','qwen3-1.7b-heretic-q5km','qwen3-4b-2507-uncensored-q4km'],ids
item=local_models.catalog_item('qwen3-4b-2507-uncensored-q4km')
assert item['size_bytes']==0 and item['size_label']=='2,50 GB'
assert item['sha256']=='6615b7b5184931e4df9c6d0ae9cd29ca9319b73908d4423283d4cc401a12a1cd'
rows=local_models.catalog_state('')
assert len(rows)==3 and rows[-1]['name'].startswith('Qwen3 4B Instruct 2507')
# Exercise unknown-size verification/marker semantics with a tiny synthetic GGUF.
test=Path(local_models.MODELS_DIR)/'synthetic.gguf'; test.parent.mkdir(parents=True,exist_ok=True); test.write_bytes(b'GGUF'+b'x'*32)
synthetic={'id':'synthetic','sha256':hashlib.sha256(test.read_bytes()).hexdigest(),'size_bytes':0}
assert local_models.verify_download(test,synthetic)==36
local_models._write_verified_marker(test,synthetic)
assert local_models._marker_valid(test,synthetic)
print('FURINA_109_DYNAMIC_SIZE_VERIFICATION_OK')
PY

# Preserve Grounded Dialogue State: adding the quality model must not reintroduce
# canned/fast-patch conversational responses.
FURINA_HOME="$TMP_HOME/dialogue" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.chat import FurinaChat
from furina_agent.config import load_config
from furina_agent.memory import MemoryStore
class FakeLLM:
    def __init__(self): self.calls=[]
    def prewarm_local(self): pass
    def cancel(self): pass
    def chat(self,messages,**kwargs): self.calls.append((messages,kwargs)); return 'generated-by-model'
cfg=load_config(); cfg.routing_mode='local'; store=MemoryStore(); llm=FakeLLM(); chat=FurinaChat(cfg,store,llm); chat._schedule_background=lambda *a,**k:None
assert chat.respond('halo')=='generated-by-model'
assert chat.respond('p')=='generated-by-model'
assert len(llm.calls)==2
assert all(call[0][-1]['role']=='user' for call in llm.calls)
print('FURINA_109_GROUNDED_MODEL_GENERATION_OK')
PY

echo FURINA_PRIVATE_1_0_9_VALIDATION_OK
