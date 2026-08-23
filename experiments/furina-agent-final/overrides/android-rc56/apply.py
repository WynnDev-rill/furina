#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise SystemExit(f"Android RC56 marker missing: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply.py <furina-root>")
    root = Path(sys.argv[1]).resolve()
    app = root / "bridge" / "app"
    java = app / "src" / "main" / "java" / "com" / "wynndev" / "furinaagentbridge"
    gradle = app / "build.gradle"
    main_path = java / "MainActivity.java"
    runtime_path = java / "BridgeRuntime.java"
    html_path = app / "src" / "main" / "assets" / "furinahub" / "index.html"
    hub_path = root / "core" / "furina_agent" / "hub.py"
    for path in (gradle, main_path, runtime_path, html_path, hub_path):
        if not path.is_file():
            raise SystemExit(f"Android RC56 source missing: {path}")

    build = once(gradle.read_text(encoding="utf-8"), "versionCode 10055", "versionCode 10056", "version code")
    build = once(build, "versionName '1.0.0-rc55'", "versionName '1.0.0-rc56'", "version name")

    main_text = main_path.read_text(encoding="utf-8")
    main_text = main_text.replace("furina-2026.08.22-rc67-rc55", "furina-2026.08.23-rc68-rc56")
    main_text = main_text.replace('EXPECTED_CORE_VERSION = "1.0.0-rc67"', 'EXPECTED_CORE_VERSION = "1.0.0-rc68"')
    if "furina-apk-confirm" not in main_text:
        method = main_text.find("@Override protected void onResume()")
        if method < 0:
            method = main_text.find("@Override\n    protected void onResume()")
        if method < 0:
            raise SystemExit("Android RC56 onResume marker missing")
        resume = main_text.find("super.onResume();", method)
        if resume < 0:
            raise SystemExit("Android RC56 super.onResume marker missing")
        insert_at = resume + len("super.onResume();")
        main_text = (
            main_text[:insert_at]
            + '\n        runFixedTermux("/data/data/com.termux/files/usr/bin/furina-apk-confirm", new String[]{"furina-2026.08.23-rc68-rc56"});'
            + main_text[insert_at:]
        )

    runtime_text = runtime_path.read_text(encoding="utf-8").replace(
        "furina-2026.08.22-rc67-rc55", "furina-2026.08.23-rc68-rc56"
    )

    hub = hub_path.read_text(encoding="utf-8")
    hub = hub.replace('"bridge_target": "1.0.0-rc55"', '"bridge_target": "1.0.0-rc56"')

    page = html_path.read_text(encoding="utf-8")
    page, count = re.subn(
        r'<button class="nav" data-view="relationship"[^>]*>.*?</button>',
        "",
        page,
        count=1,
        flags=re.S,
    )
    if count != 1 and 'data-view="relationship"' in page:
        raise SystemExit(f"Android RC56 relationship nav mismatch: {count}")
    page = once(
        page,
        '<section id="relationship" class="view">',
        '<section id="relationship" class="view hidden" aria-hidden="true">',
        "hidden internal relationship state",
    )

    gradle.write_text(build, encoding="utf-8")
    main_path.write_text(main_text, encoding="utf-8")
    runtime_path.write_text(runtime_text, encoding="utf-8")
    html_path.write_text(page, encoding="utf-8")
    hub_path.write_text(hub, encoding="utf-8")

    combined = "\n".join((build, main_text, runtime_text, hub, page))
    required = (
        "versionCode 10056",
        "versionName '1.0.0-rc56'",
        "furina-2026.08.23-rc68-rc56",
        'EXPECTED_CORE_VERSION = "1.0.0-rc68"',
        "furina-apk-confirm",
        'id="relationship"',
        'aria-hidden="true"',
    )
    missing = [item for item in required if item not in combined]
    if missing:
        raise SystemExit("Android RC56 contract failed: " + ", ".join(missing))
    if 'data-view="relationship"' in page:
        raise SystemExit("Android RC56 still exposes Kita/relationship as primary navigation")
    print("FURINAHUB_ANDROID_RC56_SINGLE_SURFACE_UPDATE_CONFIRM_OK")


if __name__ == "__main__":
    main()
