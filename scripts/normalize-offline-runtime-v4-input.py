#!/usr/bin/env python3
"""Normalize one harmless pinned llama.android diagnostic typo before the v4 patch.

The audited overlay includes an extra ')' inside the init-context error message. Runtime v4
uses the surrounding block as a fail-closed anchor when isolating temporary benchmark contexts.
Normalize only that message; do not touch runtime behavior or n_ubatch comments.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: normalize-offline-runtime-v4-input.py <ai_chat.cpp>")
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    old = 'LOGe("%s: llama_new_context_with_model() returned null)", __func__);'
    new = 'LOGe("%s: llama_new_context_with_model() returned null", __func__);'
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"v4 init-context normalization: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
