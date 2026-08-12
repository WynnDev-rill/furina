#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc6-postfix.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    chat = root / "core/furina_agent/chat.py"
    if not chat.is_file():
        raise SystemExit("missing RC6 chat source")
    text = chat.read_text(encoding="utf-8")
    broken = '        return "\n".join(lines) or "(tidak ada device context baru)"'
    fixed = r'        return "\n".join(lines) or "(tidak ada device context baru)"'
    if fixed not in text:
        if broken not in text:
            raise SystemExit("RC6 device-context newline marker not found")
        text = text.replace(broken, fixed, 1)
        chat.write_text(text, encoding="utf-8")
    print("Furina RC6 generated newline escape: OK")


if __name__ == "__main__":
    main()
