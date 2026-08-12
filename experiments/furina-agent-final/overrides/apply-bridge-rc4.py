#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


def replace_once(path: pathlib.Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-bridge-rc4.py <termux-root>")
    root = pathlib.Path(sys.argv[1]).resolve()
    gradle = root / "bridge/app/build.gradle"
    manifest = root / "bridge/app/src/main/AndroidManifest.xml"
    java = root / "bridge/app/src/main/java/com/wynndev/furinaagentbridge"
    main_activity = java / "MainActivity.java"
    updater = java / "BridgeUpdater.java"
    provider = java / "UpdateFileProvider.java"
    for path in (gradle, manifest, main_activity, updater, provider):
        if not path.is_file():
            raise SystemExit(f"missing RC4 source: {path}")

    replace_once(gradle, "        versionCode 10003", "        versionCode 10004", "Bridge RC4 versionCode")
    replace_once(gradle, "        versionName '1.0.0-rc3'", "        versionName '1.0.0-rc4'", "Bridge RC4 versionName")

    gradle_text = gradle.read_text(encoding="utf-8")
    manifest_text = manifest.read_text(encoding="utf-8")
    main_text = main_activity.read_text(encoding="utf-8")
    updater_text = updater.read_text(encoding="utf-8")
    provider_text = provider.read_text(encoding="utf-8")
    required = [
        ("rc4 versionCode", "versionCode 10004" in gradle_text),
        ("rc4 versionName", "versionName '1.0.0-rc4'" in gradle_text),
        ("install packages permission", "android.permission.REQUEST_INSTALL_PACKAGES" in manifest_text),
        ("private update provider", '.UpdateFileProvider' in manifest_text and 'android:exported="false"' in manifest_text),
        ("update UI", 'sectionTitle("UPDATE")' in main_text and 'BridgeUpdater' in main_text),
        ("verified metadata", "expectedSha256" in updater_text and "expectedSignerSha256" in updater_text),
        ("archive verification", "verifyArchive" in updater_text and "getPackageArchiveInfo" in updater_text),
        ("same signer verification", "installedSigner" in updater_text and "archiveSigner" in updater_text),
        ("content URI install", ".updateprovider/update.apk" in updater_text),
        ("provider read only", 'MODE_READ_ONLY' in provider_text and 'read only' in provider_text),
    ]
    failed = [name for name, ok in required if not ok]
    if failed:
        raise SystemExit("bridge RC4 transform incomplete: " + ", ".join(failed))
    print("Bridge RC4 in-app updater transform: OK")


if __name__ == "__main__":
    main()
