#!/usr/bin/env python3
"""Validate Furina Engineering Company v6 Factory control-plane invariants."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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
    haystack = text.casefold()
    missing = [needle for needle in needles if needle.casefold() not in haystack]
    if missing:
        raise ContractError(f"{label} missing contract markers: {', '.join(missing)}")


def require_required_fields(label: str, schema: dict, expected: set[str]) -> None:
    actual = set(schema.get("required", []))
    missing = sorted(expected - actual)
    if missing:
        raise ContractError(f"{label} missing required fields: {missing}")


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ContractError(f"unsupported work-queue schema type: {expected}")


def _validate_datetime(value: str, path: str) -> None:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ContractError(f"{path} must be ISO-8601 date-time: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{path} date-time must include timezone: {value!r}")


def validate_schema_value(value: Any, schema: dict, path: str) -> None:
    """Dependency-free validator for the JSON-Schema subset used by the work queue."""
    if "const" in schema and value != schema["const"]:
        raise ContractError(f"{path} must equal {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path} has invalid value {value!r}; expected one of {schema['enum']!r}")

    declared_type = schema.get("type")
    if declared_type is not None:
        allowed = declared_type if isinstance(declared_type, list) else [declared_type]
        if not any(_type_matches(value, expected) for expected in allowed):
            raise ContractError(f"{path} has wrong type; expected {allowed!r}, got {type(value).__name__}")

    if value is None:
        return

    if isinstance(value, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(value) < min_length:
            raise ContractError(f"{path} must have at least {min_length} characters")
        pattern = schema.get("pattern")
        if pattern is not None and re.fullmatch(pattern, value) is None:
            raise ContractError(f"{path} does not match required pattern {pattern!r}: {value!r}")
        if schema.get("format") == "date-time":
            _validate_datetime(value, path)

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ContractError(f"{path} missing required fields: {missing}")
        properties = schema.get("properties", {})
        for key, child_schema in properties.items():
            if key in value:
                validate_schema_value(value[key], child_schema, f"{path}.{key}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ContractError(f"{path} has unsupported fields: {unknown}")

    if isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for index, item in enumerate(value):
            validate_schema_value(item, item_schema, f"{path}[{index}]")


def validate_queue(schema: dict, state: dict) -> None:
    expected_top = {"schemaVersion", "updatedAt", "stagingBaseSha", "items"}
    expected_item = {
        "id", "createdAt", "shiftId", "title", "subsystem", "triageClass",
        "strategicTier", "autonomyClass", "status", "baseSha", "headSha",
        "validationTier", "evidenceLevel", "dependencies", "conflictsWith",
        "rollbackBoundary", "expectedMetric", "expectedDelta", "verificationWindow",
    }
    require_required_fields("work-queue/schema.json", schema, expected_top)
    item_schema = schema.get("properties", {}).get("items", {}).get("items", {})
    require_required_fields("work-queue item schema", item_schema, expected_item)
    validate_schema_value(state, schema, "work-queue/state.json")

    ids: set[str] = set()
    for index, item in enumerate(state.get("items", [])):
        item_id = item["id"]
        if item_id in ids:
            raise ContractError(f"duplicate work-queue id: {item_id}")
        ids.add(item_id)
        if item_id in item.get("dependencies", []):
            raise ContractError(f"work-queue item {item_id} cannot depend on itself")
        if item_id in item.get("conflictsWith", []):
            raise ContractError(f"work-queue item {item_id} cannot conflict with itself")
        overlap = sorted(set(item.get("dependencies", [])) & set(item.get("conflictsWith", [])))
        if overlap:
            raise ContractError(f"work-queue item {item_id} both depends on and conflicts with: {overlap}")


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
        "One normal release PR per day", "Research sidecars", "no production write or merge authority",
        "canonical mutable work queue",
    ])

    require_all("HOURLY_PROMPT.md", worker, [
        "Scheduled Dispatcher", "Asia/Jakarta", "`00` -> `RELEASE`", "`06`, `12`, `18` -> `INTEGRATION`",
        "Acquire a shift lease", "CANDIDATE mode", "INTEGRATION mode", "RELEASE mode",
        "Reviewer evidence-reset pass", "Boss evidence-reset pass", "expected head SHA", "SHIFT_GATED_AUTO_MERGE",
        "canonical mutable copy is always read from `company/staging`",
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
