# Furina Engineering Work Package Policy

## Purpose
The hourly cadence is a scheduling boundary, not a one-small-fix limit. Each cycle should maximize meaningful product value while keeping one coherent scope that can be reviewed, tested, and reverted as a unit.

This policy governs package shape. Candidate priority is governed by `engineering/prioritization/POLICY.md`; a large or easy engineering package must not displace a higher-tier product/evidence objective.

## Core rule
Select one coherent high-value work package per Engineer cycle, not necessarily one isolated change.

A work package may contain multiple related fixes, upgrades, refinements, tests, and cleanup items when they share the same product goal or subsystem and are safer/more efficient to ship together.

Examples:
- Chat UX package: contextual copy/play controls, visibility rules, tap targets, spacing, loading/error feedback, keyboard behavior, and related animation polish.
- Offline runtime reliability package: model-load error handling, retry behavior, crash diagnostics, storage-path robustness, and matching tests.
- Memory quality package: deduplication, contradiction handling, retrieval tuning, persistence fixes, and behavioral tests that validate the same memory objective.

## Value threshold
Do not create a PR for a trivial isolated tweak merely because an hourly cycle ran.

Before implementation, the Director should ask whether a candidate can reasonably be bundled with other related evidence-backed improvements in the same subsystem. Prefer a meaningful package over several tiny PRs when bundling does not materially increase regression risk.

A work package should normally satisfy at least one of these:
- fixes a meaningful user-visible problem or a cluster of related problems;
- materially improves reliability, performance, companion quality, or usability;
- directly unblocks measurement or safe work on a higher-tier product objective;
- removes recurring engineering friction or duplicated complexity when meta-engineering is eligible under the prioritization policy;
- combines several small related improvements whose aggregate value is clearly meaningful.

If no meaningful eligible package is available, return NO_CHANGE rather than producing cosmetic churn.

## Scope boundaries
Bundling is allowed only when changes are coherent.

Do not combine unrelated subsystems merely to make a PR look larger. Split work when:
- the changes require different evidence types or independent risk decisions;
- one part can block/revert independently from the rest;
- the combined change becomes difficult to review or test;
- the package crosses into RED scope that requires human authorization;
- the changes touch competing branches or create avoidable merge conflicts.

Reviewer and Boss must reject a package that is large but incoherent.

## Phase boundary
Package implementation belongs to the Engineer phase. The same execution that writes the package must not certify it as Reviewer or Boss. After implementation and required tests, hand the exact head SHA to a later Reviewer cycle under `engineering/review/INDEPENDENCE_POLICY.md`.

A Reviewer-requested revision returns to an Engineer phase; any new commit invalidates prior Reviewer/Boss approval for the old head SHA.

## Vercel and CI efficiency
Minimize infrastructure churn without weakening validation.

Rules:
- Prefer one coherent PR with a small number of purposeful commits over many tiny PRs in the same subsystem.
- Do not create a deployment merely to validate engineering-only/documentation/test changes when the deployment is not evidence required for the claim.
- Respect repository/Vercel ignore rules so Android-only, engineering-only, documentation, or test-only work does not consume Vercel deployments unnecessarily.
- Treat Vercel quota/rate-limit failures as external_transient when unrelated to the claimed product change.
- Do not repeatedly push no-op or cosmetic commits just to retrigger deployment or CI.

## Prediction contract
Before implementation of a measurable improvement, record expected metric/delta and verification window. Use `engineering/calibration/record.schema.json` for accepted work so later cycles can compare prediction against observation.

Do not claim a package is high-value solely from a high self-assigned impact score; strategic tier and evidence come first.

## Review contract
Reviewer must evaluate the package as a whole and also check that each included change contributes to the same objective.

Reviewer must verify package eligibility under the prioritization policy, not merely code correctness. Boss should prefer APPROVE_MERGE only when combined product value clearly outweighs aggregate regression/maintenance cost and operational independence/evidence requirements are satisfied. Boss should REQUEST_REVISION when the objective is valuable but the package contains unnecessary or weakly related scope.

## PR summary
Every PR must start with `## Ringkasan Indonesia` and summarize the complete work package, not only the last commit. State what changed, why it matters, strategic tier, evidence level, whether APK behavior is affected, important risks/blockers, and the decision expected from the human owner.
