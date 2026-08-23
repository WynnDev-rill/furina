#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"RC69 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    version_path = root / "core/furina_agent/version.py"
    if not version_path.is_file():
        raise SystemExit(f"RC69 source missing: {version_path}")

    text = version_path.read_text(encoding="utf-8")
    text = replace_once(text, 'VERSION = "1.0.0-rc68"', 'VERSION = "1.0.0-rc69"', "Core version")
    if 'UPDATE_PROTOCOL = "furina-update/1"' not in text:
        text += '\nUPDATE_PROTOCOL = "furina-update/1"\n'
    version_path.write_text(text, encoding="utf-8")
    compile(text, str(version_path), "exec")

    if 'VERSION = "1.0.0-rc69"' not in text or 'UPDATE_PROTOCOL = "furina-update/1"' not in text:
        raise SystemExit("RC69 update protocol contract failed")
    print("FURINA_RC69_UPDATE_PROTOCOL_BOUNDARY_OK")


if __name__ == "__main__":
    main()
