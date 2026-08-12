#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc6-postfix.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    chat = root / "core/furina_agent/chat.py"
    agent = root / "core/furina_agent/agent.py"
    if not chat.is_file() or not agent.is_file():
        raise SystemExit("missing RC6 generated core source")

    text = chat.read_text(encoding="utf-8")
    broken = '        return "\n".join(lines) or "(tidak ada device context baru)"'
    fixed = r'        return "\n".join(lines) or "(tidak ada device context baru)"'
    if fixed not in text:
        if broken not in text:
            raise SystemExit("RC6 device-context newline marker not found")
        text = text.replace(broken, fixed, 1)
        chat.write_text(text, encoding="utf-8")

    agent_text = agent.read_text(encoding="utf-8")
    old = '''    @staticmethod
    def _history_action_succeeded(item: dict) -> bool:
        result = item.get("result")
        if result in {None, "rejected_by_user", "failed_action"}:
            return False
        return bool(result.get("ok")) if isinstance(result, dict) else True
'''
    new = '''    @staticmethod
    def _history_action_succeeded(item: dict) -> bool:
        result = item.get("result")
        if result is None:
            return False
        if isinstance(result, str) and result in {"rejected_by_user", "failed_action", "premature_finish", "blocked_high_risk"}:
            return False
        return bool(result.get("ok")) if isinstance(result, dict) else True
'''
    if new not in agent_text:
        if old not in agent_text:
            raise SystemExit("RC6 action success helper marker not found")
        agent.write_text(agent_text.replace(old, new, 1), encoding="utf-8")

    print("Furina RC6 generated-source postfix: OK")


if __name__ == "__main__":
    main()
