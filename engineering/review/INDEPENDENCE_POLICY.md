# Furina Review Independence Policy

## Purpose
Reviewer and Boss independence must be operational, not role-played. A change may move quickly, but the same model conversation/process that authored a head must not certify that head for merge.

## Execution-context separation
For every GREEN/YELLOW PR head:

1. **Engineer** creates or revises the head. Its provenance is recorded as `engineerCycleId`.
2. **Reviewer** runs in a fresh execution context after required CI for that exact head is green. `reviewCycleId` must differ from `engineerCycleId`.
3. **Boss** runs only after a valid Reviewer `APPROVE` record exists for the same head. `bossCycleId` must differ from both prior IDs.

A separate GitHub Actions job counts as a separate execution context when it:
- starts a fresh process/job;
- performs a new model/API call with a fresh prompt;
- reads primary evidence again;
- does not reuse the Engineer or Reviewer model conversation;
- writes a separate machine-readable decision record.

There is **no minimum wall-clock delay**. If CI completes at 10:07, Reviewer may begin at 10:07. If Reviewer approves at 10:10, Boss may begin immediately afterward.

Fallback scheduled executions remain valid if event-driven orchestration is unavailable, but fixed hourly waiting is not a quality requirement.

## Head-SHA binding
Reviewer and Boss decisions are valid only for the exact PR head SHA they inspected. Any new commit invalidates prior Reviewer/Boss certification for that PR.

Minimum semantic invariants:
- `reviewCycleId != engineerCycleId`
- `bossCycleId != engineerCycleId`
- `bossCycleId != reviewCycleId`
- `reviewedHeadSha == current PR head SHA`
- Boss `headSha == current PR head SHA`
- Boss may approve only when the referenced Reviewer verdict is `APPROVE`

These invariants are not trusted to JSON Schema alone. `scripts/furina-decision-gate.py` must validate them before lifecycle transition or merge.

## Machine-readable audit trail
Reviewer and Boss decisions must be separate top-level PR comments using `engineering/decisions/AUDIT_POLICY.md`. Reviewer records use `FURINA_REVIEW_DECISION_V1`; Boss records use `FURINA_BOSS_DECISION_V1`.

Issue #42 is only the current-state pointer. It is not sufficient as the durable decision trail.

Never edit an old Reviewer/Boss decision comment to make it apply to a new head. A new head receives new decision comments.

## Reviewer contract
Reviewer output conforms to `engineering/review/decision.schema.json` and records:
- pull request
- engineer/reviewer cycle IDs
- exact reviewed head SHA
- verdict
- evidence level
- regression risk
- scope coherence
- simpler alternative
- reason
- timestamp

Reviewer returns exactly one:
`APPROVE`, `REQUEST_CHANGES`, `BLOCKED_HUMAN`, or `NO_CHANGE_RECOMMENDED`.

## Boss prerequisite
Boss must refuse approval when:
- no separate Reviewer record exists;
- Reviewer record is malformed or semantically invalid;
- Reviewer verdict is not `APPROVE`;
- reviewed SHA differs from current head;
- cycle IDs collide;
- required evidence is missing;
- the head changed after Reviewer approval.

Boss output conforms to `engineering/boss/decision.schema.json`.

## Auto-merge boundary
Under `BOSS_GATED_AUTO_MERGE`, only GREEN/YELLOW heads with a semantically valid Reviewer APPROVE and Boss APPROVE_MERGE may be merged automatically. RED remains human-authorized and human-merged.

## Anti-rubber-stamp rule
One response containing “Engineer”, “Reviewer”, and “Boss” sections is one execution, not independent certification. Separate role labels never substitute for separate execution contexts and exact-SHA machine-readable evidence.
