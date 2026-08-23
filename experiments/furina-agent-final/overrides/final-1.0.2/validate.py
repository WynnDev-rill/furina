from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = ROOT / "core" / "furina_agent"

required_files = [
    CORE / "local_runtime.py",
    CORE / "streaming.py",
    CORE / "stream_state.py",
    CORE / "stream_protocol.py",
    CORE / "performance.py",
]
for path in required_files:
    if not path.exists():
        raise SystemExit(f"missing Local Performance V2 file: {path}")
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

cfg = (CORE / "config.py").read_text(encoding="utf-8")
llm = (CORE / "llm.py").read_text(encoding="utf-8")
assert "context_size: int = 4096" in cfg
assert "keep_warm_seconds: int = 600" in cfg
assert "cache_reuse: int = 256" in cfg
assert "flash_attention: str = \"auto\"" in cfg
assert "SmoothStream" in llm
assert "def cancel(self)" in llm

print("Local Performance V2 static contract: OK")
