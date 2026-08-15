#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import shutil
import sys


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = pathlib.Path(sys.argv[1]).resolve()
    templates = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent
    core = root / "core/furina_agent"
    version = core / "version.py"
    current = version.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc40"' in current:
        print("FurinaHub Core RC40 already applied")
        return
    if 'VERSION = "1.0.0-rc39"' not in current:
        raise SystemExit("RC40 hanya dapat diterapkan dari Core RC39")
    for name in ("hub.py", "memory.py"):
        source = templates / name
        if not source.is_file():
            raise SystemExit(f"RC40 template hilang: {source}")
        shutil.copyfile(source, core / name)
    version.write_text(current.replace('VERSION = "1.0.0-rc39"', 'VERSION = "1.0.0-rc40"', 1), encoding="utf-8")
    for cache in sorted(core.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache, ignore_errors=True)
    for path in (core / "hub.py", core / "memory.py", version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    markers = {
        core / "hub.py": ('"bridge_target": "1.0.0-rc24"', "attachment_json", "/api/media/", "/api/models", "percent=percent"),
        core / "memory.py": ("attachment_json", "attachment: dict | None"),
    }
    for path, required in markers.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in required if marker not in text]
        if missing:
            raise SystemExit(f"RC40 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_CORE_RC40_OK")


if __name__ == "__main__":
    main()
