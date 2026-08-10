# Furina Engineering Work Package Policy

## Purpose
The hourly cadence is a scheduling boundary, not a one-small-fix limit. Each shift should maximize meaningful product value while keeping one coherent scope that can be tested, reviewed, revised, and reverted as a unit.

Package shape is governed here. Candidate eligibility and priority are governed by `engineering/triage/CRITICAL_PATH_POLICY.md` and `engineering/prioritization/POLICY.md`.

## Core rule
Select at most one newly chosen coherent high-value work package per shift.

A package may contain multiple related fixes, refinements, tests, and cleanup only when they share the same critical path/product objective, evidence boundary, and rollback boundary.

Examples:
- offline runtime reliability: model-load failure, crash diagnostics, storage-path robustness, retry behavior, matching tests;
- memory quality: contradiction handling, deduplication, retrieval/persistence fixes, matching behavioral evidence;
- chat UX: only when no higher critical path is actionable, combine related loading/error/keyboard/navigation friction under one rollback boundary.

## Critical-path scope boundary
When T0/T1 work is actionable, the package must stay focused on stabilizing/restoring that path.

Do not bundle unrelated local bugs, cosmetic polish, opportunistic refactors, or meta-engineering merely because nearby files are open.

A tiny incidental change is allowed only if it is required by the critical repair or adds effectively zero separate regression, evidence, and rollback burden.

## Value threshold
Do not create a PR for a trivial isolated tweak merely because an hourly shift ran.

A package should normally do at least one:
- fix a meaningful user-visible problem or coherent cluster;
- stabilize/restore a critical product path;
- materially improve reliability, performance, companion quality, or usability;
- directly unblock measurement or safe work on a higher-priority path;
- remove recurring engineering friction only when meta-engineering is eligible.

If no meaningful eligible package exists, return `NO_CHANGE`.

## Split criteria
Split work when:
- changes belong to different triage classes and the lower class is not required by the critical path;
- evidence types or rollback decisions differ materially;
- one part can block/revert independently;
- combined review becomes difficult;
- the package crosses into RED scope;
- branches/subsystems would create avoidable conflict.

## Same-shift phase boundary
Engineer, Reviewer, and Boss may occur in the same ChatGPT shift to eliminate idle waiting, but they remain separate evidence passes.

- Engineer writes code and pushes an exact head.
- Reviewer must perform the evidence-reset protocol in `engineering/review/INDEPENDENCE_POLICY.md` before certification.
- Boss must perform its own evidence-reset pass before release decision.
- Each role uses a distinct phase/provenance ID and separate audit comment.
- A new commit invalidates prior Reviewer/Boss records.

The same-shift design is an efficiency tradeoff; it must not be mislabeled as independent models.

## Revision loop
Reviewer/Boss revision returns to the same PR. If the shift clock safely permits implementation + validation + re-review, revise immediately. If time is low, checkpoint the valuable PR for the next shift rather than closing or rushing it.

## Infrastructure efficiency
- Prefer a small number of purposeful commits.
- No no-op/cosmetic commits to retrigger CI or deployment.
- Do not consume Vercel deployment when irrelevant to the claim.
- Treat temporary provider/quota failure as `external_transient` when appropriate.

## Prediction contract
Before implementation, record expected metric/delta and verification window. Use `engineering/calibration/record.schema.json` for accepted work.

Do not claim high value from a self-assigned score alone. Triage class, strategic tier, causal evidence, and critical-path position come first.

## Review contract
Reviewer checks the package as a whole and each included change against the same objective. Boss should approve only when product value clearly outweighs aggregate regression/maintenance cost and the critical path was treated rather than bypassed.

## PR summary
Every normal company PR starts with `## Ringkasan Indonesia` and summarizes the full package, triage class, strategic tier, evidence, APK impact, risk/blocker, rollback boundary, and intended decision.
