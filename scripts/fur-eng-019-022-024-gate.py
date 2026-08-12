#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FUR-ENG-019/020/021/022/024 gate failed: {message}")

engine = text("android-wrapper/app/src/main/java/com/wynndev/furina/UnifiedAiEngine.kt")
offline = text("android-wrapper/app/src/main/assets/furina-offline.html")
models = text("android-wrapper/app/src/main/java/com/wynndev/furina/ModelDownloadManager.kt")
updater = text("android-wrapper/app/src/main/java/com/wynndev/furina/UpdateManager.kt")

# 019: every completed turn must be queued; only summary compaction may be debounced.
require("requiredMaintenanceTail" in engine, "required companion maintenance queue missing")
require("previous?.join()" in engine, "companion maintenance is not serialized")
require("contextEngine.runMaintenance(sessionId, userText)" in engine, "required companion maintenance missing")
require("summaryJob?.cancel()" in engine, "summary debounce missing")

# 020: fallback shell must use persisted identity/persona/language.
require("b.appSettings()" in offline, "offline shell does not read native app settings")
require("companionPersona=effectivePersona(settings)" in offline, "offline persona/language continuity missing")
require("b.generate(activeRequest,sessionId,text,companionName,companionPersona)" in offline, "offline generation still uses hard-coded identity")

# 021: starting download must never delete a ready model.
require('if (currentState == "ready") return current' in models, "ready model is not protected from redownload")
require("modelAction').disabled=ready" in offline, "offline UI still allows redownload of verified ready model")

# 022: only a previously validated mandatory policy may enforce without network.
require("KEY_CACHED_POLICY" in updater, "validated update policy cache missing")
require("cachedMandatoryPolicy(current)" in updater, "offline mandatory enforcement missing")
require("cacheValidatedPolicy(fetched)" in updater, "validated manifest is not cached")

# 024: DownloadManager entry and stale updater-owned APK files must be removed after completion.
require("downloadManager.remove(id)" in updater, "completed DownloadManager entry is not removed")
require("cleanupUpdateFiles(currentVersionCode)" in updater, "completed update APK cleanup missing")
require("UPDATE_FILE_REGEX" in updater, "cleanup is not constrained to Furina updater files")

print("FUR-ENG-019/020/021/022/024 deterministic gate: PASS")
print("FUR-ENG-023 intentionally excluded: proper database encryption requires a separate storage-migration design and approval.")
