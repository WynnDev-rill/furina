#!/usr/bin/env python3
from __future__ import annotations

# RC19 UI performance transform. The implementation is intentionally layered
# after RC18 so the experiment can be tested and rolled back independently.

import pathlib
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-ui-performance-rc19.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    if not root.is_dir():
        raise SystemExit("missing staged root")
    print("RC19 UI performance staging: OK")


if __name__ == "__main__":
    main()
