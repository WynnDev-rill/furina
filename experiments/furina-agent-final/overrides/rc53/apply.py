#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC53 marker mismatch: {label} ({count})")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <termux-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    chat_path = core / "chat.py"
    mind_path = core / "mind_v2.py"
    version_path = core / "version.py"
    state_path = core / "companion_state_v2.py"
    module_source = Path(__file__).with_name("companion_state_v2.py")
    for path in (chat_path, mind_path, version_path, module_source):
        if not path.is_file():
            raise SystemExit(f"RC53 source missing: {path}")

    state_path.write_bytes(module_source.read_bytes())

    chat = chat_path.read_text(encoding="utf-8")
    if "from .companion_state_v2 import CompanionStateV2" not in chat:
        anchor = "from .config import Config\n"
        if anchor not in chat:
            raise SystemExit("RC53 chat import anchor missing")
        chat = chat.replace(anchor, anchor + "from .companion_state_v2 import CompanionStateV2\n", 1)

    if "from .mind_v2 import FurinaMind" not in chat:
        anchor = "from .memory import MemoryStore, extract_explicit_memories\n"
        if anchor not in chat:
            raise SystemExit("RC53 FurinaMind import anchor missing")
        chat = chat.replace(anchor, anchor + "from .mind_v2 import FurinaMind\n", 1)

    init_anchor = "        self._background_lock = threading.Lock()\n"
    if init_anchor not in chat:
        raise SystemExit("RC53 chat init anchor missing")
    if "self.companion_state = CompanionStateV2(store)" not in chat:
        chat = chat.replace(
            init_anchor,
            init_anchor + "        self.companion_state = CompanionStateV2(store)\n",
            1,
        )
    if "self.mind = FurinaMind(store)" not in chat:
        state_anchor = "        self.companion_state = CompanionStateV2(store)\n"
        if state_anchor in chat:
            chat = chat.replace(state_anchor, state_anchor + "        self.mind = FurinaMind(store)\n", 1)
        else:
            chat = chat.replace(init_anchor, init_anchor + "        self.mind = FurinaMind(store)\n", 1)

    if "LIVING COMPANION STATE:" not in chat:
        anchor = (
            '            + "\\n\\nRELATIONSHIP / INTERNAL CONTEXT:\\n"\n'
            '            + self._relationship_context()\n'
        )
        if anchor not in chat:
            raise SystemExit("RC53 context injection anchor missing")
        living = (
            '            + "\\n\\nLIVING COMPANION STATE:\\n"\n'
            '            + self.companion_state.context()\n'
        )
        if "self.mind.context(" not in chat:
            living += (
                '            + "\\n\\nLEARNED SELF / EXPERIENCE:\\n"\n'
                '            + self.mind.current_context()\n'
                '            + "\\n"\n'
                '            + self.mind.context(8)\n'
            )
        chat = chat.replace(anchor, anchor + living, 1)

    profile_anchor = "        profile = choose_profile(user_text, self.store)\n"
    if profile_anchor not in chat:
        raise SystemExit("RC53 respond pre-state anchor missing")
    before = ""
    if "self.companion_state.before_user(user_text)" not in chat:
        before += "        self.companion_state.before_user(user_text)\n"
    if "self.mind.observe_user_feedback(user_text)" not in chat:
        before += "        self.mind.observe_user_feedback(user_text)\n"
    if before:
        chat = chat.replace(profile_anchor, before + profile_anchor, 1)

    if "self.companion_state.after_turn(user_text, answer)" not in chat:
        anchor = '        self.store.add_message("assistant", answer)\n'
        if anchor not in chat:
            raise SystemExit("RC53 respond post-state anchor missing")
        chat = chat.replace(anchor, anchor + "        self.companion_state.after_turn(user_text, answer)\n", 1)

    if "self.companion_state.maintenance()" not in chat:
        anchor = "        try:\n            self._consolidate(user_text, answer)\n"
        if anchor not in chat:
            raise SystemExit("RC53 background maintenance anchor missing")
        chat = chat.replace(
            anchor,
            "        try:\n            self.companion_state.maintenance()\n            self._consolidate(user_text, answer)\n",
            1,
        )

    chat_path.write_text(chat, encoding="utf-8")
    version = version_path.read_text(encoding="utf-8")
    version = replace_once(version, 'VERSION = "1.0.0-rc52"', 'VERSION = "1.0.0-rc53"', "Core version")
    version_path.write_text(version, encoding="utf-8")

    for path in (state_path, chat_path, mind_path, version_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    final = chat_path.read_text(encoding="utf-8")
    required = (
        "CompanionStateV2", "FurinaMind", "LIVING COMPANION STATE:",
        "self.companion_state.before_user(user_text)",
        "self.mind.observe_user_feedback(user_text)",
        "self.companion_state.after_turn(user_text, answer)",
        "self.companion_state.maintenance()",
    )
    missing = [item for item in required if item not in final]
    if missing:
        raise SystemExit("RC53 companion integration incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc53"' not in version_path.read_text(encoding="utf-8"):
        raise SystemExit("RC53 version missing")

    namespace = {}
    exec(state_path.read_text(encoding="utf-8"), namespace)
    Engine = namespace["CompanionStateV2"]

    class FakeStore:
        def __init__(self): self.data = {}
        def get_state(self, key, default=None): return self.data.get(key, default)
        def set_state(self, key, value): self.data[key] = value
        def relationship_state(self):
            return {"trust": 0.62, "closeness": 0.58, "friction": 0.05, "playfulness": 0.52}

    fake = FakeStore()
    engine = Engine(fake)
    engine.before_user("Makasih, yang tadi pas. Aku kangen ngobrol begini.", now=100000.0)
    engine.after_turn("tes", "baik", now=100010.0)
    engine.maintenance(now=103610.0)
    context = engine.context(now=103611.0)
    if "BEHAVIOR CONTRACT:" not in context or "STATE COMPANION PERSISTEN" not in context:
        raise SystemExit("RC53 companion state smoke test failed")

    print("Furina Core RC53 persistent companion state + learned-self integration: OK")


if __name__ == "__main__":
    main()
