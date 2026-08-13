#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC10 hotfix marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-rc10-hotfix.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    tui = root / "core/furina_agent/tui.py"
    if not tui.is_file():
        raise SystemExit(f"missing RC10 TUI: {tui}")

    text = tui.read_text(encoding="utf-8")

    # Gum/Bubble Tea renders its interactive surface to stderr while the chosen
    # value is printed to stdout. capture_output=True swallowed stderr, leaving
    # the user staring at a blank terminal with only a cursor.
    text = replace_once(
        text,
        '''def _run_gum(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:\n    return subprocess.run(\n        [_gum(), *args],\n        input=input_text,\n        text=True,\n        capture_output=True,\n        check=False,\n    )\n''',
        '''def _run_gum(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:\n    return subprocess.run(\n        [_gum(), *args],\n        input=input_text,\n        text=True,\n        stdout=subprocess.PIPE,\n        stderr=None,\n        check=False,\n    )\n''',
        "visible Gum stderr",
    )

    # Gum 0.17 hides cursor-prefix for single-select lists; --cursor is the
    # visible active-row marker.
    text = replace_once(
        text,
        '            "--cursor-prefix", "› ",\n',
        '            "--cursor", "› ",\n',
        "Gum 0.17 cursor",
    )

    old_header = '''def _header(console, section: str = "") -> None:\n    cfg, local_ok, bridge, bridge_ok, memory_count, providers = _status_snapshot()\n    route = {"local": "LOCAL", "auto": "AUTO", "online": "ONLINE"}.get(cfg.routing_mode, cfg.routing_mode.upper())\n    title = f"[bold bright_cyan]FURINA[/] [dim]rc{VERSION.rsplit('rc', 1)[-1]}[/]"\n    if section:\n        title += f"  [dim]·[/]  [bold]{section}[/]"\n    console.print(title)\n    console.print(\n        f"{_dot(local_ok)} [dim]local[/]   "\n        f"{_dot(bridge_ok)} [dim]bridge[/]   "\n        f"[bright_cyan]{memory_count}[/] [dim]memory[/]   "\n        f"[bright_magenta]{route}[/]"\n    )\n    console.print("[dim]" + "─" * max(16, min(console.width, 72)) + "[/]")\n'''
    new_header = '''def _display_name() -> str:\n    name = str(load_config().persona_name or "Furina").strip()[:48]\n    return name.replace("[", "").replace("]", "") or "Furina"\n\n\ndef _header(console, section: str = "") -> None:\n    cfg = load_config()\n    route = {"local": "LOCAL", "auto": "AUTO", "online": "ONLINE"}.get(cfg.routing_mode, cfg.routing_mode.upper())\n    title = f"[bold bright_cyan]{_display_name()}[/] [bold]By Wynn[/]"\n    if section:\n        title += f"  [dim]·[/]  [bold]{section}[/]"\n    console.print(title)\n    console.print(f"[dim]Mode[/]  [bright_magenta]{route}[/]")\n    console.print("[dim]" + "─" * max(16, min(console.width, 72)) + "[/]")\n'''
    text = replace_once(text, old_header, new_header, "dynamic compact header")

    text = text.replace('console.print("[bold bright_magenta]Furina[/]")', 'console.print(f"[bold bright_magenta]{_display_name()}[/]")')
    text = text.replace('console.print("[bright_magenta]Furina[/]  Baik. Aku tidak menyentuh layar.\\n")', 'console.print(f"[bright_magenta]{_display_name()}[/]  Baik. Aku tidak menyentuh layar.\\n")')
    text = text.replace('console.print(f"[bold bright_magenta]Furina[/]  {reply}\\n")', 'console.print(f"[bold bright_magenta]{_display_name()}[/]  {reply}\\n")')

    required = [
        "stdout=subprocess.PIPE",
        "stderr=None",
        '"--cursor", "› "',
        "def _display_name() -> str:",
        "By Wynn",
        'console.print(f"[dim]Mode[/]  [bright_magenta]{route}[/]")',
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit("RC10 UI hotfix incomplete: " + ", ".join(missing))
    if "capture_output=True" in text:
        raise SystemExit("RC10 Gum output is still captured")
    if "memory_count" in text[text.index("def _header"):text.index("def _main_menu")]:
        raise SystemExit("RC10 header still exposes memory/bridge/local diagnostics")

    tui.write_text(text, encoding="utf-8")
    print("Furina RC10 UI hotfix: OK")


if __name__ == "__main__":
    main()
