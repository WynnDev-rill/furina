#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

BUNDLE_ID = "furina-2026.08.23-private-1.0.0"


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"final Android marker missing: {label}")
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
    page_path = app / "src/main/assets/furinahub/index.html"
    hub_path = root / "core/furina_agent/hub.py"
    for path in (gradle_path, main_path, runtime_path, page_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"final Android source missing: {path}")

    build = gradle_path.read_text(encoding="utf-8")
    build = once(build, "versionCode 10057", "versionCode 10058", "version code")
    build = once(build, "versionName '1.0.0-rc57'", "versionName '1.0.0'", "version name")

    main = main_path.read_text(encoding="utf-8")
    main = main.replace("furina-2026.08.23-rc69-rc57", BUNDLE_ID)
    main = main.replace('EXPECTED_CORE_VERSION = "1.0.0-rc69"', 'EXPECTED_CORE_VERSION = "1.0.0"')
    runtime = runtime_path.read_text(encoding="utf-8").replace("furina-2026.08.23-rc69-rc57", BUNDLE_ID)

    hub = hub_path.read_text(encoding="utf-8")
    hub, count = re.subn(r'"bridge_target"\s*:\s*"1\.0\.0-rc57"', '"bridge_target": "1.0.0"', hub)
    if count not in (1, 2):
        raise SystemExit(f"final bridge target mismatch: {count}")

    page = page_path.read_text(encoding="utf-8")
    page = once(page, "connection.connected?'Core aktif'", "connection.connected?'Siap'", "connection status copy")
    page = page.replace(
        '<section id="relationship" class="view hidden" aria-hidden="true"><div class="sectionhead"><h1>Kita</h1><div class="sub">Ruang untuk hubungan kalian sebagai pasangan—tanpa skor, streak, atau mode pertemanan.</div></div>',
        '<section id="relationship" class="view hidden" aria-hidden="true"><div class="sectionhead"><h1>Kedekatan</h1><div class="sub">Preferensi hubungan internal.</div></div>',
    )

    gradle_path.write_text(build, encoding="utf-8")
    main_path.write_text(main, encoding="utf-8")
    runtime_path.write_text(runtime, encoding="utf-8")
    page_path.write_text(page, encoding="utf-8")
    hub_path.write_text(hub, encoding="utf-8")

    combined = "\n".join((build, main, runtime, page, hub))
    required = (
        "versionCode 10058", "versionName '1.0.0'", BUNDLE_ID,
        'EXPECTED_CORE_VERSION = "1.0.0"', '"bridge_target": "1.0.0"',
        "connection.connected?'Siap'", 'id="relationship"', 'aria-hidden="true"',
    )
    missing = [item for item in required if item not in combined]
    if missing:
        raise SystemExit(f"final Android integration incomplete: {missing}")
    if 'data-view="relationship"' in page or "Core aktif" in page:
        raise SystemExit("final Android still exposes obsolete primary/status copy")
    print("FURINAHUB_PRIVATE_FINAL_OK")


if __name__ == "__main__":
    main()
