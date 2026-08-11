#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix-offline-backend-cpp-includes.py <ai_chat.cpp>")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    old = "#include <cmath>\n#include <cstdint>\n"
    new = "#include <cmath>\n#include <algorithm>\n#include <cctype>\n#include <cstdint>\n"
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"backend C++ includes: expected one anchor, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
