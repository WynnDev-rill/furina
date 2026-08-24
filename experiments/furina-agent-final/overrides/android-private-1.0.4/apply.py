#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/furina-agent-rc54-validate/termux")
APP = ROOT / "bridge/app"
BUILD = APP / "build.gradle"
MAIN = APP / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"

build = BUILD.read_text(encoding="utf-8")
if build.count("versionCode 10061") != 1 or build.count("versionName '1.0.3'") != 1:
    raise SystemExit("expected FurinaHub 1.0.3/10061 build boundary")
build = build.replace("versionCode 10061", "versionCode 10062", 1)
build = build.replace("versionName '1.0.3'", "versionName '1.0.4'", 1)
BUILD.write_text(build, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
if main.count('EXPECTED_CORE_VERSION = "1.0.3"') != 1:
    raise SystemExit("expected Core 1.0.3 marker")
main = main.replace('EXPECTED_CORE_VERSION = "1.0.3"', 'EXPECTED_CORE_VERSION = "1.0.4"', 1)
main = main.replace("furina-2026.08.24-private-1.0.3", "furina-2026.08.24-private-1.0.4")
main, count = re.subn(
    r'EXPECTED_DEPENDENCY_REVISION = "[^"]+"',
    'EXPECTED_DEPENDENCY_REVISION = "2026.08.24-r44"',
    main,
    count=1,
)
if count != 1:
    raise SystemExit("Android dependency revision marker missing")
MAIN.write_text(main, encoding="utf-8")

print("FURINAHUB_PRIVATE_1_0_4_BOUNDARY_OK")
