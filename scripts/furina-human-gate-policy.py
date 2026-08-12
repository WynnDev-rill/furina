#!/usr/bin/env python3
"""Fail closed when active scheduled engineering authority drifts away from human-gated mode."""
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
        "Gate 1",
        "Gate 2",
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
        require(phrase.casefold() not in worker.casefold(), f"hourly worker retained legacy write authority: {phrase}")

    require("There is no scheduled auto-merge mode" in policy,
            "policy must explicitly remove scheduled auto-merge authority")
    require("Gate 1 approval is **not merge approval**" in policy,
            "plan approval and merge approval must remain separate")

    print("Human-gated engineering policy passed: scheduled Engineer is read-only; Wynn owns implementation and merge gates")


if __name__ == "__main__":
    main()
