#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def normalize_signer(value: object) -> str:
    signer = re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()
    if len(signer) != 64 or not re.fullmatch(r"[0-9a-f]{64}", signer):
        raise ValueError("signer_sha256 must contain exactly 64 hexadecimal digits")
    return signer


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <bridge.json>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        print(normalize_signer(payload.get("signer_sha256")))
    except Exception as exc:
        print(f"invalid bridge signer metadata: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
