#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"QUALITY GATE FAILED: {message}")


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def verify_runtime_patch() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        cpp = td_path / "ai_chat.cpp"
        kt = td_path / "InferenceEngineImpl.kt"
        shutil.copy2(ROOT / "scripts/overlays/ai_chat.cpp", cpp)
        shutil.copy2(ROOT / "scripts/overlays/InferenceEngineImpl.kt", kt)
        subprocess.run(
            ["python3", str(ROOT / "scripts/apply-companion-runtime-policy.py"), str(cpp), str(kt)],
            check=True,
            capture_output=True,
            text=True,
        )
        patched_cpp = cpp.read_text(encoding="utf-8")
        patched_kt = kt.read_text(encoding="utf-8")
        require("DEFAULT_SAMPLER_TEMP    = 0.7f" in patched_cpp, "Qwen3.5 temperature must be 0.7")
        require("sparams.top_p = 0.80f" in patched_cpp, "Qwen3.5 top_p must be 0.8")
        require("sparams.top_k = 20" in patched_cpp, "Qwen3.5 top_k must be 20")
        require("sparams.penalty_present = 1.5f" in patched_cpp, "presence penalty must reduce loops")
        require('inputs.chat_template_kwargs["enable_thinking"] = "false"' in patched_cpp,
                "Qwen3.5 thinking must be disabled through chat template kwargs")
        require("common_sampler_reset(g_sampler)" in patched_cpp, "sampler penalties must reset per reply")
        require("processUserPrompt(message, predictLength)" in patched_kt, "raw current user message must reach native formatter")
        require("processUserPrompt(controlledMessage" not in patched_kt, "legacy /think prompt mutation must be inactive")


def verify_layered_context_contract() -> None:
    contracts = read("android-wrapper/app/src/main/java/com/wynndev/furina/AiContracts.kt")
    context = read("android-wrapper/app/src/main/java/com/wynndev/furina/ContextEngine.kt")
    local = read("android-wrapper/app/src/main/java/com/wynndev/furina/LocalLlamaProvider.kt")
    unified = read("android-wrapper/app/src/main/java/com/wynndev/furina/UnifiedAiEngine.kt")

    require("val coldStartPrompt" in contracts, "local cold start needs a query-independent rehydration layer")
    cold_section = contracts.split("val coldStartPrompt", 1)[1].split("val systemPrompt", 1)[0]
    require("relevantMemories" not in cold_section and "relevantHistory" not in cold_section,
            "query retrieval must never be frozen into local cold start")
    require("store.relevantOldContext" in context, "episodic history must use role-safe SQLite/FTS retrieval")
    require("companion.relevantHistory" not in context, "role-guessing history path must not be used")
    require("store.relevantMemories" in context, "hot-path memory retrieval must stay deterministic and DB-backed")
    require("getDeclaredField" not in context, "ContextEngine must use explicit Context injection, not reflection")
    require("query = \"\"" in unified, "prewarm must not retrieve against the previous user message")
    require("delay(6_000L)" in unified and "runMaintenance" in unified,
            "heavy memory/reflection work must wait for idle time")
    summary_pos = unified.find("store.updateSessionSummary(sessionId)")
    delay_pos = unified.find("delay(6_000L)")
    require(summary_pos > delay_pos >= 0, "session summary compaction must run after the idle delay")
    require("engine.setSystemPrompt(context.coldStartPrompt)" in local,
            "local provider must hydrate stable context only")
    require("[PRIVATE RESPONSE CONTEXT]" in local, "local turn context needs an explicit private boundary")
    wrapper = local.split('appendLine("[PRIVATE RESPONSE CONTEXT]")', 1)[1]
    require("append(request.userMessage)" in wrapper, "latest user message must be placed after background context")
    require("React as a person before answering as an assistant" not in context,
            "identity must not impose a mandatory reaction-before-answer pattern")
    require("must never create a mandatory prelude" in context,
            "identity must explicitly prevent fixed companion openings")


def verify_lifecycle_contract() -> None:
    bridge = read("android-wrapper/app/src/main/java/com/wynndev/furina/FurinaBridge.kt")
    unified = read("android-wrapper/app/src/main/java/com/wynndev/furina/UnifiedAiEngine.kt")

    require("private val aiOperationMutex = Mutex()" in bridge,
            "native AI operations must share one lifecycle mutex")
    require("jobs.joinAll()" in bridge and "aiOperationMutex.withLock" in bridge,
            "mutations must cancel/join generation before touching llama.cpp")
    require("if (generationJob === job) generationJob = null" in bridge,
            "generation completion must only clear its own job reference")
    require("if (prepareJob === job) prepareJob = null" in bridge,
            "prepare completion must only clear its own job reference")
    stop = bridge.split("fun stopGeneration()", 1)[1].split("@JavascriptInterface", 1)[0]
    require("generationJob = null" not in stop,
            "stopGeneration must not clear its job reference before cancellation unwinds")
    require("store.deleteSession(sessionId)" in bridge and "session-delete" in bridge,
            "session delete must be repeated after generation cancellation to prevent ghost writes")
    require("store.clearSession(sessionId)" in bridge and "session-clear" in bridge,
            "session clear must be repeated after generation cancellation to prevent ghost writes")
    require("suspend fun withAiPaused" in bridge,
            "cloud restore needs a shared paused-AI mutation path")
    require("maintenanceJob?.cancelAndJoin()" in unified,
            "unload/restore must wait for idle memory writers")


