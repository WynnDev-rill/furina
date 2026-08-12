#!/usr/bin/env python3
"""Validate update.json against the APK bytes before release publication."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> None:
    raise SystemExit(f"UPDATER MANIFEST GATE FAILED: {message}")


def main() -> None:
    if len(sys.argv) != 3:
        fail("usage: updater-manifest-gate.py update.json Furina.apk")
    manifest_path = Path(sys.argv[1])
    apk_path = Path(sys.argv[2])
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    for field in ("versionCode", "versionName", "minimumVersionCode", "mandatory", "apkUrl", "sha256", "packageName", "signerSha256"):
        if field not in data:
            fail(f"missing {field}")
    if not isinstance(data["versionCode"], int) or data["versionCode"] <= 0:
        fail("invalid versionCode")
    if not isinstance(data["minimumVersionCode"], int) or data["minimumVersionCode"] <= 0:
        fail("invalid minimumVersionCode")
    if not isinstance(data["mandatory"], bool):
        fail("mandatory must be boolean")
    if data["packageName"] != "com.wynndev.furina":
        fail("unexpected packageName")

    expected = str(data["sha256"]).lower().replace(":", "")
    signer = str(data["signerSha256"]).lower().replace(":", "")
    if not HEX64.fullmatch(expected):
        fail("invalid APK SHA-256")
    if not HEX64.fullmatch(signer):
        fail("invalid signer SHA-256")

    digest = hashlib.sha256(apk_path.read_bytes()).hexdigest()
    if digest != expected:
        fail("APK bytes do not match manifest sha256")

    if not str(data["apkUrl"]).startswith("https://github.com/WynnDev-rill/furina/releases/"):
        fail("untrusted apkUrl")

    print("Updater manifest gate passed: release manifest is bound to APK digest and expected package/signer metadata")


if __name__ == "__main__":
    main()
