from __future__ import annotations

from rich.console import Group
from rich.markdown import Markdown as RichMarkdown
from rich.table import Table
from rich.text import Text


def _body_renderable(body: str):
    lines = str(body or " ").splitlines()
    blocks, spoken = [], []

    def flush() -> None:
        text = "\n".join(spoken).strip()
        if text: blocks.append(RichMarkdown(text, hyperlinks=False, code_theme="monokai"))
        spoken.clear()

    for line in lines:
        if line.startswith("> "):
            flush()
            if line[2:].strip(): blocks.append(Text("  " + line[2:].strip(), style="italic #60a5fa"))
        else:
            spoken.append(line)
    flush()
    return Group(*blocks) if blocks else Text(" ")


def install_surface_v130(ns: dict) -> None:
    def message_renderable(name: str, body: str, *, assistant: bool):
        table = Table.grid(padding=(0, 1))
        table.add_column(no_wrap=True)
        table.add_column(ratio=1, overflow="fold")
        # Restore the original turquoise label for both sides. Blue is reserved for private asides.
        label = Text(f"[{name}] :", style="bold bright_cyan")
        table.add_row(label, _body_renderable(body) if assistant else Text(str(body or " ")))
        return table

    ns["_message_renderable"] = message_renderable
