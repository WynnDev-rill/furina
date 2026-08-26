#!/usr/bin/env python3
"""Build updater 1.4.2 for Furina Termux 1.1.19."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "runtime-private-1.1.9" / "build_client.py"
spec = importlib.util.spec_from_file_location("furina_119_builder", BASE)
if spec is None or spec.loader is None:
    raise SystemExit("base builder unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def build(base: Path, output: Path) -> None:
    module.build(base, output)
    text = output.read_text(encoding="utf-8")
    if 'CLIENT_VERSION = "1.4.1"' not in text:
        raise SystemExit("expected updater 1.4.1")
    text = text.replace('CLIENT_VERSION = "1.4.1"', 'CLIENT_VERSION = "1.4.2"', 1)
    text += "\n# FURINA_TERMUX_119_UPDATER\n"
    compile(text, str(output), "exec")
    output.write_text(text, encoding="utf-8")
    output.chmod(0o755)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} BASE OUTPUT", file=sys.stderr)
        return 2
    build(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    print("FURINA_TERMUX_119_UPDATER_BUILD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
