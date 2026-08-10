#!/usr/bin/env python3
"""Validate the Furina Engineering Company operating contract.

This is intentionally deterministic. It verifies that the autonomous worker cannot
silently lose the anti-stall lifecycle, evidence policy, or review-gated merge rule.
It does not claim to evaluate Furina model behavior.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "engineering/COMPANY.md"
WORKER = ROOT / "engineering/worker/HOURLY_PROMPT.md"
DEVICE_SCHEMA = ROOT / "engineering/evidence/device-report.schema.json"


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
            "ready_for_merge",
            "new commit, CI result, behavioral/model-output evidence, device report, or human decision",
            "A `blocked_human` PR with no new evidence must not consume another cycle",
            "Never auto-merge",
            "STATIC, CI, BEHAVIORAL, or DEVICE",
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

    print("Furina Engineering Company v2 policy gate passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(f"Furina Engineering Company v2 policy gate failed: {error}")
        raise SystemExit(1)
