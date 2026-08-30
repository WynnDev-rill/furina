from __future__ import annotations

from rich.console import Group
from rich.markdown import Markdown as RichMarkdown
from rich.table import Table
from rich.text import Text


def _body_renderable(body: str):
    """Render private asides as unlabeled blue lines, not Markdown quote pink."""
    lines = str(body or " ").splitlines()
    blocks = []
    spoken: list[str] = []

    def flush_spoken() -> None:
        text = "\n".join(spoken).strip()
        if text:
            blocks.append(RichMarkdown(text, hyperlinks=False, code_theme="monokai"))
        spoken.clear()

    for line in lines:
        if line.startswith("> "):
            flush_spoken()
            aside = line[2:].strip()
            if aside:
                blocks.append(Text("  " + aside, style="italic #60a5fa"))
        else:
            spoken.append(line)
    flush_spoken()
    return Group(*blocks) if blocks else Text(" ")


def install_surface_v129(ns: dict) -> None:
    clean_name = ns["_clean_name"]

    def message_renderable(name: str, body: str, *, assistant: bool):
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True)
        table.add_column(ratio=1, overflow="fold")
        label = Text(f"[{name}] :", style="bold bright_magenta" if assistant else "bold bright_cyan")
        content = _body_renderable(body) if assistant else Text(str(body or " "))
        table.add_row(label, content)
        return table

    ns["_message_renderable"] = message_renderable
    ns["_clean_name"] = clean_name

