#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FUR-ENG-014-018 GATE FAILED: {message}")


def main() -> None:
    publisher = read(".github/workflows/publish-furina-update.yml")
    main_activity = read("android-wrapper/app/src/main/java/com/wynndev/furina/MainActivity.kt")
    backup = read("android-wrapper/app/src/main/java/com/wynndev/furina/BackupManager.kt")
    manager = read("android-wrapper/app/src/main/java/com/wynndev/furina/ModelDownloadManager.kt")
    worker = read("android-wrapper/app/src/main/java/com/wynndev/furina/ModelDownloadWorker.kt")
    offline = read("android-wrapper/app/src/main/assets/furina-offline.html")

    # 014: publisher must deterministically install and address the exact build-tools revision.
    require('ANDROID_BUILD_TOOLS:' in publisher, "publisher must pin Android build-tools")
    require('sdkmanager "build-tools;${ANDROID_BUILD_TOOLS}"' in publisher,
            "publisher must install pinned Android build-tools")
    require('APKSIGNER="$ANDROID_HOME/build-tools/${ANDROID_BUILD_TOOLS}/apksigner"' in publisher,
            "publisher must use the pinned apksigner path")

    # 015: hosted failure must fall back to a bundled, functional local shell.
    require('OFFLINE_ASSET = "furina-offline.html"' in main_activity,
            "MainActivity must define the bundled offline shell")
    require('loadOfflineShell(' in main_activity and 'onReceivedError' in main_activity,
            "main-frame load failures must activate offline shell")
    require('window.FurinaNative' in offline and '.generate(' in offline and '.modelCatalog()' in offline,
            "offline shell must drive native chat/model APIs")

    # 016: bridge must be scoped to trusted top-level content and untrusted frames blocked.
    require('attachNativeBridges()' in main_activity and 'detachNativeBridges()' in main_activity,
            "native bridges need explicit attach/detach lifecycle")
    require('if (request.isForMainFrame.not()) return true' in main_activity,
            "untrusted subframe navigation must be blocked")
    require("frame-src 'none'" in main_activity and 'settings.setSupportMultipleWindows(false)' in main_activity,
            "iframe/popup surface must be disabled")

    # 017: normal WebView status must never receive the recovery secret.
    info_section = backup.split('fun infoJson()', 1)[1].split('fun backupNow()', 1)[0]
    require('getOrCreateRecoveryKey()' not in info_section and '.put("recoveryKey",' not in info_section,
            "backup info JSON must not expose the recovery secret")
    require('showRecoveryKeyDialog(backupManager.getOrCreateRecoveryKey())' in main_activity,
            "recovery key must be revealed only via explicit native UI")

    # 018: new downloads and llama mmap must share one private location.
    require('File(applicationContext.noBackupFilesDir, "models")' in worker,
            "worker must download directly into private runtime storage")
    require('private val runtimeModelDir = File(context.noBackupFilesDir, "models")' in manager,
            "manager runtime directory must be no-backup private storage")
    ensure_section = manager.split('fun ensureRuntimeModel', 1)[1].split('private fun migrateLegacyDownload', 1)[0]
    require('FileOutputStream' not in ensure_section and '.copyTo(' not in ensure_section,
            "normal runtime preparation must not copy the full GGUF")

    print("FUR-ENG-014-018 gate passed: publisher, offline shell, bridge scope, recovery key, and single-copy GGUF invariants hold")


if __name__ == "__main__":
    main()
