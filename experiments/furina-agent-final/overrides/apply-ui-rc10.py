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

    text = version.read_text(encoding="utf-8")
    old = 'VERSION = "1.0.0-rc9"'
    new = 'VERSION = "1.0.0-rc10"'
    if new not in text:
        if text.count(old) != 1:
            raise SystemExit("RC10 version marker not found")
        version.write_text(text.replace(old, new, 1), encoding="utf-8")

    rendered = tui.read_text(encoding="utf-8")
    required = [
        'def _gum() -> str | None:',
        '["Chat", "Memory", "Provider", "Settings", "System", "Update", "Exit"]',
        'Furina perlu memakai layar untuk tugas ini.',
        'console = Console(highlight=False)',
        'due_prospectives',
    ]
    missing = [item for item in required if item not in rendered]
    if missing:
        raise SystemExit("RC10 modern TUI incomplete: " + ", ".join(missing))
    if 'VERSION = "1.0.0-rc10"' not in version.read_text(encoding="utf-8"):
        raise SystemExit("RC10 version bump failed")
    print("Furina RC10 compact Termux UI transform: OK")


if __name__ == "__main__":
    main()
