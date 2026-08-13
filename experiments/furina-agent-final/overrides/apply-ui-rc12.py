#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC12 marker mismatch {label}: {text.count(old)}")
    return text.replace(old, new, 1)


def replace_block(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise SystemExit(f"RC12 block marker missing: {label}")
    return text[:start] + replacement + text[end:]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-rc12.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    tui = root / "core/furina_agent/tui.py"
    chat = root / "core/furina_agent/chat_surface.py"
    version = root / "core/furina_agent/version.py"
    for path in (tui, chat, version):
        if not path.is_file():
            raise SystemExit(f"missing RC12 source: {path}")

    # ── Shared Kira-inspired visual language for every Furina Termux surface.
    t = tui.read_text(encoding="utf-8")
    for old, new in (
        ('ACCENT = "212"', 'ACCENT = "#5de4c7"'),
        ('CYAN = "51"', 'CYAN = "#9efce7"'),
        ('MUTED = "245"', 'MUTED = "#3d6b5e"'),
        ('GREEN = "42"', 'GREEN = "#5de4c7"'),
        ('RED = "196"', 'RED = "#e05560"'),
    ):
        t = replace_once(t, old, new, old)

    # Gum gets the same inset and quiet palette as the chat shell.
    t = replace_once(t, '            "--cursor", "› ",\n', '            "--cursor", " › ",\n', "gum cursor inset")
    t = replace_once(t, '            "--selected-prefix", "› ",\n', '            "--selected-prefix", " › ",\n', "gum selected inset")
    t = replace_once(t, '            "--unselected-prefix", "  ",\n', '            "--unselected-prefix", "   ",\n', "gum row inset")

    header = '''def _header(console, section: str = "") -> None:\n    title = f"[bold #9efce7]{_display_name()}[/] [#5de4c7]By Wynn[/]"\n    if section:\n        title += f"  [#1f6e5a]·[/]  [bold]{section}[/]"\n    console.print(title)\n    console.print("[#1f6e5a]" + "─" * max(16, min(console.width - 2, 72)) + "[/]")\n\n\n'''
    t = replace_block(t, "def _header(console, section: str = \"\") -> None:\n", "def _main_menu(console) -> str:\n", header + "def _main_menu(console) -> str:\n", "compact one-row header")

    # Indent Rich-rendered content one cell without touching status APIs.
    class_marker = "def _gum() -> str | None:\n"
    themed_console = '''class _ThemedConsole:\n    def __init__(self, console):\n        self._console = console\n\n    def __getattr__(self, name):\n        return getattr(self._console, name)\n\n    def print(self, *objects, **kwargs):\n        if objects and isinstance(objects[0], str) and objects[0] and not objects[0].startswith("\\n"):\n            objects = (" " + objects[0], *objects[1:])\n        return self._console.print(*objects, **kwargs)\n\n\n'''
    if "class _ThemedConsole:" not in t:
        pos = t.find(class_marker)
        if pos < 0:
            raise SystemExit("RC12 themed console anchor missing")
        t = t[:pos] + themed_console + t[pos:]

    t = replace_once(
        t,
        "    console = Console(highlight=False)\n",
        "    console = _ThemedConsole(Console(highlight=False))\n",
        "themed console activation",
    )
    t = t.replace('"[bright_magenta]Memahami…[/]"', '"[#5de4c7]Memahami…[/]"')
    t = t.replace('"[bright_magenta]Menggunakan layar…[/]"', '"[#5de4c7]Menggunakan layar…[/]"')
    t = t.replace('"[bright_magenta]Menyalakan local model…[/]"', '"[#5de4c7]Menyalakan local model…[/]"')
    tui.write_text(t, encoding="utf-8")

    # ── Conversation surface: mobile-first, compact, keyboard-friendly.
    c = chat.read_text(encoding="utf-8")
    c = c.replace('style="bold bright_magenta" if assistant else "bold bright_cyan"', 'style="bold #5de4c7" if assistant else "bold #e8b86d"')

    css_start = c.find('        CSS = """\n        Screen {')
    css_end = c.find('        """\n        BINDINGS = [', css_start)
    if css_start < 0 or css_end < 0:
        raise SystemExit("RC12 chat CSS markers missing")
    css = '''        CSS = """\n        Screen {\n            background: #000000;\n            color: #e7eee9;\n        }\n\n        #header {\n            height: 1;\n            padding: 0 2;\n            background: #040d0b;\n            color: #e7eee9;\n        }\n\n        #messages {\n            height: 1fr;\n            padding: 1 2 0 2;\n            background: #080f0d;\n            scrollbar-size: 1 1;\n            scrollbar-color: #1f6e5a;\n            scrollbar-color-hover: #5de4c7;\n            scrollbar-background: #080f0d;\n        }\n\n        .message {\n            width: 100%;\n            height: auto;\n            margin: 0 0 1 0;\n            background: #080f0d;\n            color: #e7eee9;\n        }\n\n        #status {\n            height: 1;\n            padding: 0 2;\n            color: #3d6b5e;\n            background: #080f0d;\n        }\n\n        #composer {\n            height: 2;\n            padding: 0 1;\n            margin: 0 1;\n            border: none;\n            border-top: solid #1a2e2a;\n            background: #080f0d;\n            color: #e8b86d;\n        }\n\n        #composer:focus {\n            border: none;\n            border-top: solid #1f6e5a;\n        }\n        """\n'''
    c = c[:css_start] + css + c[css_end + len('        """\n'):]

    old_compose = '''        def compose(self) -> ComposeResult:\n            yield Static(\n                Text.assemble(\n                    (f"{self.persona_name} By Wynn", "bold bright_cyan"),\n                    ("  ·  Chat\\n", "bold"),\n                    ("/back untuk kembali", "dim"),\n                ),\n                id="header",\n            )\n            yield VerticalScroll(id="messages")\n            yield Static("", id="status")\n            yield Input(placeholder="Tulis pesan…", id="composer")\n\n        def on_mount(self) -> None:\n            self.query_one("#composer", Input).focus()\n'''
    new_compose = '''        def compose(self) -> ComposeResult:\n            yield Static(\n                Text.assemble(\n                    (f"{self.persona_name} By Wynn", "bold #9efce7"),\n                    ("  ·  ", "#1f6e5a"),\n                    ("Chat", "bold"),\n                ),\n                id="header",\n            )\n            yield VerticalScroll(id="messages")\n            yield Static("Esc kembali  ·  /back", id="status")\n            yield Input(placeholder="Tulis pesan…", id="composer")\n\n        def on_mount(self) -> None:\n            self.query_one("#composer", Input).focus()\n'''
    c = replace_once(c, old_compose, new_compose, "chat header and idle hint")

    c = replace_once(
        c,
        '        def _set_status(self, text: str) -> None:\n            self.query_one("#status", Static).update(text)\n',
        '        def _set_status(self, text: str) -> None:\n            self.query_one("#status", Static).update(text or "Esc kembali  ·  /back")\n',
        "idle status restore",
    )
    c = replace_once(c, "    ChatApp().run()\n", "    ChatApp().run(mouse=False)\n", "Termux touch keyboard compatibility")
    chat.write_text(c, encoding="utf-8")

    rendered_tui = tui.read_text(encoding="utf-8")
    rendered_chat = chat.read_text(encoding="utf-8")
    required = [
        (rendered_tui, 'ACCENT = "#5de4c7"'),
        (rendered_tui, "class _ThemedConsole:"),
        (rendered_tui, '[bold #9efce7]{_display_name()}[/]'),
        (rendered_chat, "padding: 1 2 0 2;"),
        (rendered_chat, "Esc kembali  ·  /back"),
        (rendered_chat, "ChatApp().run(mouse=False)"),
        (version.read_text(encoding="utf-8"), 'VERSION = "1.0.0-rc11"'),
    ]
    missing = [needle for haystack, needle in required if needle not in haystack]
    if missing:
        raise SystemExit("RC12 unified TUI incomplete: " + ", ".join(missing))

    print("Furina RC12 unified Termux UI: OK")


if __name__ == "__main__":
    main()
