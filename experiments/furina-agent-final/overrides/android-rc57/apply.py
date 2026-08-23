#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"Android RC57 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge/app"
    java = app / "src/main/java/com/wynndev/furinaagentbridge"
    gradle_path = app / "build.gradle"
    main_path = java / "MainActivity.java"
    runtime_path = java / "BridgeRuntime.java"
    hub_path = root / "core/furina_agent/hub.py"
    for path in (gradle_path, main_path, runtime_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"Android RC57 source missing: {path}")

    build = gradle_path.read_text(encoding="utf-8")
    build = replace_once(build, "versionCode 10056", "versionCode 10057", "version code")
    build = replace_once(build, "versionName '1.0.0-rc56'", "versionName '1.0.0-rc57'", "version name")

    main = main_path.read_text(encoding="utf-8")
    main = main.replace("furina-2026.08.23-rc68-rc56", "furina-2026.08.23-rc69-rc57")
    main = main.replace('EXPECTED_CORE_VERSION = "1.0.0-rc68"', 'EXPECTED_CORE_VERSION = "1.0.0-rc69"')

    runtime = runtime_path.read_text(encoding="utf-8").replace(
        "furina-2026.08.23-rc68-rc56", "furina-2026.08.23-rc69-rc57"
    )

    hub = hub_path.read_text(encoding="utf-8")
    hub = replace_once(hub, '"bridge_target": "1.0.0-rc56"', '"bridge_target": "1.0.0-rc57"', "bridge target")

    gradle_path.write_text(build, encoding="utf-8")
    main_path.write_text(main, encoding="utf-8")
    runtime_path.write_text(runtime, encoding="utf-8")
    hub_path.write_text(hub, encoding="utf-8")

    combined = "\n".join((build, main, runtime, hub))
    required = (
        "versionCode 10057",
        "versionName '1.0.0-rc57'",
        "furina-2026.08.23-rc69-rc57",
        'EXPECTED_CORE_VERSION = "1.0.0-rc69"',
        '"bridge_target": "1.0.0-rc57"',
        "furina-apk-confirm",
    )
    missing = [item for item in required if item not in combined]
    if missing:
        raise SystemExit("Android RC57 contract failed: " + ", ".join(missing))
    print("FURINAHUB_ANDROID_RC57_UPDATE_PROTOCOL_OK")


if __name__ == "__main__":
    main()
