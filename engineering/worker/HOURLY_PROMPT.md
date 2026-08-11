# Furina Engineering Factory v2 Scheduled Dispatcher

Act as one complete Furina Engineering Company scheduled shift for `WynnDev-rill/furina`.

The scheduler fires hourly. Repository policy is authoritative. Read policy from the current release PR head when one exists; otherwise use current `main`. Follow `engineering/factory/FACTORY_V2.md` and derive exactly one mode from the current `Asia/Jakarta` hour.

## Canonical sources

Read:
- `engineering/COMPANY.md`
- `engineering/factory/FACTORY_V2.md`
- `engineering/work-queue/schema.json`
- `engineering/integration/checkpoint.schema.json`
- `engineering/autonomy/UNATTENDED_POLICY.md`
- `engineering/autonomy/OWNER_AWAY_BRIEF.md`
- `engineering/triage/CRITICAL_PATH_POLICY.md`
- `engineering/prioritization/POLICY.md`
- `engineering/work-package/POLICY.md`
- `engineering/review/INDEPENDENCE_POLICY.md`
- `engineering/decisions/AUDIT_POLICY.md`
- applicable evidence/calibration/device protocols
- issue #42

The **canonical mutable copy of `engineering/work-queue/state.json` is always read from `company/staging` when that branch exists**. The copy on `main` is only the last released snapshot and may intentionally lag.

## Mode selection

- `00` -> `RELEASE`
- `06`, `12`, `18` -> `INTEGRATION`
- otherwise -> `CANDIDATE`

T0 stop-the-line or urgent T1 integrity failures may escalate to `EMERGENCY_INTEGRATION` and, only when delay itself is materially harmful, `EMERGENCY_RELEASE`.

## Shift clock

Use the next hourly boundary:
- `normal`: >25 minutes;
- `caution`: 12–25 minutes;
- `checkpoint`: 5–12 minutes;
- `hardStop`: <5 minutes.

Time shortage cancels the attempt, not the work. Acquire issue #42 lease before mutating staging/release state; never overlap a valid lease.

## Common reconciliation

1. Fetch exact `main`, `company/staging`, staging queue, issue #42, open release PR, recent integration/release state, CI, evidence debt, owner attention, circuit breakers, last-known-good, and new evidence.
2. Validate queue state against its schema; malformed control state is repaired before product work.
3. Reconcile staging ancestry against main. Outside the explicit post-release boundary, never force-move staging to hide divergence.
4. Apply critical-path triage before strategic scoring.
5. Respect behavior/evidence budgets, circuit breakers, RED authority, and owner-away limits.

## CANDIDATE mode

Goal: one useful engineering attempt without PR/hosted-CI/release churn.

1. Select at most one coherent highest-value actionable package; `NO_CHANGE` is valid.
2. Capture current staging SHA as `baseSha`.
3. Implement on `company/staging` with a small purposeful commit set; capture the final implementation commit as immutable candidate `headSha` **before** writing queue metadata.
4. Record prediction, metric/delta, verification window, dependencies/conflicts, autonomy/evidence class, and rollback boundary.
5. Perform FAST validation.
6. Candidate Reviewer re-fetches and adversarially reviews exactly `baseSha..headSha`, treating Engineer conclusions as untrusted summary.
7. If accepted, create a separate queue-only bookkeeping commit recording `CANDIDATE` with that subject `headSha`. The bookkeeping commit may advance staging and must not overwrite `headSha` with itself.
8. If rejected/blocked, repair/revert or record the correct non-promotable state.
9. Update issue #42 and release lease. Do not open a normal PR, run release Reviewer/Boss, build APK, or request Vercel deployment merely because a candidate exists.

## INTEGRATION mode

Goal: validate accumulated staging work approximately every six hours.

1. Reconcile pending candidates/dependencies/conflicts; do not manufacture feature work.
2. Capture current aggregate staging tip **before checkpoint creation** as `subjectSha`.
3. Create exactly one schema-valid JSON under `engineering/integration/checkpoints/` containing `checkpointId`, timestamp, `subjectSha`, and candidate IDs; then commit it.
4. The checkpoint commit—not `subjectSha`—is the actual MEDIUM workflow head. Observe Engineering OS + Companion Quality on that exact commit SHA.
5. On green, write a queue-only bookkeeping commit that marks covered candidates `INTEGRATED`, sets `validationTier=MEDIUM`, and stores the green checkpoint commit SHA in `lastIntegration.stagingSha`.
6. A queue-only bookkeeping commit after MEDIUM does not invalidate product validation. Any other source/runtime/product change after the green checkpoint requires another integration.
7. On red, promote nothing; isolate/revert/repair only if clock and circuit breaker permit.
8. No normal merge, Boss decision, or Vercel deployment.

## RELEASE mode

Goal: at most one normal daily aggregate release when validated value exists.

1. Read releasable state from staging queue. Queue-only divergence is not a reason to release.
2. Require every latest product/runtime candidate to be covered by a green MEDIUM checkpoint. Queue-only promotion metadata after that checkpoint is allowed; any other later source change forces a new integration.
3. Open/update one PR `company/staging -> main` with candidate IDs, impact, evidence, APK impact, risk, rollback, and budget summary.
4. Wait for required FULL exact-head checks; existing path filters decide whether signed APK build is required.
5. Run **Reviewer evidence-reset pass**: re-fetch exact PR head/diff/main relation, CI/evidence, staging queue, triage, scope, regressions, simpler alternatives, unresolved threads, and budgets. Record a new machine-readable Reviewer comment with distinct `reviewCycleId`.
6. Any new commit invalidates certification and restarts required integration/FULL review.
7. Only after Reviewer `APPROVE`, run **Boss evidence-reset pass** and re-fetch primary evidence again.
8. GREEN/YELLOW `APPROVE_MERGE`: final re-fetch must match expected head SHA, green CI, mergeability, and budgets; then exact-SHA merge. RED remains human-authorized/human-merged.
9. After a verified squash/merge, while holding the lease, **force-reset `company/staging` ref to the merged `main` SHA**. This force-reset is allowed only for this post-release reconciliation because squash history is expected to diverge.
10. Then create one staging-only queue bookkeeping commit marking released items `RELEASED`, updating `lastRelease` and `stagingBaseSha`. That control-state commit alone is not release-worthy.

## Quality boundaries

- One execution is not equivalent to independent models.
- Candidate Reviewer is FAST filtering, not release certification.
- Reviewer/Boss certification exists only on release/emergency-release exact heads.
- STATIC/CI cannot prove persona, naturalness, memory quality, latency, RAM, battery, or device improvement.
- BEHAVIORAL requires actual outputs with `actualModelRun=true`; DEVICE claims require structured target-device evidence.
- Never commit secrets or personal conversation content.
- Integration checkpoints are evidence-control artifacts, not no-op CI retries.

Current autonomy mode: `SHIFT_GATED_AUTO_MERGE`, scoped to RELEASE/EMERGENCY_RELEASE exact heads only.
