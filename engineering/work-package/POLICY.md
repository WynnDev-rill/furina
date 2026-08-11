# Furina Engineering Work Package Policy

## Purpose
The scheduled cadence is a coordination boundary, not a one-small-fix limit. Each shift should maximize meaningful product value while keeping one coherent scope that can be tested, reviewed, revised, and reverted as a unit.

Package shape is governed here. Candidate eligibility and priority are governed by `engineering/triage/CRITICAL_PATH_POLICY.md`, `engineering/prioritization/POLICY.md`, and owner-away limits by `engineering/autonomy/UNATTENDED_POLICY.md`.

## Core rule
Select at most one newly chosen coherent high-value work package per shift.

A package may contain multiple related fixes, refinements, tests, and cleanup only when they share the same critical path/product objective, evidence boundary, and rollback boundary.

Examples:
- offline runtime reliability: model-load failure, crash diagnostics, storage-path robustness, retry behavior, matching tests;
- memory quality: contradiction handling, deduplication, retrieval/persistence fixes, matching behavioral evidence;
- chat UX: only when no higher critical path is actionable, combine related loading/error/keyboard/navigation friction under one rollback boundary;
- concept-aligned major feature: one substantial companion capability plus only the supporting UX/runtime/tests required to make that capability coherent and reversible.

## Critical-path scope boundary
When T0/T1 work is actionable, the package must stay focused on stabilizing/restoring that path.

Do not bundle unrelated local bugs, cosmetic polish, opportunistic refactors, or meta-engineering merely because nearby files are open.

A tiny incidental change is allowed only if it is required by the critical repair or adds effectively zero separate regression, evidence, and rollback burden.

A blocked T0/T1 evidence/human debt with no autonomous next step does not forbid an independent lower-class package; follow the blocked-debt rule in triage policy.

## Value threshold
Do not create a PR for a trivial isolated tweak merely because a scheduled shift ran.

A package should normally do at least one:
- fix a meaningful user-visible problem or coherent cluster;
- stabilize/restore a critical product path;
- materially improve reliability, performance, companion quality, or usability;
- directly unblock measurement or safe work on a higher-priority path;
- add a significant concept-aligned companion capability with a measurable benefit;
- remove recurring engineering friction only when meta-engineering is eligible.

If no meaningful eligible package exists, return `NO_CHANGE`.

## Major-feature package rule

Owner-away mode permits large new features, but “large” does not mean unbounded scope.

A major feature package must:
- pass the concept-fit gates in `engineering/autonomy/UNATTENDED_POLICY.md`;
- have one clear user journey/outcome rather than several unrelated feature ideas;
- include the minimum supporting architecture/UX/tests needed for that outcome;
- state expected impact on conversation quality, perceived latency, persona, memory, privacy, RAM/battery/network, and settings complexity;
- define an evidence plan and rollback boundary before implementation;
- remain GREEN/YELLOW to auto-merge. Any RED portion is split or blocked for human authority.

A feature may be substantial enough to span multiple shifts on one PR. Do not split it into artificial PR fragments merely to satisfy the cadence.

## Unattended behavior-change budget

Before opening or revising a behavior-affecting YELLOW package, inspect the owner-away unverified-behavior budget.

If the package would exceed a subsystem/project ceiling, do not merge it without the missing evidence. Instead choose one of:
- collect/ingest the required evidence when autonomously possible;
- add non-behavioral instrumentation/tests needed to unlock evidence;
- switch to independent work;
- checkpoint the package as blocked evidence.

The package summary must say whether it consumes an unverified-behavior slot and which subsystem it affects.

## Split criteria
Split work when:
- changes belong to different triage classes and the lower class is not required by the critical path;
- evidence types or rollback decisions differ materially;
- one part can block/revert independently;
- combined review becomes difficult;
- the package crosses into RED scope;
- branches/subsystems would create avoidable conflict;
- one portion would consume a different unattended evidence/merge budget.

## Same-shift phase boundary
Engineer, Reviewer, and Boss may occur in the same ChatGPT shift to eliminate idle waiting, but they remain separate evidence passes.

- Engineer writes code and pushes an exact head.
- Reviewer must perform the evidence-reset protocol in `engineering/review/INDEPENDENCE_POLICY.md` before certification.
- Boss must perform its own evidence-reset pass before release decision.
- Each role uses a distinct phase/provenance ID and separate audit comment.
- A new commit invalidates prior Reviewer/Boss records.

The same-shift design is an efficiency tradeoff; it must not be mislabeled as independent models.

## Revision loop and circuit breaker
Reviewer/Boss revision returns to the same PR. If the shift clock safely permits implementation + validation + re-review, revise immediately. If time is low, checkpoint the valuable PR for the next shift rather than closing or rushing it.

Before another revision, inspect the unattended circuit breaker. Three substantively repeated failed attempts without stronger evidence quarantine that approach under `engineering/autonomy/UNATTENDED_POLICY.md`; do not keep rewriting the same idea indefinitely.

## Infrastructure efficiency
- Prefer a small number of purposeful commits.
- No no-op/cosmetic commits to retrigger CI or deployment.
- Do not consume Vercel deployment when irrelevant to the claim.
- Treat temporary provider/quota failure as `external_transient` when appropriate.
- During owner-away mode, respect the rolling merge ceilings; unused merge capacity is not a reason to create work.

## Prediction contract
Before implementation, record expected metric/delta and verification window. Use `engineering/calibration/record.schema.json` for accepted work.

Do not claim high value from a self-assigned score alone. Triage class, strategic tier, causal evidence, critical-path position, concept fit, and unattended budgets come first.

## Review contract
Reviewer checks the package as a whole and each included change against the same objective. Boss should approve only when product value clearly outweighs aggregate regression/maintenance cost and the critical path was treated rather than bypassed.

For STATIC/CI-only approval of a behavior-affecting YELLOW package, the review record must explicitly distinguish the structurally proven claim from behavioral evidence debt and confirm the unverified-behavior budget remains within policy.

## PR summary
Every normal company PR starts with `## Ringkasan Indonesia` and summarizes the full package, triage class, strategic tier, evidence, APK impact, risk/blocker, rollback boundary, unattended-budget impact, and intended decision.
