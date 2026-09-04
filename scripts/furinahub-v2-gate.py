#!/usr/bin/env python3
"""Static release guard for the FurinaHub V2 chat appearance contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVITY = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/NativeHubActivity.kt"
APPEARANCE = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/ChatAppearance.kt"
CONTROLLER = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/NativeHubController.kt"
GRADLE = ROOT / "android-wrapper/app/build.gradle"
MANIFEST = ROOT / "android-wrapper/app/src/main/AndroidManifest.xml"


def require(source: str, needle: str, label: str) -> None:
    if needle not in source:
        raise SystemExit(f"FurinaHub V2 gate failed: {label}")


def main() -> None:
    activity = ACTIVITY.read_text(encoding="utf-8")
    appearance = APPEARANCE.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    gradle = GRADLE.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")

    require(gradle, 'versionName "4.1.${buildNumber}"', "versionName must identify the V2 line")
    require(activity, "private fun ChatWallpaper", "chat wallpaper renderer is missing")
    require(activity, "private fun VideoWallpaper", "motion wallpaper renderer is missing")
    require(activity, 'Text(if (connected) "Core" else "Sambungkan"', "compact Core state is missing")
    require(controller, "fun importChatWallpaper", "wallpaper import controller is missing")
    require(appearance, "MAX_IMAGE_BYTES = 12L * 1024L * 1024L", "image size guard changed")
    require(appearance, "MAX_VIDEO_BYTES = 20L * 1024L * 1024L", "video size guard changed")
    require(appearance, "MAX_VIDEO_DURATION_MS = 30_000L", "video duration guard changed")
    require(appearance, "context.filesDir", "wallpaper must stay in app-private storage")

    forbidden_permissions = (
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.MANAGE_EXTERNAL_STORAGE",
    )
    leaked = [permission for permission in forbidden_permissions if permission in manifest]
    if leaked:
        raise SystemExit(f"FurinaHub V2 gate failed: broad media permissions present: {', '.join(leaked)}")

    print("FurinaHub V2 gate passed")


if __name__ == "__main__":
    main()
