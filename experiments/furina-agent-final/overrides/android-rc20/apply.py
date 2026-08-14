#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys


def replace_once(text, old, new, label):
    if new in text and old not in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"RC20 marker mismatch: {label}")
    return text.replace(old, new, 1)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: apply.py <termux-root> [template-dir]")
    root = Path(sys.argv[1]).resolve()
    templates = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent
    app = root / "bridge/app"
    manifest = app / "src/main/AndroidManifest.xml"
    main_activity = app / "src/main/java/com/wynndev/furinaagentbridge/MainActivity.java"
    gradle = app / "build.gradle"
    asset = app / "src/main/assets/furinahub/index.html"

    for path in (manifest, main_activity, gradle):
        if not path.is_file():
            raise SystemExit(f"RC20 source missing: {path}")

    gradle_text = gradle.read_text(encoding="utf-8")
    gradle_text = replace_once(gradle_text, "versionCode 10019", "versionCode 10020", "versionCode")
    gradle_text = replace_once(gradle_text, "versionName '1.0.0-rc19'", "versionName '1.0.0-rc20'", "versionName")
    gradle.write_text(gradle_text, encoding="utf-8")

    shutil.copyfile(templates / "MainActivity.java", main_activity)
    asset.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(templates / "hub_shell.html", asset)

    manifest_text = manifest.read_text(encoding="utf-8")
    for marker in ('android:label="FurinaHub"', 'com.termux.permission.RUN_COMMAND', '<package android:name="com.termux"'):
        if marker not in manifest_text:
            raise SystemExit(f"RC20 manifest prerequisite missing: {marker}")

    java = main_activity.read_text(encoding="utf-8")
    for marker in ("loadBundledShell()", "connectionStatus()", "connectCore()", "requestPermissions(new String[]{RUN_COMMAND}", "coreRequest(String requestId", "setAllowFileAccess(false)", "setAllowContentAccess(false)", "loadDataWithBaseURL"):
        if marker not in java:
            raise SystemExit(f"RC20 Java marker missing: {marker}")

    shell = asset.read_text(encoding="utf-8")
    for marker in ("Hubungkan ke Termux", "Personalisasi", "Agent & Skill", "prefers-reduced-motion", "min-width:44px", "Memori & Psyche"):
        if marker not in shell:
            raise SystemExit(f"RC20 shell marker missing: {marker}")
    if "Ringkasan Hubungan" in shell:
        raise SystemExit("RC20 shell contains forbidden relationship summary")

    print("FURINAHUB_ANDROID_RC20_OK")


if __name__ == "__main__":
    main()
