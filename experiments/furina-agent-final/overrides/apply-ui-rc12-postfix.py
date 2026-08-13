#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-rc12-postfix.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    tui = root / "core/furina_agent/tui.py"
    chat = root / "core/furina_agent/chat_surface.py"
    if not tui.is_file() or not chat.is_file():
        raise SystemExit("RC12 postfix source missing")

    text = tui.read_text(encoding="utf-8")
    duplicate = "def _main_menu(console) -> str:\ndef _main_menu(console) -> str:\n"
    if duplicate in text:
        text = text.replace(duplicate, "def _main_menu(console) -> str:\n", 1)
    elif text.count("def _main_menu(console) -> str:") != 1:
        raise SystemExit("RC12 main menu marker is not deterministic")

    # Fail while the new Core is still staged. Never allow invalid Python to
    # replace the currently working installation.
    compile(text, str(tui), "exec")
    chat_text = chat.read_text(encoding="utf-8")
    compile(chat_text, str(chat), "exec")

    if "ChatApp().run(mouse=False)" not in chat_text:
        raise SystemExit("RC12 mobile chat interaction patch missing")
    if "class _ThemedConsole:" not in text:
        raise SystemExit("RC12 unified theme missing")

    tui.write_text(text, encoding="utf-8")
    print("Furina RC12 UI postfix + syntax guard: OK")


if __name__ == "__main__":
    main()
