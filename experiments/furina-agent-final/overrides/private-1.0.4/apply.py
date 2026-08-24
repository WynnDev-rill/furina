#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
HERE = Path(__file__).resolve().parent
CORE = ROOT / "core/furina_agent"

version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if 'VERSION = "1.0.3"' not in text:
    raise SystemExit("expected reconstructed Core 1.0.3")
version.write_text(text.replace('VERSION = "1.0.3"', 'VERSION = "1.0.4"', 1), encoding="utf-8")

config = CORE / "config.py"
text = config.read_text(encoding="utf-8")
text, count = re.subn(r"config_revision: int = \d+", "config_revision: int = 8", text, count=1)
if count != 1:
    raise SystemExit("config revision marker missing")
config.write_text(text, encoding="utf-8")

for script in ("memory_fix.py", "chat_fix.py", "hub_stream_fix.py"):
    subprocess.run([sys.executable, str(HERE / script), str(ROOT)], check=True)

for path in CORE.glob("*.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_0_4_UNIFIED_MEMORY_STREAM_OK")
