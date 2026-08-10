#!/usr/bin/env python3
"""Validate the Furina Engineering Company operating contract.

This is intentionally deterministic. It verifies that the autonomous worker cannot
silently lose the anti-stall lifecycle, evidence policy, review-gated merge rule,
or independent Boss decision gate. It does not claim to evaluate Furina model behavior.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "engineering/COMPANY.md"
WORKER = ROOT / "engineering/worker/HOURLY_PROMPT.md"
DEVICE_SCHEMA = ROOT / "engineering/evidence/device-report.schema.json"
BOSS_POLICY = ROOT / "engineering/boss/BOSS_POLICY.md"
BOSS_SCHEMA = ROOT / "engineering/boss/decision.schema.json"


class ContractError(RuntimeError):
    pass


def read(path: Path) -> str:
    if not path.is_file():
        raise ContractError(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_all(label: str, text: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise ContractError(f"{label} missing contract markers: {', '.join(missing)}")


def main() -> int:
    company = read(COMPANY)
    worker = read(WORKER)
    schema_text = read(DEVICE_SCHEMA)
    boss_policy = read(BOSS_POLICY)
    boss_schema_text = read(BOSS_SCHEMA)

    require_all(
        "COMPANY.md",
        company,
        [
            "REVIEW_GATED",
            "blocked_human",
            "ready_for_merge",
            "Do not spend a new cycle re-reviewing a `blocked_human` PR unless there is new evidence",
            "STATIC",
            "CI",
            "BEHAVIORAL",
            "DEVICE",
            "Auto-merge is intentionally disabled today",
        ],
    )
    require_all(
        "HOURLY_PROMPT.md",
        worker,
        [
            "blocked_human",
            "awaiting_boss",
            "boss_approved",
            "new commit, CI result, behavioral/model-output evidence, device report, Boss decision, or human decision",
            "A `blocked_human` PR with no new evidence must not consume another cycle",
            "Never auto-merge",
            "STATIC, CI, BEHAVIORAL, or DEVICE",
            "APPROVE_MERGE",
            "REJECT_CLOSE",
            "REQUEST_REVISION",
            "BLOCKED_HUMAN",
        ],
    )
    require_all(
        "BOSS_POLICY.md",
        boss_policy,
        [
            "The Boss does not write code",
            "APPROVE_MERGE",
            "REJECT_CLOSE",
            "REQUEST_REVISION",
            "BLOCKED_HUMAN",
            "It does NOT merge automatically",
            "Anti-rubber-stamp rule",
        ],
    )

    schema = json.loads(schema_text)
    required = set(schema.get("required", []))
    expected_required = {"schemaVersion", "recordedAt", "commit", "device", "model", "objective", "observation"}
    if not expected_required.issubset(required):
        missing = sorted(expected_required - required)
        raise ContractError(f"device report schema missing required fields: {missing}")

    properties = schema.get("properties", {})
    for field in ("measurements", "runtime", "behavioral", "privacy"):
        if field not in properties:
            raise ContractError(f"device report schema missing property: {field}")

    boss_schema = json.loads(boss_schema_text)
    boss_required = set(boss_schema.get("required", []))
    expected_boss_required = {
        "decision", "pullRequest", "headSha", "evidenceLevel", "productValue",
        "regressionRisk", "complexityCost", "confidence", "reason",
        "requiredNextAction", "decidedAt"
    }
    if not expected_boss_required.issubset(boss_required):
        missing = sorted(expected_boss_required - boss_required)
        raise ContractError(f"boss decision schema missing required fields: {missing}")

    decision_enum = set(
        boss_schema.get("properties", {}).get("decision", {}).get("enum", [])
    )
    expected_decisions = {"APPROVE_MERGE", "REJECT_CLOSE", "REQUEST_REVISION", "BLOCKED_HUMAN"}
    if decision_enum != expected_decisions:
        raise ContractError(f"boss decision enum mismatch: {sorted(decision_enum)}")

    print("Furina Engineering Company v2 policy gate passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(f"Furina Engineering Company v2 policy gate failed: {error}")
        raise SystemExit(1)
