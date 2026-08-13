#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"RC15 marker mismatch {label}: {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-core-rc15.py <termux-root>")

    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    chat_surface = core / "chat_surface.py"
    version = core / "version.py"
    if not chat_surface.is_file() or not version.is_file():
        raise SystemExit("missing RC15 source")

    paste_input = r'''from __future__ import annotations

from rich.cells import cell_len
from rich.text import Text
from textual import events
from textual.expand_tabs import expand_tabs_inline
from textual.widgets import Input


class FullPasteInput(Input):
    """Single-row composer that preserves complete bracketed-paste payloads.

    Textual Input intentionally keeps only the first pasted line. Furina needs
    the opposite behavior for chat: the complete payload is kept in ``value``
    while line breaks are rendered as one-cell markers so the compact composer
    remains a single terminal row.
    """

    @staticmethod
    def _normalize_paste(text: str) -> str:
        return str(text or "").replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def _display_text(text: str) -> str:
        # Keep a 1:1 character mapping so cursor indexes remain valid. A newline
        # is one source character and becomes one visible marker in the composer.
        return str(text or "").replace("\r", "↵").replace("\n", "↵")

    @property
    def _value(self) -> Text:
        value = self._display_text(self.value)
        text = Text(value, no_wrap=True, overflow="ignore", end="")
        if self.highlighter is not None:
            text = self.highlighter(text)
        return text

    def _position_to_cell(self, position: int) -> int:
        display = self._display_text(self.value[:position])
        return cell_len(expand_tabs_inline(display, 4))

    def _on_paste(self, event: events.Paste) -> None:
        text = self._normalize_paste(event.text)
        if text:
            selection = self.selection
            if selection.is_empty:
                self.insert_text_at_cursor(text)
            else:
                self.replace(text, *selection)
        event.stop()
'''
    (core / "paste_input.py").write_text(paste_input, encoding="utf-8")

    text = chat_surface.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "        from textual.widgets import Input, Static\n",
        "        from textual.widgets import Input, Static\n        from .paste_input import FullPasteInput\n",
        "paste input import",
    )
    text = replace_once(
        text,
        '            yield Input(placeholder="Tulis pesan…", id="composer", max_length=0)  # RC14: unbounded composer\n',
        '            yield FullPasteInput(placeholder="Tulis pesan…", id="composer", max_length=0)  # RC15: full multiline paste\n',
        "full paste composer",
    )
    chat_surface.write_text(text, encoding="utf-8")

    v = version.read_text(encoding="utf-8")
    v = replace_once(v, 'VERSION = "1.0.0-rc14"', 'VERSION = "1.0.0-rc15"', "core version")
    version.write_text(v, encoding="utf-8")

    for path in (chat_surface, version, core / "paste_input.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    required = [
        (chat_surface, "FullPasteInput"),
        (chat_surface, "RC15: full multiline paste"),
        (core / "paste_input.py", "class FullPasteInput(Input):"),
        (core / "paste_input.py", "self.insert_text_at_cursor(text)"),
        (core / "paste_input.py", 'replace("\\n", "↵")'),
        (version, 'VERSION = "1.0.0-rc15"'),
    ]
    missing = [needle for path, needle in required if needle not in path.read_text(encoding="utf-8")]
    if missing:
        raise SystemExit("RC15 full-paste contract incomplete: " + ", ".join(missing))

    print("Furina RC15 complete multiline paste composer: OK")


if __name__ == "__main__":
    main()
