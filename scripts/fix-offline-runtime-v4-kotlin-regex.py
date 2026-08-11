#!/usr/bin/env python3
"""Fix the generated Kotlin benchmark regex after the v4 runtime patch.

Python string escaping intentionally stays out of the large deterministic patch: the emitted
Kotlin line contains single backslashes (invalid escapes). Replace it with a Kotlin raw string.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix-offline-runtime-v4-kotlin-regex.py <InferenceEngineImpl.kt>")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    old = '        Regex("\\|\\s+(pp|tg)\\s+\\d+\\s+\\|\\s+([0-9.]+)").findAll(raw).forEach { match ->'
    new = '        Regex("""\\|\\s+(pp|tg)\\s+\\d+\\s+\\|\\s+([0-9.]+)""").findAll(raw).forEach { match ->'
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"v4 Kotlin benchmark regex: expected exactly one generated line, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
