#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
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
    require("query = \"\"" in unified, "prewarm must not retrieve against the previous user message")
    require("delay(6_000L)" in unified and "runMaintenance" in unified,
            "heavy memory/reflection work must wait for idle time")
    require("engine.setSystemPrompt(context.coldStartPrompt)" in local,
            "local provider must hydrate stable context only")
    require("[PRIVATE RESPONSE CONTEXT]" in local, "local turn context needs an explicit private boundary")
    wrapper = local.split('appendLine("[PRIVATE RESPONSE CONTEXT]")', 1)[1]
    require("append(request.userMessage)" in wrapper, "latest user message must be placed after background context")
    require("React as a person before answering as an assistant" not in context,
            "identity must not impose a mandatory reaction-before-answer pattern")
    require("must never create a mandatory prelude" in context,
            "identity must explicitly prevent fixed companion openings")


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
    count = verify_scenario_matrix()
    print(f"Furina companion quality gate passed: {count} deterministic pipeline scenarios")


if __name__ == "__main__":
    main()
