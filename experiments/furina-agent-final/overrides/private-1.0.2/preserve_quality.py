#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CONFIG = ROOT / "core/furina_agent/config.py"
PROVIDERS = ROOT / "core/furina_agent/providers.py"
LLM = ROOT / "core/furina_agent/llm.py"

text = CONFIG.read_text(encoding="utf-8")
text = text.replace("max_tokens: int = 1536", "max_tokens: int = 2048", 1)
text = text.replace("response_continuations: int = 2", "response_continuations: int = 4", 1)
text = text.replace('defaults["max_tokens"] = 1536', 'defaults["max_tokens"] = 2048')
text = text.replace('defaults["response_continuations"] = 2', 'defaults["response_continuations"] = 4')
CONFIG.write_text(text, encoding="utf-8")

# Continuation ceilings remain the same as 1.0.1; latency work must not shorten
# an answer merely to make a benchmark look better.
for path in (PROVIDERS, LLM):
    body = path.read_text(encoding="utf-8")
    body = body.replace("max(384,min(max_tokens,1536))", "max(512,min(max_tokens,2048))")
    body = body.replace("max(384, min(limit, 1536))", "max(512, min(limit, 2048))")
    path.write_text(body, encoding="utf-8")

print("FURINA_PRIVATE_1_0_2_QUALITY_BUDGET_PRESERVED")
