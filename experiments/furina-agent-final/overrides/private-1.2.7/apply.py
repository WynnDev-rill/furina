#!/usr/bin/env python3
"""Build Core 1.1.26: stable behavior kernel, continuity and private reasoning."""
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
    "settings_v126.py", "personality_v126.py", "memory_v126.py", "response_v126.py",
    "output_v126.py", "chat_v126.py", "tui_v126.py",
):
    shutil.copy2(HERE / name, CORE / name)

replace_once(CORE / "version.py", 'VERSION = "1.1.25"', 'VERSION = "1.1.26"', "Core 1.1.25")
replace_once(CORE / "hub.py", 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r75"', 'EXPECTED_DEPENDENCY_REVISION = "2026.08.27-r76"', "dependency r75")
replace_once(CORE / "hub.py", "furina-2026.08.27-termux-1.1.25", "furina-2026.08.27-termux-1.1.26", "bundle 1.1.25")
replace_once(CORE / "hub.py", 'expected_revision = "2026.08.27-r75"', 'expected_revision = "2026.08.27-r76"', "expected revision r75")

append_once(CORE / "hub_settings.py", "FURINA_TERMUX_126_DYNAMIC_SETTINGS", r'''
# FURINA_TERMUX_126_DYNAMIC_SETTINGS
from .settings_v126 import install_settings_v126
install_settings_v126(globals())
''')
append_once(CORE / "personality.py", "FURINA_TERMUX_126_WHOLE_TRAIT_ENGINE", r'''
# FURINA_TERMUX_126_WHOLE_TRAIT_ENGINE
from .personality_v126 import install_personality_v126
install_personality_v126(globals())
''')
append_once(CORE / "memory.py", "FURINA_TERMUX_126_CONTINUITY_CAPSULE", r'''
# FURINA_TERMUX_126_CONTINUITY_CAPSULE
from .memory_v126 import install_memory_v126
install_memory_v126(globals())
''')
append_once(CORE / "response.py", "FURINA_TERMUX_126_ADAPTIVE_DIALOGUE", r'''
# FURINA_TERMUX_126_ADAPTIVE_DIALOGUE
from .response_v126 import install_response_v126
install_response_v126(globals())
''')
append_once(CORE / "providers.py", "FURINA_TERMUX_126_PRIVATE_REASONING", r'''
# FURINA_TERMUX_126_PRIVATE_REASONING
from .output_v126 import install_output_v126
install_output_v126(globals())
''')
append_once(CORE / "chat.py", "FURINA_TERMUX_126_FINAL_BEHAVIOR_KERNEL", r'''
# FURINA_TERMUX_126_FINAL_BEHAVIOR_KERNEL
from .chat_v126 import install_chat_v126
install_chat_v126(globals())
''')
append_once(CORE / "tui.py", "FURINA_TERMUX_126_ROLEPLAY_CUSTOM_TRAITS_UI", r'''
# FURINA_TERMUX_126_ROLEPLAY_CUSTOM_TRAITS_UI
from .tui_v126 import install_tui_v126
install_tui_v126(globals())
''')

# Training Room candidates obey the same final personality and RolePlay
# settings as normal chat while their neutral test prompts remain isolated.
replace_once(
    CORE / "training_v125.py",
    '        name, identity, learned = training_context(self.state_path)\n        negative = negative_contract(state, self.category_id, dimension)\n',
    '        name, identity, learned = training_context(self.state_path)\n'
    '        from .hub_settings import load_hub_settings, personalization_prompt\n'
    '        training_settings = load_hub_settings()\n'
    '        training_personality = personalization_prompt(training_settings, str(record.get("prompt") or ""), {"partner_mode": bool(training_settings.get("partner_mode")), "roleplay_mode": bool(training_settings.get("roleplay_mode"))})\n'
    '        negative = negative_contract(state, self.category_id, dimension)\n',
    "Training Room personality context",
)
replace_once(
    CORE / "training_v125.py",
    '            f"{identity}\\nKontrak kualitas materi: {category_contract(self.category_id)}. "\n',
    '            f"{identity}\\n{training_personality}\\nKontrak kualitas materi: {category_contract(self.category_id)}. "\n',
    "Training Room final behavior contract",
)

print("FURINA_TERMUX_126_BEHAVIOR_CONTINUITY_OK")
