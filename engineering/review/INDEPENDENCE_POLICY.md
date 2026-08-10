# Furina Review Independence Policy

## Purpose
Reviewer and Boss independence must be operational, not merely role-played inside one execution. The same scheduled execution that authored a change must not also certify that change for merge.

## Execution-context separation
For every GREEN/YELLOW PR:

1. **Engineer phase** — one execution may select, implement, test, and update the PR. It must finish by setting lifecycle to `testing` or `blocked_human`. It may not emit Reviewer approval or a Boss decision for code it authored in that execution.
2. **Reviewer phase** — a later scheduled execution with a different `cycleId` must inspect the diff and evidence from primary sources. It may return `APPROVE`, `REQUEST_CHANGES`, `BLOCKED_HUMAN`, or `NO_CHANGE_RECOMMENDED`. It must record `reviewCycleId` and `reviewedHeadSha`.
3. **Boss phase** — a still later scheduled execution with a third `cycleId` may run only after an independent Reviewer event exists for the exact current head SHA. It must inspect primary evidence again and record `bossCycleId`.

A single execution may reconcile old decisions, but it may not create an Engineer result, Reviewer approval, and Boss approval for the same head SHA in one cycle.

## Head-SHA binding
Reviewer and Boss decisions are valid only for the exact PR head SHA they inspected. Any new commit invalidates both previous Reviewer and Boss approval for that PR and returns it to `testing` until a later cycle reviews the new head.

## Minimum separation
`reviewCycleId` must differ from `engineerCycleId`.
`bossCycleId` must differ from both `engineerCycleId` and `reviewCycleId`.

The separation is about fresh execution context, not elapsed wall-clock time. Hourly cadence naturally provides this without artificial delays.

## Reviewer output
The Reviewer record must include:
- `reviewCycleId`
- `reviewedHeadSha`
- `verdict`
- `evidenceLevel`
- `regressionRisk`
- `scopeCoherence`
- `simplerAlternative`
- `reason`

## Boss prerequisite
The Boss must refuse to decide and leave the PR in `testing` when:
- no independent Reviewer record exists;
- the Reviewer inspected a different head SHA;
- the Reviewer was produced by the Engineer cycle;
- required evidence for the product claim is missing.

## Anti-rubber-stamp rule
Role labels inside one model response are not independent review. Independence requires separate scheduled executions and SHA-bound records.
