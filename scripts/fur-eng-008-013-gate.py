#!/usr/bin/env python3
"""Deterministic invariants for approved FUR-ENG-008..013 package."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"FUR-ENG-008-013 GATE FAILED: {message}")


def main() -> None:
    unified = read("android-wrapper/app/src/main/java/com/wynndev/furina/UnifiedAiEngine.kt")
    model = read("android-wrapper/app/src/main/java/com/wynndev/furina/ModelCatalog.kt")
    online = read("android-wrapper/app/src/main/java/com/wynndev/furina/OpenAiCompatibleProvider.kt")
    updater = read("android-wrapper/app/src/main/java/com/wynndev/furina/UpdateManager.kt")
    publish = read(".github/workflows/publish-furina-update.yml")

    require("SESSION_CHECKPOINT_EVERY_MESSAGES" not in unified,
            "full session checkpoint cadence must stay disabled")
    require("activeProvider.checkpointConversation(" not in unified,
            "normal generation must not write full session KV checkpoints")
    require("companion-v4-role-safe-rehydration" in unified,
            "continuity mode must advertise role-safe rehydration")

    require("/resolve/main/" not in model,
            "model download must not depend on mutable Hugging Face main")
    require("DECKARD_HF_REVISION" in model and "/resolve/$DECKARD_HF_REVISION/" in model,
            "model download must use an explicit immutable revision")

    generate = online.split("private suspend fun generateCandidate", 1)[1].split("private fun applyReasoningPolicy", 1)[0]
    require('if (id != "gemini") payload.put("temperature", 0.85)' in generate,
            "Gemini payload must omit explicit temperature")
    require('.put("stream", true)\n            .put("temperature"' not in generate,
            "temperature must not be unconditional")

    for field in ("sha256", "packageName", "signerSha256"):
        require(f'json.getString("{field}")' in updater,
                f"updater must require {field}")
    require("PackageInfoCompat.getLongVersionCode(archive) != targetVersion" in updater,
            "updater must bind APK to target version")
    signer_bound = (
        "expectedSigner !in installedSigners" in updater or
        "return expectedSigner in signerDigests(installed)" in updater
    )
    require(signer_bound, "updater must bind new APK signer to installed Furina signer")

    require('"mandatory": False' in publish and '"minimumVersionCode": 1' in publish,
            "normal automated releases must be optional and not force latest minimum")
    require("release_required=false" in publish,
            "publisher must allow validation builds without a user release")
    require("updater-manifest-gate.py" in publish,
            "publisher must validate manifest against APK before release")

    print("FUR-ENG-008..013 gate passed")


if __name__ == "__main__":
    main()
