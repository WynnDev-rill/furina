#!/usr/bin/env python3
from pathlib import Path
import base64
import shutil
import sys


def replace_once(text, old, new, label):
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC24 marker mismatch: {label}")
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
            raise SystemExit(f"RC24 source missing: {path}")
    text = gradle.read_text(encoding="utf-8")
    text = replace_once(text, "versionCode 10023", "versionCode 10024", "versionCode")
    text = replace_once(text, "versionName '1.0.0-rc23'", "versionName '1.0.0-rc24'", "versionName")
    gradle.write_text(text, encoding="utf-8")
    shutil.copyfile(templates / "MainActivity.java", main_activity)
    html = (templates / "hub_shell.html").read_text(encoding="utf-8")
    for marker, name in (
        ("__ICON_CAMERA__", "camera.svg"), ("__ICON_IMAGE__", "image.svg"),
        ("__ICON_FILE_TEXT__", "file-text.svg"), ("__ICON_PLUG__", "plug.svg"),
    ):
        encoded = base64.b64encode((templates / name).read_bytes()).decode("ascii")
        html = html.replace(marker, "data:image/svg+xml;base64," + encoded)
    if "__ICON_" in html:
        raise SystemExit("RC24 icon asset belum terikat")
    asset.write_text(html, encoding="utf-8")
    checks = {
        main_activity: ("pickImage", "takePhoto", "saveImage", "REQ_SAVE_IMAGE", "onMediaPicked", "setAllowFileAccess(false)"),
        asset: ('id="plusMenu" class="sheet compact"', "messageImage", "Hal yang belum selesai", "/api/models/status", "providerTestResult"),
        gradle: ("versionCode 10024", "versionName '1.0.0-rc24'"),
    }
    for path, markers in checks.items():
        body = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in body]
        if missing:
            raise SystemExit(f"RC24 marker hilang di {path.name}: {missing}")
    print("FURINAHUB_ANDROID_RC24_OK")


if __name__ == "__main__":
    main()
