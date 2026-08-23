#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/tmp/furina-agent-rc54-validate/termux}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$HERE/../.." && pwd)"

bash "$PROJECT/overrides/private-1.0.1/validate.sh" "$ROOT"
python3 "$HERE/apply.py" "$ROOT"
python3 "$HERE/preserve_quality.py" "$ROOT"
python3 "$PROJECT/overrides/android-private-1.0.2/apply.py" "$ROOT"

python3 -m py_compile \
  "$ROOT/core/furina_agent/config.py" \
  "$ROOT/core/furina_agent/llm.py" \
  "$ROOT/core/furina_agent/providers.py" \
  "$ROOT/core/furina_agent/routing.py" \
  "$ROOT/core/furina_agent/local_runtime.py" \
  "$ROOT/core/furina_agent/performance.py" \
  "$ROOT/core/furina_agent/streaming.py" \
  "$ROOT/core/furina_agent/tui.py" \
  "$ROOT/core/furina_agent/hub.py"

grep -Fq 'VERSION = "1.0.2"' "$ROOT/core/furina_agent/version.py"
grep -Fq 'versionCode 10060' "$ROOT/bridge/app/build.gradle"
grep -Fq "versionName '1.0.2'" "$ROOT/bridge/app/build.gradle"
grep -Fq 'furina-2026.08.24-private-1.0.2' "$ROOT/bridge/app/src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

env STAGE_ROOT="$ROOT" python3 - <<'PY'
import ast, os
from pathlib import Path
root=Path(os.environ['STAGE_ROOT']); core=root/'core/furina_agent'
for p in core.glob('*.py'): ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
config=(core/'config.py').read_text(); routing=(core/'routing.py').read_text(); llm=(core/'llm.py').read_text(); providers=(core/'providers.py').read_text(); runtime=(core/'local_runtime.py').read_text(); perf=(core/'performance.py').read_text(); tui=(core/'tui.py').read_text(); models=(core/'local_models.py').read_text(); page=(root/'bridge/app/src/main/assets/furinahub/index.html').read_text()
assert 'context_size: int = 4096' in config and 'threads: int = 5' in config
assert 'max_tokens: int = 2048' in config and 'response_continuations: int = 4' in config
assert 'cache_reuse: int = 256' in config and 'keep_warm_seconds: int = 600' in config
assert 'flash_attention: str = "auto"' in config and 'accel_backend: str = "auto"' in config
assert 'timeout=135' not in routing and 'ensure_ready(timeout=45.0' in routing
assert 'prewarm_local' in routing and 'stop_local' in routing and 'def cancel(self)' in routing
assert 'SmoothStream' in llm and '"stream": bool(on_token) and not json_mode' in llm
assert 'SmoothStream' in providers and 'on_token=None' in providers and '"stream": bool(on_token) and not json_mode' in providers
assert 'Never fail over after visible text has streamed' in routing
assert 'min(timeout, 45.0)' in runtime and 'keep_warm_seconds' in runtime
assert '--cache-reuse' in runtime and '--flash-attn' in runtime and '_flag_supported' in runtime
assert 'for threads in (4, 5, 6)' in perf and 'FURINA_LLAMA_SERVER_OPENCL' in perf and 'FURINA_LLAMA_SERVER_VULKAN' in perf
assert 'sedang disiapkan di background' in tui
assert "action == \"prewarm\"" in (core/'hub.py').read_text()
assert "action:'prewarm'" in page and 'Menyiapkan model lokal' in page
# Point 7 explicitly remains unchanged.
assert 'wifugpt-1.7b-q4km' in models and 'qwen3-1.7b-heretic-q5km' in models
assert 'Q4_K_M' in models and 'Q5_K_M' in models
print('FURINA_PRIVATE_1_0_2_STATIC_OK')
PY

# First visible stream chunk must not wait for the coalescing frame.
PYTHONPATH="$ROOT/core" python3 - <<'PY'
import time
from furina_agent.streaming import SmoothStream
seen=[]
s=SmoothStream(lambda x: seen.append((x,time.monotonic())),frame_ms=30,max_buffer_chars=96)
t0=time.monotonic(); s.feed('A')
limit=time.monotonic()+0.2
while not seen and time.monotonic()<limit: time.sleep(.002)
assert seen and seen[0][0]=='A' and (seen[0][1]-t0)<.08
s.feed('B'); s.feed('C'); s.close(); assert ''.join(x[0] for x in seen)=='ABC'
print('FURINA_STREAM_V2_FIRST_CHUNK_OK')
PY

# Config migration optimizes legacy performance defaults without reducing the
# prior response-quality budget.
TMP_HOME="$(mktemp -d)"; trap 'rm -rf "$TMP_HOME"' EXIT
mkdir -p "$TMP_HOME/data"
cat >"$TMP_HOME/config.json" <<'JSON'
{"config_revision":5,"context_size":6144,"threads":6,"max_tokens":2048,"response_continuations":4,"routing_mode":"local"}
JSON
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
c=load_config(); assert c.config_revision==6; assert c.context_size==4096; assert c.threads==5; assert c.max_tokens==2048; assert c.response_continuations==4
print('FURINA_LOCAL_PERF_MIGRATION_OK')
PY

# Generic import/startup must not spawn llama-server; prewarm is explicit.
FURINA_HOME="$TMP_HOME" PYTHONPATH="$ROOT/core" python3 - <<'PY'
from furina_agent.config import load_config
from furina_agent.routing import RoutingLLM
r=RoutingLLM(load_config())
assert r.runtime.status.state=='stopped'
print('FURINA_NO_GENERIC_PREWARM_OK')
PY

echo FURINA_PRIVATE_1_0_2_VALIDATION_OK
