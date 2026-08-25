#!/usr/bin/env python3
"""Advance the shared Core bundle for the FurinaHub connection repair."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"

version = CORE / "version.py"
text = version.read_text(encoding="utf-8")
if text.count('VERSION = "1.1.9"') != 1:
    raise SystemExit("expected reconstructed Core 1.1.9")
version.write_text(text.replace('VERSION = "1.1.9"', 'VERSION = "1.1.10"', 1), encoding="utf-8")

hub = CORE / "hub.py"
text = hub.read_text(encoding="utf-8")
text, revision_count = re.subn(
    r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"',
    'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r60"',
    text,
    count=1,
)
if revision_count != 1:
    raise SystemExit("Core dependency revision marker missing")
if "furina-2026.08.25-private-1.1.9" not in text:
    raise SystemExit("Core bundle marker missing")
text = text.replace(
    "furina-2026.08.25-private-1.1.9",
    "furina-2026.08.25-private-1.1.10",
)
hub.write_text(text, encoding="utf-8")

for path in CORE.glob("*.py"):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("FURINA_PRIVATE_1_1_1_CORE_CONNECTION_REPAIR_OK")
