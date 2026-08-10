#!/usr/bin/env python3
"""Validate Furina Engineering Company control-plane invariants.

This gate protects the rules that prevent hourly reward hacking, same-cycle self-review,
false BEHAVIORAL claims, policy drift, infrastructure churn, and autonomous merge authority.
It validates contracts; it does not itself prove Furina model quality.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "engineering/COMPANY.md"
WORKER = ROOT / "engineering/worker/HOURLY_PROMPT.md"
WORK_PACKAGE = ROOT / "engineering/work-package/POLICY.md"
PRIORITY = ROOT / "engineering/prioritization/POLICY.md"
INDEPENDENCE = ROOT / "engineering/review/INDEPENDENCE_POLICY.md"
REVIEW_SCHEMA = ROOT / "engineering/review/decision.schema.json"
DEVICE_SCHEMA = ROOT / "engineering/evidence/device-report.schema.json"
BEHAVIORAL_SCHEMA = ROOT / "engineering/evidence/behavioral-run.schema.json"
CALIBRATION_SCHEMA = ROOT / "engineering/calibration/record.schema.json"
BOSS_POLICY = ROOT / "engineering/boss/BOSS_POLICY.md"
BOSS_SCHEMA = ROOT / "engineering/boss/decision.schema.json"


class ContractError(RuntimeError):
    pass


def read(path: Path) -> str:
    if not path.is_file():
        raise ContractError(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    try:
        return json.loads(read(path))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def require_all(label: str, text: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise ContractError(f"{label} missing contract markers: {', '.join(missing)}")


def require_required_fields(label: str, schema: dict, expected: set[str]) -> None:
    actual = set(schema.get("required", []))
    missing = sorted(expected - actual)
    if missing:
        raise ContractError(f"{label} missing required fields: {missing}")


def main() -> int:
    company = read(COMPANY)
    worker = read(WORKER)
    work_package = read(WORK_PACKAGE)
    priority = read(PRIORITY)
    independence = read(INDEPENDENCE)
    boss_policy = read(BOSS_POLICY)

    lifecycle = ["active", "testing", "ready_for_merge", "blocked_human", "completed", "superseded"]

    require_all(
        "COMPANY.md",
        company,
        [
            "REVIEW_GATED",
            *lifecycle,
            "Every engineering cycle may legitimately conclude with NO_CHANGE",
            "A green build is evidence of build health, not proof of product improvement",
            "STATIC",
            "CI",
            "BEHAVIORAL",
            "DEVICE",
            "Auto-merge is intentionally disabled today",
        ],
    )

    require_all(
        "PRIORITIZATION/POLICY.md",
        priority,
        [
            "authoritative for candidate ranking",
            "P0_PRODUCT",
            "P0_UNBLOCKER",
            "P1_PRODUCT",
            "P2_PRODUCT",
            "META_ENGINEERING",
            "A lower tier cannot outrank a higher eligible tier",
            "withinTierScore",
            "no more than one of the last six completed change-producing cycles",
            "confidence is capped at 7/10",
            "engineering/calibration/record.schema.json",
            "Anti-self-optimization rule",
        ],
    )

    require_all(
        "REVIEW/INDEPENDENCE_POLICY.md",
        independence,
        [
            "Engineer phase",
            "Reviewer phase",
            "Boss phase",
            "different `cycleId`",
            "reviewCycleId",
            "bossCycleId",
            "reviewedHeadSha",
            "Any new commit invalidates both previous Reviewer and Boss approval",
            "Role labels inside one model response are not independent review",
        ],
    )

    require_all(
        "WORK_PACKAGE/POLICY.md",
        work_package,
        [
            "engineering/prioritization/POLICY.md",
            "one coherent high-value work package",
            "Do not create a PR for a trivial isolated tweak",
            "Do not combine unrelated subsystems",
            "same execution that writes the package must not certify it as Reviewer or Boss",
            "engineering/calibration/record.schema.json",
            "Do not repeatedly push no-op or cosmetic commits",
            "## Ringkasan Indonesia",
        ],
    )

    require_all(
        "HOURLY_PROMPT.md",
        worker,
        [
            "engineering/prioritization/POLICY.md",
            "engineering/review/INDEPENDENCE_POLICY.md",
            "engineering/evidence/behavioral-run.schema.json",
            "engineering/calibration/record.schema.json",
            "scheduler prompt must not duplicate the full company policy",
            "One-role-per-cycle rule",
            "reviewCycleId != engineerCycleId",
            "bossCycleId",
            "actualModelRun=true",
            "Strategic tier is lexicographic",
            "META_ENGINEERING",
            "Never auto-merge",
            "Human merge remains the final write to `main`",
        ],
    )

    if "priority = impact * confidence * frequency / max(1, effort * regressionRisk)" in worker:
        raise ContractError("HOURLY_PROMPT.md reintroduced the old reward-hacking-prone priority formula")

    require_all(
        "BOSS_POLICY.md",
        boss_policy,
        [
            "Role labels inside one model response are not independent review",
            "engineerCycleId",
            "reviewCycleId",
            "bossCycleId",
            "reviewedHeadSha",
            "Reviewer and Boss results must be recorded separately",
            "actualModelRun=true",
            "engineering/prioritization/POLICY.md",
            "engineering/calibration/record.schema.json",
            "It does NOT merge automatically",
            "Anti-rubber-stamp rule",
        ],
    )

    review = read_json(REVIEW_SCHEMA)
    require_required_fields(
        "review/decision.schema.json",
        review,
        {
            "pullRequest", "reviewCycleId", "engineerCycleId", "reviewedHeadSha",
            "verdict", "evidenceLevel", "regressionRisk", "scopeCoherence",
            "simplerAlternative", "reason", "reviewedAt",
        },
    )
    review_verdicts = set(review.get("properties", {}).get("verdict", {}).get("enum", []))
    if review_verdicts != {"APPROVE", "REQUEST_CHANGES", "BLOCKED_HUMAN", "NO_CHANGE_RECOMMENDED"}:
        raise ContractError(f"review decision enum mismatch: {sorted(review_verdicts)}")

    device = read_json(DEVICE_SCHEMA)
    require_required_fields(
        "device-report.schema.json",
        device,
        {"schemaVersion", "recordedAt", "commit", "device", "model", "objective", "observation"},
    )
    for field in ("measurements", "runtime", "behavioral", "privacy"):
        if field not in device.get("properties", {}):
            raise ContractError(f"device-report.schema.json missing property: {field}")

    behavioral = read_json(BEHAVIORAL_SCHEMA)
    require_required_fields(
        "behavioral-run.schema.json",
        behavioral,
        {"schemaVersion", "recordedAt", "commit", "benchmarkVersion", "actualModelRun", "model", "scenarios", "aggregate"},
    )
    actual_model_run = behavioral.get("properties", {}).get("actualModelRun", {})
    if actual_model_run.get("const") is not True:
        raise ContractError("behavioral-run.schema.json must require actualModelRun=true")
    scenario = behavioral.get("properties", {}).get("scenarios", {}).get("items", {})
    scenario_required = set(scenario.get("required", []))
    if not {"scenarioId", "output", "scores"}.issubset(scenario_required):
        raise ContractError("behavioral-run.schema.json scenarios must require scenarioId/output/scores")

    calibration = read_json(CALIBRATION_SCHEMA)
    require_required_fields(
        "calibration/record.schema.json",
        calibration,
        {"schemaVersion", "workId", "category", "strategicTier", "prediction", "status"},
    )
    prediction_required = set(calibration.get("properties", {}).get("prediction", {}).get("required", []))
    expected_prediction = {"cycleId", "recordedAt", "impact", "confidence", "expectedMetric", "expectedDelta", "verificationWindow"}
    if not expected_prediction.issubset(prediction_required):
        raise ContractError("calibration prediction contract is incomplete")
    calibration_enum = set(
        calibration.get("properties", {})
        .get("observation", {})
        .get("properties", {})
        .get("calibration", {})
        .get("enum", [])
    )
    if calibration_enum != {"overestimated", "calibrated", "underestimated", "inconclusive"}:
        raise ContractError("calibration outcome enum mismatch")

    boss = read_json(BOSS_SCHEMA)
    require_required_fields(
        "boss/decision.schema.json",
        boss,
        {
            "decision", "pullRequest", "headSha", "engineerCycleId", "reviewCycleId",
            "bossCycleId", "reviewedHeadSha", "evidenceLevel", "productValue",
            "regressionRisk", "complexityCost", "confidence", "reason",
            "requiredNextAction", "decidedAt",
        },
    )
    decisions = set(boss.get("properties", {}).get("decision", {}).get("enum", []))
    expected_decisions = {"APPROVE_MERGE", "REJECT_CLOSE", "REQUEST_REVISION", "BLOCKED_HUMAN"}
    if decisions != expected_decisions:
        raise ContractError(f"boss decision enum mismatch: {sorted(decisions)}")

    print("Furina Engineering Company v3 control-plane policy gate passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(f"Furina Engineering Company v3 control-plane policy gate failed: {error}")
        raise SystemExit(1)
