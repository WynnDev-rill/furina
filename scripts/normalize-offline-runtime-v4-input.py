#!/usr/bin/env python3
"""Normalize one known post-stability llama.cpp anchor before the v4 adaptive patch.

The stability policy intentionally shrinks n_ubatch to 64/128. The adaptive v4 policy adds
Flash Attention AUTO immediately after that setting and uses explanatory comments as a
fail-closed anchor. Keep the normalization isolated so both policies remain independently
auditable.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: normalize-offline-runtime-v4-input.py <ai_chat.cpp>")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    old = "    ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128;\n"
    new = (
        "    // Physical micro-batch size changes scratch memory and prompt throughput,\n"
        "    // not model quality. Use the smaller shape only under RAM pressure.\n"
        "    ctx_params.n_ubatch = g_low_memory_mode ? 64 : 128;\n"
    )
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"v4 n_ubatch normalization: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
