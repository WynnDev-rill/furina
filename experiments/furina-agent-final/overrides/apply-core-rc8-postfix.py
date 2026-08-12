#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc8-postfix.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    chat = root / "core/furina_agent/chat.py"
    if not chat.is_file():
        raise SystemExit("missing RC8 generated chat source")

    text = chat.read_text(encoding="utf-8")
    broken = '        return "\n".join(lines)'
    fixed = r'        return "\n".join(lines)'
    if broken in text:
        text = text.replace(broken, fixed, 1)
    if fixed not in text:
        raise SystemExit("RC8 prospective-context newline marker not found")
    chat.write_text(text, encoding="utf-8")
    print("Furina RC8 generated-source postfix: OK")


if __name__ == "__main__":
    main()
