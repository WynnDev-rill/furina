#!/usr/bin/env python3
"""Validate Furina Engineering Company v6 Factory control-plane invariants."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "company": ROOT / "engineering/COMPANY.md",
    "factory": ROOT / "engineering/factory/FACTORY_V2.md",
    "worker": ROOT / "engineering/worker/HOURLY_PROMPT.md",
    "queue_schema": ROOT / "engineering/work-queue/schema.json",
    "queue_state": ROOT / "engineering/work-queue/state.json",
    "work_package": ROOT / "engineering/work-package/POLICY.md",
    "priority": ROOT / "engineering/prioritization/POLICY.md",
    "triage": ROOT / "engineering/triage/CRITICAL_PATH_POLICY.md",
    "separation": ROOT / "engineering/review/INDEPENDENCE_POLICY.md",
    "audit": ROOT / "engineering/decisions/AUDIT_POLICY.md",
    "review_schema": ROOT / "engineering/review/decision.schema.json",
    "device_schema": ROOT / "engineering/evidence/device-report.schema.json",
    "behavioral_schema": ROOT / "engineering/evidence/behavioral-run.schema.json",
    "calibration_schema": ROOT / "engineering/calibration/record.schema.json",
    "boss_policy": ROOT / "engineering/boss/BOSS_POLICY.md",
    "boss_schema": ROOT / "engineering/boss/decision.schema.json",
    "decision_gate": ROOT / "scripts/furina-decision-gate.py",
    "engineering_workflow": ROOT / ".github/workflows/furina-engineering-os.yml",
    "companion_workflow": ROOT / ".github/workflows/companion-quality.yml",
    "vercel": ROOT / "vercel.json",
}
LEGACY_ORCHESTRATOR = ROOT / ".github/workflows/furina-autonomous-gate.yml"


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
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise ContractError(f"{label} missing contract markers: {', '.join(missing)}")


def require_required_fields(label: str, schema: dict, expected: set[str]) -> None:
    actual = set(schema.get("required", []))
    missing = sorted(expected - actual)
    if missing:
        raise ContractError(f"{label} missing required fields: {missing}")


def validate_queue(schema: dict, state: dict) -> None:
    require_required_fields("work-queue/schema.json", schema, {"schemaVersion", "updatedAt", "stagingBaseSha", "items"})
    for key in ("schemaVersion", "updatedAt", "stagingBaseSha", "items"):
        if key not in state:
            raise ContractError(f"work-queue/state.json missing key: {key}")
    if state.get("schemaVersion") != 1:
        raise ContractError("work-queue/state.json schemaVersion must be 1")
    if not isinstance(state.get("items"), list):
        raise ContractError("work-queue/state.json items must be an array")
    valid_statuses = {
        "CANDIDATE", "INTEGRATED", "RELEASED", "BLOCKED_EVIDENCE", "BLOCKED_HUMAN",
        "QUARANTINED", "SUPERSEDED", "REJECTED",
    }
    ids: set[str] = set()
    for item in state["items"]:
        if not isinstance(item, dict):
            raise ContractError("work-queue item must be an object")
        for key in ("id", "status", "baseSha", "headSha", "rollbackBoundary"):
            if not item.get(key):
                raise ContractError(f"work-queue item missing {key}")
        if item["id"] in ids:
            raise ContractError(f"duplicate work-queue id: {item['id']}")
        ids.add(item["id"])
        if item["status"] not in valid_statuses:
            raise ContractError(f"invalid work-queue status: {item['status']}")


def main() -> int:
    if LEGACY_ORCHESTRATOR.exists():
        raise ContractError("legacy external AI autonomous gate must remain removed")

    text = {name: read(path) for name, path in FILES.items() if not name.endswith("_schema") and name != "queue_state"}
    company = text["company"]
    factory = text["factory"]
    worker = text["worker"]
    priority = text["priority"]
    triage = text["triage"]
    separation = text["separation"]
    audit = text["audit"]
    boss = text["boss_policy"]
    work_package = text["work_package"]

    require_all("COMPANY.md", company, [
        "SHIFT_GATED_AUTO_MERGE", "engineering/factory/FACTORY_V2.md", "company/staging",
        "Candidate Reviewer", "Reviewer evidence-reset", "Boss evidence-reset",
        "Stabilize -> Restore -> Optimize -> Polish", "Time shortage cancels the attempt, not the work",
        "RED remains human-authorized and human-merged", "A green build is evidence of build health, not proof of product improvement",
        "STATIC", "CI", "BEHAVIORAL", "DEVICE", "NO_CHANGE",
    ])

    require_all("FACTORY_V2.md", factory, [
        "CANDIDATE", "INTEGRATION", "RELEASE", "EMERGENCY_INTEGRATION", "company/staging",
        "FAST", "MEDIUM", "FULL", "engineering/integration/checkpoints/",
        "one normal release PR per day", "Research sidecars", "no production write or merge authority",
    ])

    require_all("HOURLY_PROMPT.md", worker, [
        "Scheduled Dispatcher", "Asia/Jakarta", "`00` -> `RELEASE`", "`06`, `12`, `18` -> `INTEGRATION`",
        "Acquire a shift lease", "CANDIDATE mode", "INTEGRATION mode", "RELEASE mode",
        "Reviewer evidence-reset pass", "Boss evidence-reset pass", "expected head SHA", "SHIFT_GATED_AUTO_MERGE",
    ])

    require_all("WORK_PACKAGE/POLICY.md", work_package, [
        "engineering/triage/CRITICAL_PATH_POLICY.md", "Critical-path scope boundary", "Candidate Reviewer",
        "Integration boundary", "Release boundary", "evidence-reset", "time is low",
    ])

    require_all("REVIEW/INDEPENDENCE_POLICY.md", separation, [
        "Candidate Reviewer", "not equivalent to independent models", "Evidence-reset rule",
        "reviewCycleId != engineerCycleId", "bossCycleId != engineerCycleId", "SHIFT_GATED_AUTO_MERGE",
        "CANDIDATE and INTEGRATION modes have no merge authority",
    ])

    require_all("TRIAGE/CRITICAL_PATH_POLICY.md", triage, [
        "T0_STOP_THE_LINE", "T1_CRITICAL_PATH", "T2_MAJOR", "T3_LOCAL", "T4_POLISH",
        "Critical-path graph", "dependencyCentrality", "scopeReach",
        "Stabilize -> Restore -> Optimize -> Polish", "highest eligible triage class",
    ])

    require_all("PRIORITIZATION/POLICY.md", priority, [
        "triage class", "P0_PRODUCT", "P0_UNBLOCKER", "P1_PRODUCT", "P2_PRODUCT", "META_ENGINEERING",
        "A lower tier cannot outrank a higher eligible tier", "Critical bottleneck ordering",
        "dependencyCentrality", "scopeReach", "withinTierScore",
    ])

    require_all("DECISIONS/AUDIT_POLICY.md", audit, [
        "FURINA_REVIEW_DECISION_V1", "FURINA_BOSS_DECISION_V1", "phase/provenance IDs",
        "Never edit/reuse an old decision comment", "current PR head",
    ])

    require_all("BOSS_POLICY.md", boss, [
        "same ChatGPT execution", "evidence reset", "SHIFT_GATED_AUTO_MERGE", "REQUEST_REVISION",
        "Time shortage cancels the current attempt, not a valuable PR", "Critical-path test",
        "expected head SHA", "RED remains human-authorized and human-merged",
    ])

    require_all("furina-engineering-os.yml", text["engineering_workflow"], [
        "company/staging", "engineering/integration/checkpoints/**", "work-queue/schema.json", "work-queue/state.json",
    ])
    require_all("companion-quality.yml", text["companion_workflow"], [
        "company/staging", "engineering/integration/checkpoints/**", "companion-quality-gate.py",
    ])

    vercel = read_json(FILES["vercel"])
    deployment_enabled = vercel.get("git", {}).get("deploymentEnabled", {})
    if deployment_enabled.get("company/**") is not False:
        raise ContractError("vercel.json must disable company/** deployments")

    queue_schema = read_json(FILES["queue_schema"])
    queue_state = read_json(FILES["queue_state"])
    validate_queue(queue_schema, queue_state)

    review = read_json(FILES["review_schema"])
    require_required_fields("review/decision.schema.json", review, {
        "pullRequest", "reviewCycleId", "engineerCycleId", "reviewedHeadSha", "verdict",
        "evidenceLevel", "regressionRisk", "scopeCoherence", "simplerAlternative", "reason", "reviewedAt",
    })

    boss_schema = read_json(FILES["boss_schema"])
    require_required_fields("boss/decision.schema.json", boss_schema, {
        "decision", "pullRequest", "headSha", "engineerCycleId", "reviewCycleId", "bossCycleId",
        "reviewedHeadSha", "evidenceLevel", "autonomyClass", "productValue", "regressionRisk",
        "complexityCost", "confidence", "reason", "requiredNextAction", "decidedAt",
    })

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

    print("Furina Engineering Company v6 Factory policy gate passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(f"Furina Engineering Company v6 policy gate failed: {exc}")
        raise SystemExit(1)
