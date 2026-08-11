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

A T0 stop-the-line or urgent T1 repair may escalate to an **EMERGENCY_INTEGRATION** and, only when waiting would materially worsen user/data/release integrity, **EMERGENCY_RELEASE**. Emergency use must be recorded in issue #42 and the work queue.

## Branch and deployment model

- `main`: released source of truth.
- `company/staging`: accumulated accepted candidate work awaiting integration/release.
- `company/**`, `integration/**`, `research/**`: Vercel deployment disabled by `vercel.json`.
- Normal candidate work does **not** open a PR.
- Integration checkpoints do **not** merge to `main`.
- One normal release PR per day is the target ceiling, not a required output.

## Machine-readable work queue

Canonical state: `engineering/work-queue/state.json` validated by `engineering/work-queue/schema.json`.

Statuses:

- `CANDIDATE`: accepted by the hourly candidate review but not yet aggregate-validated.
- `INTEGRATED`: included in an exact `company/staging` head that passed MEDIUM integration validation.
- `RELEASED`: present in merged `main` after exact-head release gates.
- `BLOCKED_EVIDENCE`, `BLOCKED_HUMAN`, `QUARANTINED`, `SUPERSEDED`, `REJECTED`: non-promotable states with explicit reasons.

Every accepted package records its base/head SHA, subsystem, triage/tier, risk class, prediction, rollback boundary, dependencies/conflicts, and verification state.

## Validation tiers

### FAST — candidate shift

Purpose: reject obviously bad work without hosted CI churn.

Use the cheapest evidence appropriate to the package: source inspection, syntax/schema reasoning, targeted deterministic checks that can be executed without opening a PR, dependency/conflict inspection, and exact-diff review. FAST is never described as behavioral/device proof.

A candidate may remain accepted with higher evidence debt only when repository policy allows that debt and its risk budget remains eligible.

### MEDIUM — integration shift

Purpose: validate the aggregate `company/staging` head every ~6 hours.

The integration shift writes a checkpoint JSON under `engineering/integration/checkpoints/`. That push is the deliberate trigger for:

- Furina Engineering OS;
- Furina Companion Quality Gate.

These workflows check out the latest staging head, so the checkpoint validates all accumulated candidate work, not just the marker file.

MEDIUM success promotes included `CANDIDATE` items to `INTEGRATED`. Failure promotes nothing; isolate/revert/repair the failing aggregate before release.

### FULL — release shift

Purpose: certify the exact release PR head.

Release opens or updates one PR from `company/staging` to `main`. Existing PR-triggered workflows provide the required full validation set, including signed APK build when its path filters require it. Reviewer and Boss evidence-reset passes bind to the exact PR head SHA. GREEN/YELLOW may merge only when every repository gate and unattended budget remains eligible. RED remains human-authorized and human-merged.

## Candidate mode

1. Acquire issue #42 lease and reconcile `main`, `company/staging`, queue, open release PR, evidence debt, owner attention, budgets, circuit breakers, and new evidence.
2. If staging is behind/diverged from `main`, repair that control-plane state before new work.
3. Apply critical-path triage and select at most one coherent package. `NO_CHANGE` is valid.
4. Implement directly on `company/staging` with a small purposeful commit set.
5. Perform FAST validation.
6. Run a **Candidate Reviewer** pass: re-fetch the exact staging diff introduced by this shift and try to falsify the implementation, scope, dependency, regression, and rollback claims. This is a quality filter, not release certification and creates no Reviewer/Boss PR decision record.
7. If accepted, append/update the work-queue item as `CANDIDATE`; if not, revert/repair within the safe clock or record `REJECTED`/blocked state.
8. Update issue #42 and release the lease. Do not open a PR merely because the hour ran.

## Integration mode

1. Acquire lease; reconcile exact `main`, staging, queue, and any previous integration result.
2. Do not manufacture a new product feature merely to fill the integration hour.
3. Inspect pending candidate dependencies/conflicts and remove/supersede work that became obsolete.
4. Write one checkpoint record under `engineering/integration/checkpoints/` containing the staging SHA and candidate IDs intended for validation.
5. Observe the exact staging MEDIUM workflows. If green, mark those exact-head candidates `INTEGRATED` and store the integration run metadata. If red, promote nothing and isolate the failure; a narrow repair is allowed only when the shift clock permits.
6. No normal merge to `main`.

## Release mode

1. Acquire lease and reconcile all state.
2. If staging equals `main` and no release-worthy work exists, record `NO_CHANGE` and stop.
3. Perform a final integration checkpoint for the exact staging head unless an exact-head MEDIUM success already exists after the latest candidate commit.
4. Require green MEDIUM validation before opening/updating the release PR.
5. Open/update a single release PR `company/staging -> main` with one coherent daily summary of candidate IDs, user impact, evidence, risks, APK impact, and rollback boundaries.
6. Wait for required FULL exact-head checks.
7. Run Reviewer evidence-reset and record the machine-readable PR decision.
8. Only after Reviewer `APPROVE`, run Boss evidence-reset and record the decision.
9. GREEN/YELLOW `APPROVE_MERGE` may exact-SHA merge when budgets and mergeability remain valid. RED never auto-merges.
10. Mark included queue items `RELEASED`, update `lastRelease`, reconcile issue #42, then reset/fast-forward `company/staging` to the merged `main` SHA before future candidate work.

## Candidate accumulation safety

Because candidate commits accumulate before release:

- no candidate may knowingly depend on a broken prior candidate;
- integration failure blocks release of the aggregate head;
- a later candidate may repair an earlier candidate only when the dependency is explicit;
- a superseded candidate remains in history but is marked `SUPERSEDED` so integrators do not treat commit count as product value;
- destructive/RED work is never silently accumulated in staging.

## Research sidecars

Research sidecars are optional and become useful only when they investigate independent questions. They may inspect external primary/official sources, model/runtime alternatives, UX patterns, behavioral evidence, or performance hypotheses. They write proposals/evidence only and must not mutate runtime production source or bypass the Director queue.

## Cost-control rules

- Candidate mode: no PR, no normal hosted CI, no APK build, no Vercel deployment.
- Integration mode: deliberate MEDIUM checks only when a checkpoint is written.
- Release mode: FULL PR CI and APK build only when relevant; main deploy occurs at most once in the normal daily cycle.
- Do not use no-op commits to trigger validation. Checkpoint files are explicit evidence-control artifacts, not no-op retries.
- External quota/provider failures are recorded and rechecked; do not rewrite healthy code to satisfy them.

## Success metric

Optimize released product quality and decision quality per unit of time/CI/deployment budget. Do not optimize number of commits, candidates, PRs, merges, or scheduled runs.
