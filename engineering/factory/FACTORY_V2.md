# Furina Engineering Factory v2

## Purpose

Factory v2 separates **thinking/work frequency** from **integration/release frequency**. Furina may receive one high-value engineering attempt every hour without turning every attempt into a pull request, hosted-CI run, APK build, merge, or Vercel deployment.

Repository product/evidence policy remains authoritative. This document controls cadence and promotion.

## Core invariant

**One production writer, many possible intelligence inputs.**

- `company/staging` is the single unattended production-writing branch.
- Only one scheduled shift may mutate `company/staging` at a time; issue #42 lease remains mandatory.
- Parallel research/intelligence work may produce evidence, proposals, benchmarks, or hypotheses, but it has no production write or merge authority.
- `main` changes only through a release PR from `company/staging`, except an explicitly authorized emergency/human path.

## Jakarta schedule modes

The hourly scheduler runs every hour in `Asia/Jakarta` and derives exactly one mode from the local hour:
- `00`: **RELEASE** — final integration, full release validation, Reviewer, Boss, and eligible merge.
- `06`, `12`, `18`: **INTEGRATION** — aggregate validation only; normally no release to `main`.
- all other hours: **CANDIDATE** — one coherent work package or `NO_CHANGE`.

A T0 stop-the-line or urgent T1 repair may escalate to `EMERGENCY_INTEGRATION` and, only when waiting would materially worsen user/data/release integrity, `EMERGENCY_RELEASE`. Record the reason in issue #42 and queue state.

## Branch and deployment model

- `main`: released source of truth and last released queue snapshot.
- `company/staging`: accumulated accepted candidate work plus the **canonical mutable work queue**.
- `company/**`, `integration/**`, `research/**`: Vercel deployment disabled by `vercel.json`.
- Candidate work does not open a normal PR.
- Integration checkpoints do not merge to `main`.
- One normal release PR per day is the target ceiling, not a required output.

## Work queue SHA semantics

Canonical mutable state is `engineering/work-queue/state.json` on `company/staging`; the copy on `main` may lag between releases.

Queue item SHA fields are deliberately non-self-referential:
- `baseSha`: staging SHA immediately before implementation begins.
- `headSha`: exact **implementation subject SHA** reviewed by Candidate Reviewer, captured before the queue bookkeeping commit that records the item.
- a later queue-only bookkeeping commit may advance staging without changing the candidate `headSha`.

Statuses: `CANDIDATE`, `INTEGRATED`, `RELEASED`, `BLOCKED_EVIDENCE`, `BLOCKED_HUMAN`, `QUARANTINED`, `SUPERSEDED`, `REJECTED`.

## Validation tiers

### FAST — candidate
Use source inspection, syntax/schema reasoning, targeted deterministic checks, dependency/conflict inspection, and exact implementation diff review. FAST is not behavioral/device proof.

### MEDIUM — integration
Integration writes one JSON checkpoint under `engineering/integration/checkpoints/`, validated against `engineering/integration/checkpoint.schema.json`.

Checkpoint SHA semantics:
1. capture current aggregate staging tip as `subjectSha` **before** creating the checkpoint commit;
2. write `subjectSha` + candidate IDs into the checkpoint JSON;
3. commit the checkpoint; this new commit becomes the actual workflow head;
4. Engineering OS + Companion Quality validate that exact checkpoint commit;
5. after success, a queue-only bookkeeping commit records the actual validated checkpoint commit SHA in `lastIntegration.stagingSha` and promotes covered candidates to `INTEGRATED`.

The bookkeeping commit after green MEDIUM does not invalidate the product validation when its diff is restricted to the canonical queue state. Any product/runtime/source change after the validated checkpoint requires another integration before release.

### FULL — release
Release opens/updates one PR from `company/staging` to `main`. PR-triggered workflows certify the final head, including signed APK build when runtime/build path filters require it. Reviewer and Boss bind to the exact PR head SHA.

## Candidate mode

