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
    if not version.is_file():
        raise SystemExit(f"RC38 source missing: {version}")
    current = version.read_text(encoding="utf-8")
    if 'VERSION = "1.0.0-rc38"' in current:
        print("FurinaHub Core RC38 already applied")
        return
    if 'VERSION = "1.0.0-rc37"' not in current:
        raise SystemExit("RC38 hanya dapat diterapkan dari Core RC37")

    for name in ("hub.py", "direct_control.py"):
        source = templates / name
        if not source.is_file():
            raise SystemExit(f"RC38 template hilang: {source}")
        shutil.copyfile(source, core / name)

    version.write_text(current.replace('VERSION = "1.0.0-rc37"', 'VERSION = "1.0.0-rc38"', 1), encoding="utf-8")
    for cache in sorted(core.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache, ignore_errors=True)
    for path in (core / "hub_settings.py", core / "hub.py", core / "direct_control.py", version):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    markers = {
        core / "hub.py": (
            '"bridge_target": "1.0.0-rc22"', "/api/device/probe", "/api/messages/clear",
            "/api/connectors/execute", "test_provider", "requested_mode", "effective_mode",
            "_update_failure_detail", "prepare_\" + mode", "rish di Termux tidak diperlukan",
        ),
        core / "hub_settings.py": (
            "SETTINGS_STATE_KEY", "SCHEMA_VERSION = 2", "device_access", "allow_write_actions",
        ),
        core / "direct_control.py": ("effective_device_mode", "load_hub_settings"),
    }
    for path, required in markers.items():
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in required if marker not in text]
        if missing:
            raise SystemExit(f"RC38 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_CORE_RC38_OK")


if __name__ == "__main__":
    main()
