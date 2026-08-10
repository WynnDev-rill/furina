#!/usr/bin/env python3
"""Deterministic Furina architecture audit used by humans and autonomous workers.

The script intentionally reports evidence and warnings without pretending to evaluate
model output quality. Behavioral quality belongs to actual companion evals.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KOTLIN = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina"
SCRIPTS = ROOT / "scripts"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def main() -> int:
    memory = read(KOTLIN / "MemoryStore.kt")
    intelligence = read(KOTLIN / "CompanionIntelligence.kt")
    local = read(KOTLIN / "LocalLlamaProvider.kt")
    context = read(KOTLIN / "ContextEngine.kt")
    unified = read(KOTLIN / "UnifiedAiEngine.kt")
    catalog = read(KOTLIN / "ModelCatalog.kt")
    native_overlay = read(SCRIPTS / "overlays/ai_chat.cpp")
    runtime_policy = read(SCRIPTS / "apply-companion-runtime-policy.py")

    state_defs = []
    for file_name, text in [("MemoryStore.kt", memory), ("CompanionIntelligence.kt", intelligence)]:
        for match in re.finditer(r"(?:data\s+class|class)\s+(Companion\w*State\w*)", text):
            state_defs.append({"file": file_name, "name": match.group(1)})

    findings = []
    if len(state_defs) > 1:
        findings.append({
            "severity": "high",
            "code": "duplicate_companion_state",
            "evidence": state_defs,
            "message": "Multiple companion-state models exist; verify there is one canonical source of truth."
        })

    if "maybeRemember" in memory and "extractMemoryCandidates" in memory:
        findings.append({
            "severity": "info",
            "code": "automatic_memory_present",
            "message": "Automatic user-memory extraction is present."
        })
    if "Regex(" in memory or "Regex(" in intelligence:
        findings.append({
            "severity": "medium",
            "code": "rule_based_learning",
            "message": "Companion learning contains rule/regex-based extraction; test implicit preference learning separately."
        })

    if "runMaintenance" in unified and ("delay(" in unified or "MAINTENANCE" in unified.upper()):
        findings.append({
            "severity": "info",
            "code": "deferred_maintenance",
            "message": "Heavy companion maintenance is deferred from the generation hot path."
        })

    cpu_only = "n_gpu_layers = 0" in native_overlay
    if cpu_only:
        findings.append({
            "severity": "medium",
            "code": "cpu_only_local_inference",
            "message": "Native overlay configures CPU-only local inference; this is a likely throughput ceiling."
        })

    thinking_disabled = "enable_thinking" in runtime_policy and "false" in runtime_policy.lower()
    if thinking_disabled:
        findings.append({
            "severity": "info",
            "code": "thinking_disabled_by_policy",
            "message": "Build-time runtime policy explicitly disables thinking for the companion runtime."
        })

    model_count = len(re.findall(r"ModelSpec\s*\(", catalog)) or len(re.findall(r"LocalModel", catalog))
    latest_first = "latest" in context.lower() or "answer the latest" in context.lower()

    result = {
        "schemaVersion": 1,
        "stateDefinitions": state_defs,
        "signals": {
            "localProviderPresent": bool(local),
            "contextEnginePresent": bool(context),
            "unifiedEnginePresent": bool(unified),
            "cpuOnlyOverlay": cpu_only,
            "thinkingDisabledByPolicy": thinking_disabled,
            "modelCatalogEntriesApprox": model_count,
            "latestMessagePrioritySignal": latest_first
        },
        "findings": findings
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
