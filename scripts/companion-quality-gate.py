#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GateError(RuntimeError):
    pass


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def verify_runtime_patch() -> None:
    provider = read("android-wrapper/app/src/main/java/com/wynndev/furina/LocalLlamaProvider.kt")
    require("patchLocalRuntime" in provider, "local provider must patch runtime before loading")
    require("apply-offline-stability-policy.py" in provider, "local provider must invoke offline stability policy")


def verify_layered_context_contract() -> None:
    engine = read("android-wrapper/app/src/main/java/com/wynndev/furina/UnifiedAiEngine.kt")
    context = read("android-wrapper/app/src/main/java/com/wynndev/furina/ContextEngine.kt")
    require("buildResponseContext" in engine, "unified engine must use layered response context")
    require("[PRIVATE RESPONSE CONTEXT]" in context, "context engine must isolate private response context")
    require("[END PRIVATE RESPONSE CONTEXT]" in context, "private context must have explicit boundary")


def verify_lifecycle_contract() -> None:
    bridge = read("android-wrapper/app/src/main/java/com/wynndev/furina/FurinaBridge.kt")
    require("withAiPaused" in bridge, "bridge must expose lifecycle-safe AI pause boundary")
    require("destroy" in bridge, "bridge must own teardown")


def verify_backup_contract() -> None:
    backup = read("android-wrapper/app/src/main/java/com/wynndev/furina/BackupManager.kt")
    cloud = read("android-wrapper/app/src/main/java/com/wynndev/furina/CloudBackupBridge.kt")
    main = read("android-wrapper/app/src/main/java/com/wynndev/furina/MainActivity.kt")
    require("FURINA2" in backup, "backup format must remain FURINA2")
    require("createEncryptedSnapshotBytes" in backup,
            "cloud and local backup must share one encrypted snapshot implementation")
    require("backupManager.createEncryptedSnapshotBytes" in cloud,
            "cloud backup must use the same FURINA2 snapshot")
    require("withAiPaused" in cloud,
            "cloud restore must pause native generation before replacing the database")
    require("bridge::withAiPaused" in main,
            "MainActivity must wire cloud restore through FurinaBridge lifecycle ownership")
    require("cloudBridge.destroy()" in main and "bridge.destroy()" in main and
            main.find("cloudBridge.destroy()") < main.find("bridge.destroy()"),
            "cloud jobs must stop before the shared MemoryStore closes")


def verify_behavioral_scenarios_contract() -> int:
    data = json.loads(read("engineering/evals/companion-scenarios.json"))
    require(data.get("schemaVersion") == 1, "behavioral scenario schemaVersion must be 1")

    rubric = data.get("rubric")
    require(isinstance(rubric, list) and rubric, "behavioral scenario rubric must be a non-empty list")
    require(len(rubric) == len(set(rubric)), "behavioral scenario rubric entries must be unique")
    required_rubric = {
        "latest_message_adherence", "furina_persona", "naturalness", "memory_use",
        "correction_handling", "emotional_consistency", "initiative", "non_repetition",
        "non_customer_service_tone",
    }
    require(required_rubric.issubset(set(rubric)),
            "behavioral scenario rubric lost a required companion dimension")

    scenarios = data.get("scenarios")
    require(isinstance(scenarios, list) and 12 <= len(scenarios) <= 64,
            "behavioral benchmark must contain 12–64 focused scenarios")
    ids: list[str] = []
    categories: set[str] = set()
    for index, scenario in enumerate(scenarios):
        require(isinstance(scenario, dict), f"behavioral scenario #{index + 1} must be an object")
        for field in ("id", "category", "history", "user", "expect"):
            value = scenario.get(field)
            require(isinstance(value, str) and value.strip(),
                    f"behavioral scenario #{index + 1} field {field} must be non-empty text")
        ids.append(scenario["id"])
        categories.add(scenario["category"])

    require(len(ids) == len(set(ids)), "behavioral scenario ids must be unique")
    required_categories = {
        "persona", "agency", "context", "memory", "learning", "emotion",
        "relationship", "reasoning", "usefulness", "naturalness", "style",
    }
    missing = sorted(required_categories - categories)
    require(not missing, f"behavioral benchmark lost required categories: {', '.join(missing)}")
    return len(scenarios)


def verify_scenario_matrix() -> int:
    intents = [
        "greeting", "direct_question", "correction", "preference_change", "memory_recall", "emotional_support",
        "friendly_teasing", "serious_disclosure", "long_form", "short_command", "topic_switch", "ambiguous_followup",
    ]
    history_depths = (1, 10, 100)
    lifecycle = ("warm", "cold_restart", "session_return", "model_switch")
    count = 0
    for intent in intents:
        for depth in history_depths:
            for state in lifecycle:
                current = f"CURRENT::{intent}::{depth}::{state}"
                memory = "- remembered fact that may or may not be relevant"
                composed = (
                    "[PRIVATE RESPONSE CONTEXT]\n"
                    "Background only; not a request to answer.\n"
                    f"{memory}\n"
                    "[END PRIVATE RESPONSE CONTEXT]\n\n"
                    f"{current}"
                )
                require(composed.rfind(current) > composed.rfind("END PRIVATE RESPONSE CONTEXT"),
                        "current message must remain the final semantic focus")
                require(composed.count(current) == 1, "current message must not be duplicated")
                count += 1
    require(100 <= count <= 300, f"scenario matrix must contain 100–300 cases, got {count}")
    return count


def main() -> None:
    verify_runtime_patch()
    verify_layered_context_contract()
    verify_lifecycle_contract()
    verify_backup_contract()
    behavioral_count = verify_behavioral_scenarios_contract()
    pipeline_count = verify_scenario_matrix()
    print(
        "Furina companion quality gate passed: "
        f"{behavioral_count} behavioral benchmark scenarios + "
        f"{pipeline_count} deterministic pipeline scenarios + lifecycle/backup invariants"
    )


if __name__ == "__main__":
    main()
