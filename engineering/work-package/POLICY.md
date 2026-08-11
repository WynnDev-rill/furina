# Furina Engineering Work Package Policy v2

## Purpose

Each CANDIDATE shift may select at most one newly chosen coherent high-value work package. The cadence is a work opportunity, not a requirement to create a change.

Candidate eligibility/priority is governed by `engineering/triage/CRITICAL_PATH_POLICY.md`, `engineering/prioritization/POLICY.md`, Factory promotion by `engineering/factory/FACTORY_V2.md`, and owner-away limits by `engineering/autonomy/UNATTENDED_POLICY.md`.

## Core rule

One CANDIDATE shift -> at most one coherent package -> FAST validation -> Candidate Reviewer -> queue.

Do not open a normal product PR merely because a package exists. Promotion is separate from creation.

A package may contain multiple related code/test/cleanup changes only when they share one product objective, one causal path, compatible evidence, and one rollback boundary.

## Critical-path scope boundary

When T0/T1 work is actionable, keep the package focused on stabilizing/restoring that path. Do not bundle unrelated polish/refactors/meta-work.

Blocked T0/T1 evidence/human debt with no autonomous next step does not freeze independent work; preserve debt and select from the highest eligible non-blocked class.

## Value threshold

A package should normally do at least one:
- fix a meaningful user-visible problem or coherent cluster;
- stabilize/restore a critical path;
- materially improve reliability/performance/companion quality/usability;
- unblock measurement or safe work on a higher-priority path;
- add a significant concept-aligned capability with measurable benefit;
- remove recurring engineering friction when meta-engineering is eligible.

Otherwise return `NO_CHANGE`.

## Queue contract

Before implementation record enough metadata to satisfy `engineering/work-queue/schema.json`:
- package ID/title/subsystem;
- triage and strategic tier;
- autonomy class;
- base SHA;
- dependencies/conflicts;
- expected metric/delta and verification window;
- evidence target;
- exact rollback boundary.

After accepted FAST review, bind `headSha` to the exact staging head and set status `CANDIDATE`.

## Candidate review boundary

The Candidate Reviewer is a same-shift FAST filter, not release certification.

It must re-fetch the exact change introduced by the Engineer and challenge root cause, scope, simpler alternatives, dependency/conflict assumptions, regression risk, rollback, and evidence truth. It does not create `FURINA_REVIEW_DECISION_V1`/Boss comments and has no merge authority.

## Integration boundary

INTEGRATION mode does not choose new feature work by default. It validates the aggregate staging head through an explicit checkpoint and MEDIUM workflows.

Candidates can promote to `INTEGRATED` only when the exact staging head containing them passes the required MEDIUM gate. Integration failure promotes nothing.

## Release boundary

Release certification happens only on the release PR `company/staging -> main` or a justified emergency-release PR.

Release Reviewer and Boss use the evidence-reset protocol. A new staging commit invalidates old exact-head certification. GREEN/YELLOW may merge only after exact-head FULL CI/evidence, Reviewer APPROVE, Boss APPROVE_MERGE, budget eligibility, final expected head SHA match, and mergeability. RED remains human-authorized and human-merged.

## Unverified behavior budget

Before accepting/releasing behavior-affecting YELLOW work, inspect the owner-away budget. Candidate status does not consume a released slot, but a release must be blocked if promotion would exceed a subsystem/project ceiling.

Do not relabel behavior change as structural to bypass the budget.

## Split criteria

Split work when:
- changes have materially different critical paths;
- evidence/rollback decisions differ;
- one portion can block/revert independently;
- combined review becomes difficult;
- any portion crosses RED authority;
- dependencies/conflicts would make aggregate diagnosis ambiguous.

## Revision and circuit breaker

Repair a rejected candidate or failed integration only when the shift clock safely permits it. Time is low -> checkpoint rather than rush.

Three substantively repeated failed attempts without stronger evidence quarantine the approach under unattended policy.

## Infrastructure efficiency

- Prefer a small number of purposeful commits.
- Candidate mode: no normal PR, hosted CI, APK build, or Vercel deployment.
- Integration mode: checkpoint-triggered MEDIUM validation only.
- Release mode: one aggregate FULL validation/release when warranted.
- No no-op/cosmetic commits to retrigger CI/deployment.
- Do not consume Vercel deployment when irrelevant to delivery.
- Treat transient provider/quota failure as external when appropriate.

## Prediction contract

Every accepted package states expected metric/delta and verification window. Do not claim product improvement from self-assigned scores, candidate acceptance, STATIC, or CI beyond what those evidence levels prove.

## Release PR summary

The normal daily release PR starts with `## Ringkasan Indonesia` and summarizes all promoted candidate IDs, triage/tier, user impact, evidence, APK impact, risk/blocker, rollback boundaries, unattended-budget impact, and intended decision.
