#!/usr/bin/env python3
"""Build Core 1.1.27: restore 20-trait UI and harden visible output."""
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


for name in ("settings_v127.py", "personality_v127.py", "output_v127.py", "chat_v127.py", "tui_v127.py"):
    shutil.copy2(HERE / name, CORE / name)

replace_once(CORE / "version.py", 'VERSION = "1.1.26"', 'VERSION = "1.1.27"', "Core 1.1.26")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r76"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.29-r77"', "dependency r76")
replace_once(CORE / "hub.py", "furina-2026.08.27-termux-1.1.26", "furina-2026.08.29-termux-1.1.27", "bundle 1.1.26")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.27-r76"', 'expected_revision = "2026.08.29-r77"', "expected revision r76")

append_once(CORE / "hub_settings.py", "FURINA_TERMUX_127_BUILTIN_TRAITS_ONLY", r'''
# FURINA_TERMUX_127_BUILTIN_TRAITS_ONLY
from .settings_v127 import install_settings_v127
install_settings_v127(globals())
''')
append_once(CORE / "personality.py", "FURINA_TERMUX_127_TWENTY_TRAIT_ENGINE", r'''
# FURINA_TERMUX_127_TWENTY_TRAIT_ENGINE
from .personality_v127 import install_personality_v127
install_personality_v127(globals())
''')
append_once(CORE / "providers.py", "FURINA_TERMUX_127_VISIBLE_OUTPUT_GATE", r'''
# FURINA_TERMUX_127_VISIBLE_OUTPUT_GATE
from .output_v127 import install_output_v127
install_output_v127(globals())
''')
append_once(CORE / "chat.py", "FURINA_TERMUX_127_HISTORY_QUARANTINE", r'''
# FURINA_TERMUX_127_HISTORY_QUARANTINE
from .chat_v127 import install_chat_v127
install_chat_v127(globals())
''')
append_once(CORE / "tui.py", "FURINA_TERMUX_127_RESTORED_PERSONALITY_UI", r'''
# FURINA_TERMUX_127_RESTORED_PERSONALITY_UI
from .tui_v127 import install_tui_v127
install_tui_v127(globals())
''')

print("FURINA_TERMUX_127_OUTPUT_PERSONALITY_OK")
