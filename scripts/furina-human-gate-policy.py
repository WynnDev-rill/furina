#!/usr/bin/env python3
"""Fail closed when active scheduled engineering authority drifts away from Wynn-gated mode."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "engineering/HUMAN_GATE_POLICY.md"
WORKER = ROOT / "engineering/worker/HOURLY_PROMPT.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"HUMAN GATE POLICY FAILED: {message}")


def main() -> None:
    policy = POLICY.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")

    for marker in (
        "Wynn is the sole authority",
        "at least 5 distinct new or materially changed MEDIUM-to-HIGH value findings",
        "AWAITING WYNN APPROVAL",
        "Single-approval implementation flow",
        "implementation approval and merge approval",
        "There is no scheduled auto-merge mode",
        "company/staging` from Factory v2 is legacy state",
    ):
        require(marker.casefold() in policy.casefold(), f"active policy missing marker: {marker}")

    for marker in (
        "read-only Furina Engineer",
        "HUMAN_GATE_POLICY.md",
        "Wynn is the sole Reviewer/Boss",
        "Never modify files",
        "at least **5 distinct NEW or materially changed MEDIUM-to-HIGH value findings**",
        "AWAITING WYNN APPROVAL",
        "Do nothing automatically",
        "No second merge approval is required",
    ):
        require(marker.casefold() in worker.casefold(), f"hourly worker missing marker: {marker}")

    forbidden_worker_authority = (
        "then exact-sha merge",
        "may immediately auto-merge",
        "goal: one useful engineering attempt",
        "implement on `company/staging`",
        "force-reset `company/staging`",
    )
    for phrase in forbidden_worker_authority:
        require(phrase.casefold() not in worker.casefold(), f"hourly worker retained legacy scheduled write authority: {phrase}")

    require("There is no scheduled auto-merge mode" in policy,
            "scheduled policy must explicitly remove unattended auto-merge authority")
    require("Wynn approval is therefore **implementation approval and merge approval for the approved scope**" in policy,
            "one explicit Wynn approval must authorize both implementation and in-scope merge")
    require("No second merge approval is required for the same approved scope" in worker,
            "interactive flow must not require a second Wynn approval")
    require("Scheduled Engineer authority never changes" in worker,
            "scheduled Engineer must remain read-only after interactive approval")

    print("Human-gated engineering policy passed: scheduled Engineer is read-only; one Wynn approval authorizes validated in-scope implementation and merge")


if __name__ == "__main__":
    main()