def verify_backup_contract() -> None:
    backup = read("android-wrapper/app/src/main/java/com/wynndev/furina/BackupManager.kt")
    cloud = read("android-wrapper/app/src/main/java/com/wynndev/furina/CloudBackupBridge.kt")
    main = read("android-wrapper/app/src/main/java/com/wynndev/furina/MainActivity.kt")

    require('"FURINA2"' in backup and '"FURINA1"' in backup,
            "backup format must advance while preserving legacy restore")
    require('COMPANION_ENTRY = "companion_intelligence.json"' in backup,
            "portable backup must include learned companion continuity")
    for key in ("state", "experiences", "reflections", "memory_meta"):
        require(key in backup, f"portable backup must carry companion field {key}")
    require("createEncryptedSnapshotBytes" in backup and "restoreEncryptedSnapshotBytes" in backup,
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


def verify_behavioral_scenarios_contract() -> tuple[int, list[str]]:
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
    require(required_rubric.issubset(set(rubric)), "behavioral scenario rubric lost a required companion dimension")

    scenarios = data.get("scenarios")
    require(isinstance(scenarios, list) and 12 <= len(scenarios) <= 64,
            "behavioral benchmark must contain 12–64 focused scenarios")
    ids = []
    categories = set()
    executable_count = 0
    for index, scenario in enumerate(scenarios):
        require(isinstance(scenario, dict), f"behavioral scenario #{index + 1} must be an object")
        for field in ("id", "category", "history", "user", "expect"):
            value = scenario.get(field)
            require(isinstance(value, str) and value.strip(),
                    f"behavioral scenario #{index + 1} field {field} must be non-empty text")
        setup = scenario.get("setup")
        require(isinstance(setup, list), f"behavioral scenario {scenario['id']} setup must be a list")
        previous_role = None
        for turn_index, turn in enumerate(setup):
            require(isinstance(turn, dict) and set(turn) == {"role", "content"},
                    f"behavioral scenario {scenario['id']} setup turn #{turn_index + 1} must contain only role/content")
            require(turn["role"] in {"user", "assistant"},
                    f"behavioral scenario {scenario['id']} setup roles must be user/assistant only")
            require(isinstance(turn["content"], str) and turn["content"].strip(),
                    f"behavioral scenario {scenario['id']} setup content must be non-empty")
            require(turn["role"] != previous_role,
                    f"behavioral scenario {scenario['id']} setup roles must alternate")
            previous_role = turn["role"]
        if setup:
            require(setup[0]["role"] == "user" and setup[-1]["role"] == "assistant",
                    f"behavioral scenario {scenario['id']} setup must form complete user/assistant turns")
        executable_count += 1
        ids.append(scenario["id"])
        categories.add(scenario["category"])
    require(executable_count == len(scenarios), "every behavioral scenario must be executable")
    require(len(ids) == len(set(ids)), "behavioral scenario ids must be unique")
    required_categories = {
        "persona", "agency", "context", "memory", "learning", "emotion",
        "relationship", "reasoning", "usefulness", "naturalness", "style",
    }
    missing = sorted(required_categories - categories)
    require(not missing, f"behavioral benchmark lost required categories: {', '.join(missing)}")
    return len(scenarios), ids


def verify_behavioral_run_manifests(expected_ids: list[str]) -> None:
    runner = ROOT / "scripts/furina-behavioral-run-plan.py"
    inputs = json.loads(subprocess.run(
        [sys.executable, str(runner), "inputs"], check=True, capture_output=True, text=True,
    ).stdout)
    judge = json.loads(subprocess.run(
        [sys.executable, str(runner), "judge"], check=True, capture_output=True, text=True,
    ).stdout)

    input_scenarios = inputs.get("scenarios", [])
    judge_scenarios = judge.get("scenarios", [])
    input_ids = [item.get("scenarioId") for item in input_scenarios]
    judge_ids = [item.get("scenarioId") for item in judge_scenarios]
    require(input_ids == expected_ids, "behavioral input manifest must preserve benchmark order and IDs")
    require(judge_ids == expected_ids, "behavioral judge manifest must preserve benchmark order and IDs")
    require(all(set(item) == {"scenarioId", "setup", "user"} for item in input_scenarios),
            "model input manifest must contain only scenarioId/setup/user")
    require("rubric" not in inputs and "expect" not in json.dumps(inputs, ensure_ascii=False),
            "model input manifest must not leak judge rubric/expectations")
    require(isinstance(judge.get("rubric"), list) and judge["rubric"],
            "judge manifest must carry the scoring rubric")
    require(all(set(item) == {"scenarioId", "category", "expect"} for item in judge_scenarios),
            "judge manifest must contain scenarioId/category/expect only")


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
    behavioral_count, behavioral_ids = verify_behavioral_scenarios_contract()
    verify_behavioral_run_manifests(behavioral_ids)
    pipeline_count = verify_scenario_matrix()
    print(
        "Furina companion quality gate passed: "
        f"{behavioral_count} executable behavioral benchmark scenarios + "
        f"{pipeline_count} deterministic pipeline scenarios + lifecycle/backup invariants"
    )


if __name__ == "__main__":
    main()
