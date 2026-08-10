#!/usr/bin/env python3
"""Validate Furina Engineering Company control-plane invariants.

This gate protects strategic prioritization, event-driven role independence, exact-SHA
decision semantics, auditability, evidence discipline, and Boss-gated merge authority.
It validates contracts; it does not prove Furina runtime/model quality.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "company": ROOT / "engineering/COMPANY.md",
    "worker": ROOT / "engineering/worker/HOURLY_PROMPT.md",
    "work_package": ROOT / "engineering/work-package/POLICY.md",
    "priority": ROOT / "engineering/prioritization/POLICY.md",
    "independence": ROOT / "engineering/review/INDEPENDENCE_POLICY.md",
    "audit": ROOT / "engineering/decisions/AUDIT_POLICY.md",
    "review_schema": ROOT / "engineering/review/decision.schema.json",
    "device_schema": ROOT / "engineering/evidence/device-report.schema.json",
    "behavioral_schema": ROOT / "engineering/evidence/behavioral-run.schema.json",
    "calibration_schema": ROOT / "engineering/calibration/record.schema.json",
    "boss_policy": ROOT / "engineering/boss/BOSS_POLICY.md",
    "boss_schema": ROOT / "engineering/boss/decision.schema.json",
    "decision_gate": ROOT / "scripts/furina-decision-gate.py",
    "model_gate": ROOT / "scripts/furina-model-gate.py",
    "ci_wait": ROOT / "scripts/furina-ci-wait.py",
    "orchestrator": ROOT / ".github/workflows/furina-autonomous-gate.yml",
}

OLD_PRIORITY = "priority = impact * confidence * frequency / max(1, effort * regressionRisk)"

class ContractError(RuntimeError):
    pass

def read(path: Path) -> str:
    if not path.is_file():
        raise ContractError(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")

def read_json(path: Path) -> dict:
    try:
        value = json.loads(read(path))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value

def require_all(label: str, text: str, needles: list[str]) -> None:
    missing = [x for x in needles if x not in text]
    if missing:
        raise ContractError(f"{label} missing contract markers: {', '.join(missing)}")

def require_required_fields(label: str, schema: dict, expected: set[str]) -> None:
    actual = set(schema.get("required", []))
    missing = sorted(expected - actual)
    if missing:
        raise ContractError(f"{label} missing required fields: {missing}")

def main() -> int:
    text = {name: read(path) for name, path in FILES.items() if not name.endswith("_schema")}
    company = text["company"]
    worker = text["worker"]
    priority = text["priority"]
    independence = text["independence"]
    audit = text["audit"]
    boss = text["boss_policy"]
    orchestrator = text["orchestrator"]

    require_all("COMPANY.md", company, [
        "BOSS_GATED_AUTO_MERGE",
        "engineering/prioritization/POLICY.md",
        "engineering/review/INDEPENDENCE_POLICY.md",
        "engineering/decisions/AUDIT_POLICY.md",
        "scripts/furina-decision-gate.py",
        ".github/workflows/furina-autonomous-gate.yml",
        "There is no artificial wall-clock delay",
        "RED remains human-authorized and human-merged",
        "FURINA_COMPANY_PR_V1",
        "A green build is evidence of build health, not proof of product improvement",
        "STATIC", "CI", "BEHAVIORAL", "DEVICE",
    ])
    if OLD_PRIORITY in company:
        raise ContractError("COMPANY.md still contains the superseded cross-tier priority formula")
    if "REVIEW_GATED" in company and "BOSS_GATED_AUTO_MERGE" not in company:
        raise ContractError("COMPANY.md autonomy mode drifted back to REVIEW_GATED")

    require_all("PRIORITIZATION/POLICY.md", priority, [
        "authoritative for candidate ranking",
        "P0_PRODUCT", "P0_UNBLOCKER", "P1_PRODUCT", "P2_PRODUCT", "META_ENGINEERING",
        "A lower tier cannot outrank a higher eligible tier",
        "withinTierScore",
        "Anti-self-optimization rule",
    ])

    require_all("REVIEW/INDEPENDENCE_POLICY.md", independence, [
        "no minimum wall-clock delay",
        "separate GitHub Actions job",
        "reviewCycleId != engineerCycleId",
        "bossCycleId != engineerCycleId",
        "scripts/furina-decision-gate.py",
        "FURINA_REVIEW_DECISION_V1",
        "BOSS_GATED_AUTO_MERGE",
    ])

    require_all("DECISIONS/AUDIT_POLICY.md", audit, [
        "FURINA_REVIEW_DECISION_V1",
        "FURINA_BOSS_DECISION_V1",
        "separate top-level PR comments",
        "Never edit/reuse an old decision comment",
        "scripts/furina-decision-gate.py",
    ])

    require_all("HOURLY_PROMPT.md", worker, [
        "hourly automation is only a **shift trigger**",
        ".github/workflows/furina-autonomous-gate.yml",
        "strategic tier first",
        "Do **not** issue Reviewer APPROVE or Boss APPROVE_MERGE yourself",
        "Do **not** wait for an arbitrary minute boundary",
        "BOSS_GATED_AUTO_MERGE",
        "FURINA_COMPANY_PR_V1",
    ])
    if OLD_PRIORITY in worker:
        raise ContractError("HOURLY_PROMPT.md reintroduced old cross-tier priority formula")

    require_all("BOSS_POLICY.md", boss, [
        "fresh execution context",
        "There is no required time delay",
        "scripts/furina-decision-gate.py",
        "autonomy class",
        "BOSS_GATED_AUTO_MERGE",
        "APPROVE_MERGE",
        "RED",
        "FURINA_BOSS_DECISION_V1",
    ])

    require_all("furina-autonomous-gate.yml", orchestrator, [
        "models: read",
        "actions: read",
        "pull-requests: write",
        "issues: write",
        "furina-ci-wait.py",
        "furina-model-gate.py",
        "furina-decision-gate.py",
        "FURINA_REVIEW_DECISION_V1",
        "FURINA_BOSS_DECISION_V1",
        "APPROVE_MERGE",
        "autonomyClass",
        "github.event.pull_request.head.repo.full_name == github.repository",
    ])

    review = read_json(FILES["review_schema"])
    require_required_fields("review/decision.schema.json", review, {
        "pullRequest", "reviewCycleId", "engineerCycleId", "reviewedHeadSha",
        "verdict", "evidenceLevel", "regressionRisk", "scopeCoherence",
        "simplerAlternative", "reason", "reviewedAt",
    })

    boss_schema = read_json(FILES["boss_schema"])
    require_required_fields("boss/decision.schema.json", boss_schema, {
        "decision", "pullRequest", "headSha", "engineerCycleId", "reviewCycleId",
        "bossCycleId", "reviewedHeadSha", "evidenceLevel", "autonomyClass",
        "productValue", "regressionRisk", "complexityCost", "confidence",
        "reason", "requiredNextAction", "decidedAt",
    })
    autonomy = set(boss_schema.get("properties", {}).get("autonomyClass", {}).get("enum", []))
    if autonomy != {"GREEN", "YELLOW", "RED"}:
        raise ContractError(f"Boss autonomyClass enum mismatch: {sorted(autonomy)}")

    behavioral = read_json(FILES["behavioral_schema"])
    if behavioral.get("properties", {}).get("actualModelRun", {}).get("const") is not True:
        raise ContractError("behavioral-run.schema.json must require actualModelRun=true")

    calibration = read_json(FILES["calibration_schema"])
    require_required_fields("calibration/record.schema.json", calibration, {
        "schemaVersion", "workId", "category", "strategicTier", "prediction", "status",
    })

    device = read_json(FILES["device_schema"])
    require_required_fields("device-report.schema.json", device, {
        "schemaVersion", "recordedAt", "commit", "device", "model", "objective", "observation",
    })

    proc = subprocess.run(
        [sys.executable, str(FILES["decision_gate"]), "self-test"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode:
        raise ContractError(f"decision semantic self-test failed:\n{proc.stdout}")

    print("Furina Engineering Company v4 event-driven policy gate passed")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(f"Furina Engineering Company v4 policy gate failed: {exc}")
        raise SystemExit(1)
