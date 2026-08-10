#!/usr/bin/env python3
"""Deterministic semantic validation for Furina Reviewer/Boss decisions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_SCHEMA = ROOT / "engineering/review/decision.schema.json"
BOSS_SCHEMA = ROOT / "engineering/boss/decision.schema.json"

REVIEW_VERDICTS = {"APPROVE", "REQUEST_CHANGES", "BLOCKED_HUMAN", "NO_CHANGE_RECOMMENDED"}
BOSS_DECISIONS = {"APPROVE_MERGE", "REJECT_CLOSE", "REQUEST_REVISION", "BLOCKED_HUMAN"}
EVIDENCE = {"STATIC", "CI", "BEHAVIORAL", "DEVICE"}
AUTONOMY = {"GREEN", "YELLOW", "RED"}

class DecisionError(RuntimeError):
    pass

def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DecisionError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DecisionError(f"{path} must contain a JSON object")
    return value

def schema_required(path: Path) -> set[str]:
    return set(load_json(path).get("required", []))

def require_fields(label: str, obj: dict, required: set[str]) -> None:
    missing = sorted(required - set(obj))
    if missing:
        raise DecisionError(f"{label} missing fields: {', '.join(missing)}")

def validate_review(review: dict, *, expected_head: str, expected_engineer_cycle: str | None = None,
                    expected_pr: int | None = None) -> None:
    require_fields("review", review, schema_required(REVIEW_SCHEMA))
    if review["verdict"] not in REVIEW_VERDICTS:
        raise DecisionError(f"invalid reviewer verdict: {review['verdict']}")
    if review["evidenceLevel"] not in EVIDENCE:
        raise DecisionError(f"invalid reviewer evidence level: {review['evidenceLevel']}")
    if review["reviewCycleId"] == review["engineerCycleId"]:
        raise DecisionError("reviewCycleId must differ from engineerCycleId")
    if expected_engineer_cycle is not None and review["engineerCycleId"] != expected_engineer_cycle:
        raise DecisionError("review engineerCycleId does not match expected Engineer provenance")
    if review["reviewedHeadSha"].lower() != expected_head.lower():
        raise DecisionError("reviewedHeadSha does not match current PR head")
    if expected_pr is not None and review["pullRequest"] != expected_pr:
        raise DecisionError("review pullRequest does not match expected PR")
    for field in ("regressionRisk", "scopeCoherence"):
        value = review[field]
        if not isinstance(value, (int, float)) or not 0 <= value <= 10:
            raise DecisionError(f"{field} must be a number from 0 to 10")

def validate_boss(boss: dict, review: dict, *, expected_head: str,
                  expected_engineer_cycle: str | None = None, expected_pr: int | None = None) -> None:
    validate_review(
        review,
        expected_head=expected_head,
        expected_engineer_cycle=expected_engineer_cycle,
        expected_pr=expected_pr,
    )
    require_fields("boss", boss, schema_required(BOSS_SCHEMA))
    if review["verdict"] != "APPROVE":
        raise DecisionError("Boss may decide merge only after Reviewer APPROVE")
    if boss["decision"] not in BOSS_DECISIONS:
        raise DecisionError(f"invalid Boss decision: {boss['decision']}")
    if boss["evidenceLevel"] not in EVIDENCE:
        raise DecisionError(f"invalid Boss evidence level: {boss['evidenceLevel']}")
    if boss["autonomyClass"] not in AUTONOMY:
        raise DecisionError(f"invalid autonomyClass: {boss['autonomyClass']}")
    if boss["engineerCycleId"] != review["engineerCycleId"]:
        raise DecisionError("Boss engineerCycleId does not match Reviewer record")
    if boss["reviewCycleId"] != review["reviewCycleId"]:
        raise DecisionError("Boss reviewCycleId does not match Reviewer record")
    if boss["bossCycleId"] in {boss["engineerCycleId"], boss["reviewCycleId"]}:
        raise DecisionError("bossCycleId must differ from Engineer and Reviewer cycle IDs")
    if boss["reviewedHeadSha"].lower() != expected_head.lower():
        raise DecisionError("Boss reviewedHeadSha does not match current PR head")
    if boss["headSha"].lower() != expected_head.lower():
        raise DecisionError("Boss headSha does not match current PR head")
    if boss["pullRequest"] != review["pullRequest"]:
        raise DecisionError("Boss pullRequest does not match Reviewer record")
    if expected_pr is not None and boss["pullRequest"] != expected_pr:
        raise DecisionError("Boss pullRequest does not match expected PR")
    for field in ("productValue", "regressionRisk", "complexityCost", "confidence"):
        value = boss[field]
        if not isinstance(value, (int, float)) or not 0 <= value <= 10:
            raise DecisionError(f"{field} must be a number from 0 to 10")
    if boss["decision"] == "APPROVE_MERGE" and boss["autonomyClass"] == "RED":
        raise DecisionError("RED work cannot receive autonomous APPROVE_MERGE")

def self_test() -> None:
    head = "a" * 40
    other = "b" * 40
    review = {
        "pullRequest": 47,
        "reviewCycleId": "gha-100-reviewer",
        "engineerCycleId": "engineer-head-aaaa",
        "reviewedHeadSha": head,
        "verdict": "APPROVE",
        "evidenceLevel": "CI",
        "regressionRisk": 2,
        "scopeCoherence": 9,
        "simplerAlternative": None,
        "reason": "valid",
        "reviewedAt": "2026-08-11T00:00:00Z",
    }
    boss = {
        "decision": "APPROVE_MERGE",
        "pullRequest": 47,
        "headSha": head,
        "engineerCycleId": review["engineerCycleId"],
        "reviewCycleId": review["reviewCycleId"],
        "bossCycleId": "gha-100-boss",
        "reviewedHeadSha": head,
        "evidenceLevel": "CI",
        "autonomyClass": "YELLOW",
        "productValue": 8,
        "regressionRisk": 2,
        "complexityCost": 2,
        "confidence": 8,
        "reason": "valid",
        "requiredNextAction": "merge exact head",
        "decidedAt": "2026-08-11T00:01:00Z",
    }
    validate_review(review, expected_head=head, expected_engineer_cycle=review["engineerCycleId"], expected_pr=47)
    validate_boss(boss, review, expected_head=head, expected_engineer_cycle=review["engineerCycleId"], expected_pr=47)

    def must_fail(fn, name: str) -> None:
        try:
            fn()
        except DecisionError:
            return
        raise DecisionError(f"self-test expected failure did not occur: {name}")

    bad = dict(review)
    bad["reviewCycleId"] = bad["engineerCycleId"]
    must_fail(lambda: validate_review(bad, expected_head=head), "same-cycle reviewer")

    bad = dict(review)
    bad["reviewedHeadSha"] = other
    must_fail(lambda: validate_review(bad, expected_head=head), "stale reviewer SHA")

    badboss = dict(boss)
    badboss["bossCycleId"] = badboss["reviewCycleId"]
    must_fail(lambda: validate_boss(badboss, review, expected_head=head), "same-cycle boss")

    badreview = dict(review)
    badreview["verdict"] = "REQUEST_CHANGES"
    must_fail(lambda: validate_boss(boss, badreview, expected_head=head), "boss after non-approve reviewer")

    badboss = dict(boss)
    badboss["headSha"] = other
    must_fail(lambda: validate_boss(badboss, review, expected_head=head), "boss head mismatch")

    badboss = dict(boss)
    badboss["autonomyClass"] = "RED"
    must_fail(lambda: validate_boss(badboss, review, expected_head=head), "RED auto-merge")

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("self-test")

    review_p = sub.add_parser("review")
    review_p.add_argument("--decision", required=True, type=Path)
    review_p.add_argument("--expected-head", required=True)
    review_p.add_argument("--engineer-cycle")
    review_p.add_argument("--pr", type=int)

    boss_p = sub.add_parser("boss")
    boss_p.add_argument("--decision", required=True, type=Path)
    boss_p.add_argument("--review", required=True, type=Path)
    boss_p.add_argument("--expected-head", required=True)
    boss_p.add_argument("--engineer-cycle")
    boss_p.add_argument("--pr", type=int)

    args = parser.parse_args()

    if args.command == "self-test":
        self_test()
        print("Furina decision semantic self-test passed")
        return 0

    if args.command == "review":
        validate_review(
            load_json(args.decision),
            expected_head=args.expected_head,
            expected_engineer_cycle=args.engineer_cycle,
            expected_pr=args.pr,
        )
        print("Furina Reviewer decision semantic validation passed")
        return 0

    validate_boss(
        load_json(args.decision),
        load_json(args.review),
        expected_head=args.expected_head,
        expected_engineer_cycle=args.engineer_cycle,
        expected_pr=args.pr,
    )
    print("Furina Boss decision semantic validation passed")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DecisionError as exc:
        print(f"Furina decision semantic validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
