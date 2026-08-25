#!/usr/bin/env python3
"""Advance the shared Core contract after repairing Hub state rendering."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/furina-agent-rc54-validate/termux')
CORE=ROOT/'core/furina_agent'
version=CORE/'version.py'; text=version.read_text(encoding='utf-8')
if 'VERSION = "1.1.14"' not in text: raise SystemExit('expected Core 1.1.14')
version.write_text(text.replace('VERSION = "1.1.14"','VERSION = "1.1.15"',1),encoding='utf-8')
hub=CORE/'hub.py'; text=hub.read_text(encoding='utf-8')
for old,new,label in (
 ('EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r64"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.25-r65"', 'revision'),
 ('expected_bundle = "furina-2026.08.25-private-1.1.14"', 'expected_bundle = "furina-2026.08.25-private-1.1.15"', 'authoritative bundle'),
 ('expected_revision = "2026.08.25-r64"', 'expected_revision = "2026.08.25-r65"', 'authoritative revision'),
 ('snapshot["bridge_target"] = "1.1.14"', 'snapshot["bridge_target"] = "1.1.15"', 'bridge target'),
):
    if old not in text: raise SystemExit(f'{label} marker missing')
    text=text.replace(old,new,1)
text=text.replace('furina-2026.08.25-private-1.1.14', 'furina-2026.08.25-private-1.1.15')
hub.write_text(text,encoding='utf-8')
print('FURINA_FINAL_116_CORE_OK')
