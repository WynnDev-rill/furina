#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC68 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "core" / "furina_agent"
    version = core / "version.py"
    tui_path = core / "tui.py"
    if not version.is_file() or not tui_path.is_file():
        raise SystemExit("RC68 source incomplete")

    version.write_text(
        once(
            version.read_text(encoding="utf-8"),
            'VERSION = "1.0.0-rc67"',
            'VERSION = "1.0.0-rc68"',
            "RC67 version",
        ),
        encoding="utf-8",
    )

    tui = tui_path.read_text(encoding="utf-8")
    tui = once(
        tui,
        'choice = _choose("", ["Chat", "Kita", "Memory", "Provider & Model", "Pengaturan", "System", "Backup", "Update & Recovery", "Exit"], height=11)',
        'choice = _choose("", ["Chat", "Memory", "Provider & Model", "Pengaturan", "System", "Backup", "Update & Recovery", "Exit"], height=10)',
        "top-level Kita menu",
    )
    tui = once(
        tui,
        '        elif choice == "Kita": _lite_relationship(console)\n',
        "",
        "Kita dispatch",
    )
    tui_path.write_text(tui, encoding="utf-8")

    for path in (version, tui_path):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    menu_start = tui.rfind('choice = _choose("", ["Chat"')
    menu_end = tui.find("\n", menu_start)
    menu_line = tui[menu_start:menu_end] if menu_start >= 0 else ""
    if not menu_line or '"Kita"' in menu_line or 'choice == "Kita"' in tui:
        raise SystemExit("RC68 still exposes Kita as a separate primary menu")
    relationship = core / "relationship_v4.py"
    if not relationship.is_file() or "partner" not in relationship.read_text(encoding="utf-8"):
        raise SystemExit("RC68 relationship core was removed unexpectedly")
    print("FURINA_RC68_SINGLE_COMPANION_SURFACE_OK")


if __name__ == "__main__":
    main()
