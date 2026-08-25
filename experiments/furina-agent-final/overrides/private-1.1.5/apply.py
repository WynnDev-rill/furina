#!/usr/bin/env python3
"""Advance the final contract after decoupling pairing from update metadata."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
CORE=ROOT/'core/furina_agent'
version=CORE/'version.py'; text=version.read_text(encoding='utf-8')
if 'VERSION = "1.1.13"' not in text: raise SystemExit('expected Core 1.1.13')
version.write_text(text.replace('VERSION = "1.1.13"','VERSION = "1.1.14"',1),encoding='utf-8')
hub=CORE/'hub.py'; text=hub.read_text(encoding='utf-8')
if 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r63"' not in text: raise SystemExit('expected r63')
text=text.replace('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r63"','EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r64"',1).replace('furina-2026.08.25-private-1.1.13','furina-2026.08.25-private-1.1.14')
for old,new,label in (
    ('expected_revision = "2026.08.25-r63"', 'expected_revision = "2026.08.25-r64"', 'authoritative revision'),
    ('snapshot["bridge_target"] = "1.1.13"', 'snapshot["bridge_target"] = "1.1.14"', 'bridge target'),
):
    if old not in text: raise SystemExit(f'{label} marker missing')
    text=text.replace(old,new,1)
hub.write_text(text,encoding='utf-8')
print('FURINA_FINAL_115_CORE_OK')
