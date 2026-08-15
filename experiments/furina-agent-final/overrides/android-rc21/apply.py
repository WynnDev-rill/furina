#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys


def replace_once(text, old, new, label):
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC21 marker mismatch: {label}")
    return text.replace(old, new, 1)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = Path(sys.argv[1]).resolve()
    templates = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent
    app = root / "bridge/app"
    main_activity = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    gradle = app / "build.gradle"
    asset = app / "src/main/assets/furinahub/index.html"
    for path in (main_activity, gradle, asset):
        if not path.is_file():
            raise SystemExit(f"RC21 source missing: {path}")
    text = gradle.read_text(encoding="utf-8")
    text = replace_once(text, "versionCode 10020", "versionCode 10021", "versionCode")
    text = replace_once(text, "versionName '1.0.0-rc20'", "versionName '1.0.0-rc21'", "versionName")
    gradle.write_text(text, encoding="utf-8")
    shutil.copyfile(templates / "MainActivity.java", main_activity)
    shutil.copyfile(templates / "hub_shell.html", asset)
    checks = {
        main_activity: ("pickAttachment()", "REQ_PICK_ATTACHMENT", "onAttachmentPicked", "setAllowFileAccess(false)"),
        asset: ("statuschip chat-hidden", "openMessageMenu", "probeDeviceMode", "OpenConnector", "refreshSharedSettings"),
        gradle: ("versionCode 10021", "versionName '1.0.0-rc21'"),
    }
    for path, markers in checks.items():
        body = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in body]
        if missing:
            raise SystemExit(f"RC21 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_ANDROID_RC21_OK")


if __name__ == "__main__":
    main()
