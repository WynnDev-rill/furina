# Furina Decision Audit Policy

## Purpose
Keep Reviewer and Boss decisions durable and inspectable without creating one repository commit per decision.

Issue #42 remains the mutable current-state snapshot. PR conversation comments are the append-only-by-policy decision trail.

## Comment markers
Reviewer decisions use exactly:

`<!-- FURINA_REVIEW_DECISION_V1 -->`

followed by one fenced `json` object conforming to `engineering/review/decision.schema.json`.

Boss decisions use exactly:

`<!-- FURINA_BOSS_DECISION_V1 -->`

followed by one fenced `json` object conforming to `engineering/boss/decision.schema.json`.

## Rules
- Reviewer and Boss decisions are always separate top-level PR comments.
- Never edit/reuse an old decision comment to certify a new head SHA.
- Any new PR head receives fresh Reviewer/Boss records.
- A Boss record must reference the exact cycle IDs and SHA from the accepted Reviewer record.
- Before posting a decision, run `scripts/furina-decision-gate.py`.
- Before merge, run semantic validation again against the current PR head.
- If a comment is malformed, ambiguous, stale, or semantically invalid, treat it as non-existent.
- Do not place credentials, private conversation content, or device-sensitive personal data in decision comments.

GitHub comments are not cryptographically immutable; “append-only” here is a company operating rule. If evidence suggests a decision comment was edited, the safe action is to require a fresh decision for the current head.
