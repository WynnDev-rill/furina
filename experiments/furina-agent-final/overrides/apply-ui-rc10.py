#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import shutil
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-rc10.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    core = root / "core/furina_agent"
    staged = core / "tui_rc10.py"
    tui = core / "tui.py"
    version = core / "version.py"
    for path in (staged, tui, version):
        if not path.is_file():
            raise SystemExit(f"missing RC10 UI source: {path}")

    # Previous transforms intentionally keep operating on the legacy Rich TUI.
    # RC10 swaps the final surface only after every older migration is complete,
    # so historical transforms remain deterministic and update-safe.
    shutil.copyfile(staged, tui)
    staged.unlink()

    text = tui.read_text(encoding="utf-8")
    # Termux currently ships Gum 0.17. In single-select choose, Gum hides the
    # selected/unselected prefixes and uses --cursor for the active row marker.
    text = text.replace('"--cursor-prefix", "› ",', '"--cursor", "› ",', 1)

    old = "store.due_prospectives(time.time() + 365 * 86400, 30)"
    new = "store.pending_prospectives(30)"
    if old in text:
        text = text.replace(old, new, 1)
    show_old = '''    for item in due:
        console.print(f"[yellow]Reminder[/]  {item.get('text', '')}")
'''
    show_new = '''    for item in due:
        console.print(f"[yellow]Reminder[/]  {item.get('text', '')}")
        try:
            store.mark_prospective_fired(int(item["id"]))
        except Exception:
            pass
'''
    if show_old in text:
        text = text.replace(show_old, show_new, 1)
    tui.write_text(text, encoding="utf-8")

    vtext = version.read_text(encoding="utf-8")
    old_version = 'VERSION = "1.0.0-rc9"'
    new_version = 'VERSION = "1.0.0-rc10"'
    if new_version not in vtext:
        if vtext.count(old_version) != 1:
            raise SystemExit("RC10 version marker not found")
        version.write_text(vtext.replace(old_version, new_version, 1), encoding="utf-8")

    rendered = tui.read_text(encoding="utf-8")
    required = [
        'def _gum() -> str | None:',
        '["Chat", "Memory", "Provider", "Settings", "System", "Update", "Exit"]',
        '"--cursor", "› "',
        'Furina perlu memakai layar untuk tugas ini.',
        'console = Console(highlight=False)',
        'pending_prospectives(30)',
        'store.mark_prospective_fired',
    ]
    missing = [item for item in required if item not in rendered]
    if missing:
        raise SystemExit("RC10 modern TUI incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc10"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC10 version bump failed")
    print("Furina RC10 compact Termux UI transform: OK")


if __name__ == "__main__":
    main()
