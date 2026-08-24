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
if 'VERSION = "1.0.7"' not in text:
    raise SystemExit("expected reconstructed Core 1.0.7")
version.write_text(text.replace('VERSION = "1.0.7"', 'VERSION = "1.0.8"', 1), encoding="utf-8")

subprocess.run([sys.executable, str(HERE / "dialogue_architecture.py"), str(ROOT)], check=True)

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
text, count = re.subn(r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r48"', text, count=1)
if count != 1:
    raise SystemExit("hub dependency revision marker missing")
text = text.replace("furina-2026.08.24-private-1.0.7", "furina-2026.08.24-private-1.0.8")
text = text.replace('"bridge_target": "1.0.7"', '"bridge_target": "1.0.8"')
hub.write_text(text, encoding="utf-8")

for path in CORE.glob("*.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("FURINA_PRIVATE_1_0_8_DIALOGUE_STATE_OK")
