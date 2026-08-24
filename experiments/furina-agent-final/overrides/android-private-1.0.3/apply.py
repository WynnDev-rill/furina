#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
APP = ROOT / "bridge/app"
BUILD = APP / "build.gradle"
MAIN = APP / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
HTML = APP / "src/main/assets/furinahub/index.html"


def one(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected one match, got {text.count(old)}")
    return text.replace(old, new, 1)

build = BUILD.read_text(encoding="utf-8")
build = one(build, "versionCode 10060", "versionCode 10061", "version code")
build = one(build, "versionName '1.0.2'", "versionName '1.0.3'", "version name")
BUILD.write_text(build, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
main = one(main, 'EXPECTED_CORE_VERSION = "1.0.2"', 'EXPECTED_CORE_VERSION = "1.0.3"', "expected core")
old_bundle = 'furina-2026.08.24-private-1.0.2'
new_bundle = 'furina-2026.08.24-private-1.0.3'
count = main.count(old_bundle)
if count not in {1, 2}:
    raise SystemExit(f"bundle id: expected one or two references, got {count}")
main = main.replace(old_bundle, new_bundle)
MAIN.write_text(main, encoding="utf-8")

# Keep the model/provider UI unchanged; only make the fast-path behavior clear.
page = HTML.read_text(encoding="utf-8")
page = page.replace(
    "Furina menyiapkannya di background agar chat pertama lebih cepat.",
    "Furina menyiapkannya di background dan memprioritaskan chat agar respons lokal terasa lebih cepat.",
)
HTML.write_text(page, encoding="utf-8")

print("FURINAHUB_PRIVATE_1_0_3_LOCAL_FAST_UI_OK")
