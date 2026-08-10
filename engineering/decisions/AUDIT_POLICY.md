# Furina Decision Audit Policy

## Purpose
Keep Reviewer and Boss decisions durable and inspectable without one repository commit per decision.

Issue #42 remains the mutable current-state snapshot. PR conversation comments are the append-only-by-policy decision trail.

## Comment markers
Reviewer decisions use:

`<!-- FURINA_REVIEW_DECISION_V1 -->`

followed by one fenced JSON object conforming to `engineering/review/decision.schema.json`.

Boss decisions use:

`<!-- FURINA_BOSS_DECISION_V1 -->`

followed by one fenced JSON object conforming to `engineering/boss/decision.schema.json`.

## Rules
- Reviewer and Boss decisions are separate top-level PR comments even when produced inside the same ChatGPT shift.
- Distinct `engineerCycleId`, `reviewCycleId`, and `bossCycleId` are phase/provenance IDs. They do not claim independent models.
- Never edit/reuse an old decision comment to certify a new head SHA.
- Any new PR head receives fresh Reviewer/Boss records.
- Boss record must reference the exact phase IDs and SHA from the accepted Reviewer record.
- Before posting a decision, validate the record semantics with `scripts/furina-decision-gate.py` when executable validation is available; in tool-only execution, apply the same deterministic invariants explicitly.
- Immediately before merge, revalidate against the current PR head and current CI state.
- Malformed, ambiguous, stale, or semantically invalid comments are treated as non-existent.
- Never place credentials, private conversation content, or sensitive device data in decision comments.

GitHub comments are not cryptographically immutable. “Append-only” is an operating rule. Evidence that an old record changed requires a fresh decision for the current head.
