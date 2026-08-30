#!/usr/bin/env python3
"""Build Core 1.1.30: adaptive romantic dialogue and reliable private asides."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
CORE = ROOT / "core/furina_agent"
HERE = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing {label}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: Path, marker: str, payload: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + payload.strip() + "\n", encoding="utf-8")


for name in ("character_state_v129.py", "chat_v129.py", "surface_v129.py", "chat_v130.py", "surface_v130.py"):
    shutil.copy2(HERE / name, CORE / name)

replace_once(CORE / "version.py", 'VERSION = "1.1.28"', 'VERSION = "1.1.30"', "Core 1.1.28")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.29-r78"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.30-r80"', "dependency r78")
replace_once(CORE / "hub.py", "furina-2026.08.29-termux-1.1.28", "furina-2026.08.30-termux-1.1.30", "bundle 1.1.28")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.29-r78"', 'expected_revision = "2026.08.30-r80"', "expected revision r78")

append_once(CORE / "chat.py", "FURINA_TERMUX_129_INTERLEAVED_PRIVATE_ASIDES", r'''
# FURINA_TERMUX_129_INTERLEAVED_PRIVATE_ASIDES
from .chat_v129 import install_chat_v129
install_chat_v129(globals())
''')
append_once(CORE / "chat_surface.py", "FURINA_TERMUX_129_BLUE_ASIDE_RENDERER", r'''
# FURINA_TERMUX_129_BLUE_ASIDE_RENDERER
from .surface_v129 import install_surface_v129
install_surface_v129(globals())
''')

append_once(CORE / "chat.py", "FURINA_TERMUX_130_ADAPTIVE_ROMANCE_ASIDES", r'''
# FURINA_TERMUX_130_ADAPTIVE_ROMANCE_ASIDES
from .chat_v130 import install_chat_v130
install_chat_v130(globals())
''')
append_once(CORE / "chat_surface.py", "FURINA_TERMUX_130_RESTORED_LABEL_BLUE_ASIDES", r'''
# FURINA_TERMUX_130_RESTORED_LABEL_BLUE_ASIDES
from .surface_v130 import install_surface_v130
install_surface_v130(globals())
''')

print("FURINA_TERMUX_130_ADAPTIVE_ROMANCE_SYSTEM_OK")
