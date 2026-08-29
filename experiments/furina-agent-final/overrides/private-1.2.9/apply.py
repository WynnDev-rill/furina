#!/usr/bin/env python3
"""Build Core 1.1.28: adaptive human dialogue and optional character inner voice."""
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


for name in (
    "settings_v128.py", "persona_v128.py", "style_v128.py", "personality_v128.py",
    "output_v128.py", "chat_v128.py", "tui_v128.py",
):
    shutil.copy2(HERE / name, CORE / name)

replace_once(CORE / "version.py", 'VERSION = "1.1.27"', 'VERSION = "1.1.28"', "Core 1.1.27")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.29-r77"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.29-r78"', "dependency r77")
replace_once(CORE / "hub.py", "furina-2026.08.29-termux-1.1.27", "furina-2026.08.29-termux-1.1.28", "bundle 1.1.27")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.29-r77"', 'expected_revision = "2026.08.29-r78"', "expected revision r77")

append_once(CORE / "hub_settings.py", "FURINA_TERMUX_128_INNER_THOUGHT_SETTING", r'''
# FURINA_TERMUX_128_INNER_THOUGHT_SETTING
from .settings_v128 import install_settings_v128
install_settings_v128(globals())
''')
append_once(CORE / "persona.py", "FURINA_TERMUX_128_NEUTRAL_HUMAN_IDENTITY", r'''
# FURINA_TERMUX_128_NEUTRAL_HUMAN_IDENTITY
from .persona_v128 import install_persona_v128
install_persona_v128(globals())
''')
append_once(CORE / "personality.py", "FURINA_TERMUX_128_SOCIAL_STATE", r'''
# FURINA_TERMUX_128_SOCIAL_STATE
from .personality_v128 import install_personality_v128
install_personality_v128(globals())
''')
append_once(CORE / "providers.py", "FURINA_TERMUX_128_HUMAN_ROLEPLAY_GATE", r'''
# FURINA_TERMUX_128_HUMAN_ROLEPLAY_GATE
from .output_v128 import install_output_v128
install_output_v128(globals())
''')
append_once(CORE / "chat.py", "FURINA_TERMUX_128_ADAPTIVE_STYLE_POLICY", r'''
# FURINA_TERMUX_128_ADAPTIVE_STYLE_POLICY
from .chat_v128 import install_chat_v128
install_chat_v128(globals())
''')
append_once(CORE / "tui.py", "FURINA_TERMUX_128_INNER_THOUGHT_UI", r'''
# FURINA_TERMUX_128_INNER_THOUGHT_UI
from .tui_v128 import install_tui_v128
install_tui_v128(globals())
''')

print("FURINA_TERMUX_128_ADAPTIVE_HUMAN_DIALOGUE_OK")