1. Acquire issue #42 lease and reconcile `main`, `company/staging`, staging queue, evidence debt, budgets, circuit breakers, and new evidence.
2. Repair unexpected staging/main ancestry before new product work.
3. Select at most one coherent highest-value actionable package; `NO_CHANGE` is valid.
4. Record `baseSha`, implement on staging, then capture the resulting implementation commit as the candidate `headSha`.
5. Perform FAST validation.
6. Candidate Reviewer re-fetches and reviews exactly `baseSha..headSha`, ignoring Engineer conclusions as untrusted summary.
7. If accepted, write a separate queue bookkeeping commit recording `CANDIDATE` and that immutable subject `headSha`; if rejected/blocked, repair/revert or record the appropriate non-promotable state.
8. Update issue #42 and release lease. No normal PR, hosted CI, APK build, or Vercel deployment.

## Integration mode

1. Acquire lease; reconcile exact main, staging, staging queue, and previous integration result.
2. Do not manufacture feature work merely to fill the integration hour.
3. Resolve obvious dependency/conflict/supersession issues first.
4. Capture the current aggregate staging tip as checkpoint `subjectSha`.
5. Create one schema-valid checkpoint JSON with `subjectSha` and candidate IDs, then commit it.
6. Observe MEDIUM workflows for the **checkpoint commit SHA**, not the pre-checkpoint `subjectSha`.
7. On green, write a queue-only bookkeeping commit: promote covered candidates to `INTEGRATED`, set `validationTier=MEDIUM`, and set `lastIntegration.stagingSha` to the actual green checkpoint commit SHA. On red, promote nothing.
8. No normal merge to `main`, Boss decision, or Vercel deployment.

## Release mode

1. Acquire lease and read releasable state from the staging queue.
2. If there is no release-worthy integrated product work, record `NO_CHANGE`; queue-only divergence is not a release reason.
3. Require the latest product/runtime changes to be covered by green MEDIUM. Queue-only bookkeeping after that checkpoint is allowed; any other source change requires a new checkpoint.
4. Open/update one release PR `company/staging -> main` with candidate IDs, product impact, evidence, APK impact, risk, and rollback boundaries.
5. Wait for required FULL exact-head checks.
6. Reviewer evidence-reset re-fetches exact head/diff/main relationship/evidence/budgets and records its machine-readable decision.
7. Only after Reviewer `APPROVE`, Boss performs an independent evidence reset.
8. GREEN/YELLOW `APPROVE_MERGE` may exact-SHA merge only after final head/CI/mergeability/budget checks. RED remains human-authorized and human-merged.
9. A normal release may use squash merge. After verified merge and while holding the lease, **force-reset `company/staging` ref to the merged `main` SHA**; this force move is allowed only at this post-release reconciliation boundary because squash history is expected to diverge.
10. Then write one staging-only queue bookkeeping commit that marks included items `RELEASED`, updates `lastRelease` and `stagingBaseSha`, and remains outside normal release eligibility by itself.

## Candidate accumulation safety

- no candidate knowingly depends on a broken prior candidate;
- integration failure blocks release of the affected aggregate;
- later repair dependencies must be explicit;
- superseded candidates remain auditable but do not count as product value;
- destructive/RED work is never silently accumulated;
- queue/checkpoint bookkeeping commits are control state, not product improvement claims.

## Research sidecars

Research sidecars may inspect primary/official sources, model/runtime alternatives, UX patterns, behavioral evidence, or performance hypotheses. They write proposals/evidence only and have no production write/merge authority.

## Cost-control rules

- Candidate: no PR, normal hosted CI, APK build, or Vercel deployment.
- Integration: deliberate MEDIUM checks only on checkpoint commits.
- Release: FULL PR CI and APK build only when relevant; normal main delivery at most once daily.
- APK path filters remain limited to runtime/build-affecting inputs; generic control-plane `scripts/**` changes alone must not rebuild APK.
- No no-op commits to burn CI. Checkpoints are explicit evidence-control artifacts.
- External quota/provider failures are recorded and rechecked rather than treated as code defects.

## Success metric

Optimize released product quality and decision quality per unit of time/CI/deployment budget. Do not optimize commit, candidate, PR, merge, or scheduled-run count.
