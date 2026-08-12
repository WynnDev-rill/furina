#!/usr/bin/env python3
"""Static regression gate for Furina's native APK update contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/UpdateManager.kt"
PUBLISH = ROOT / ".github/workflows/publish-furina-update.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"UPDATER REGRESSION GATE FAILED: {message}")


def main() -> None:
    updater = UPDATER.read_text(encoding="utf-8")
    publish = PUBLISH.read_text(encoding="utf-8")

    for marker in (
        'json.getString("sha256")',
        'json.getString("packageName")',
        'json.getString("signerSha256")',
        'PackageInfoCompat.getLongVersionCode(archive) != targetVersion',
        'sha256(apk) != expectedSha',
        'Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES',
        'downloadManager.getUriForDownloadedFile(id)',
        'clearPendingDownloadState()',
    ):
        require(marker in updater, f"UpdateManager missing invariant: {marker}")

    archive_signer_bound = (
        'expectedSigner !in archiveSigners' in updater or
        'expectedSigner !in signerDigests(archive)' in updater
    )
    installed_signer_bound = (
        'expectedSigner !in installedSigners' in updater or
        'return expectedSigner in signerDigests(installed)' in updater
    )
    require(archive_signer_bound, "UpdateManager must reject an APK whose signer differs from the manifest")
    require(installed_signer_bound, "UpdateManager must bind the manifest signer to the installed Furina signer")

    require('json.optBoolean("mandatory", false)' in updater,
            "updater default must be optional unless manifest explicitly says mandatory")
    require('"mandatory": False' in publish,
            "automated publisher must not make every APK update mandatory")
    require('"minimumVersionCode": 1' in publish,
            "automated publisher must not force minimum version to latest build")
    require('release_required=true' in publish and 'release_required=false' in publish,
            "publisher must distinguish validation builds from user-facing releases")
    for field in ('"sha256"', '"packageName"', '"signerSha256"'):
        require(field in publish, f"published update manifest missing {field}")

    print("Updater regression gate passed: optional-by-default release + artifact identity verification + install recovery invariants")


if __name__ == "__main__":
    main()
