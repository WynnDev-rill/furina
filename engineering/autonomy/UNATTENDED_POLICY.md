# Furina Unattended Owner-Away Policy v2

## Status

Active by explicit owner authorization from 2026-08-11 until revoked. Owner-away mode changes allocation and pacing; it never weakens evidence truth, exact-SHA release review, privacy rules, signing integrity, or RED authority.

Factory cadence is governed by `engineering/factory/FACTORY_V2.md`.

## 1. Evidence debt is local

Missing BEHAVIORAL or DEVICE evidence blocks only the claim/candidate/subsystem decision that depends on it.

When evidence cannot be obtained autonomously:
1. create/update `evidenceDebt` in issue #42;
2. mark dependent work `BLOCKED_EVIDENCE` or `evidence_saturated` as applicable;
3. preserve the exact uncertified claim and recheck condition;
4. continue independent actionable work.

At most one active target-device request may exist for the same purpose. Coalesce requests to a stable verification boundary rather than replacing them after every staging commit.

## 2. Unverified behavior-change budget

To prevent conversational drift:
- max **2 released YELLOW behavior-affecting packages per subsystem** since its last matching BEHAVIORAL/DEVICE validation;
- max **4 outstanding project-wide**;
- reaching a limit marks the dependent subsystem `evidence_saturated` until evidence or a safe revert resolves debt.

Prompt, memory, retrieval, sampling, companion-state, context-framing, and generation-behavior changes count when their behavioral effect remains unverified. Candidate/integration status alone does not consume the released budget until work reaches `main`, but integrators must block a release that would exceed the ceiling.

## 3. Release pace and CI/deployment budget

Factory v2 replaces hourly auto-merge with batched promotion.

Normal target:
- up to **24 hourly engineering opportunities**;
- MEDIUM aggregate integration around `06`, `12`, `18`, plus final release integration at `00` when needed;
- at most **1 normal release merge in a rolling 24-hour period**.

This is a ceiling, not a target. `NO_CHANGE` and zero releases are valid.

An additional `EMERGENCY_RELEASE` is allowed only for a T0 stop-the-line or urgent T1 integrity failure where waiting for the normal window materially worsens user/data/release integrity. Record the reason, exact evidence, and why normal batching was unsafe.

Evidence ingestion, diagnosis, research, queue maintenance, and integration checkpoints do not consume the normal release count.

## 4. Circuit breaker

Quarantine an approach when, without stronger new evidence:
- three implementation/revision attempts hit the same substantive failure;
- three completed candidate/integration cycles revisit the same root-cause approach without stronger evidence or a materially different hypothesis;
- repeated Reviewer/Boss rejection identifies the same unresolved reason.

Record the failed approach in issue #42 and queue, then quarantine for at least 6 scheduled shifts. External/transient provider failures do not count unless code caused them.

## 5. Last-known-good and rollback

Issue #42 maintains `lastKnownGood` when evidence supports it: exact SHA, official build/run when applicable, strongest evidence level, scope, and timestamp.

A deterministic GREEN/YELLOW regression with a clear culprit may be reverted through normal Factory promotion and release gates. RED/destructive rollback remains human-authorized.

Because staging accumulates candidates, integration failure blocks release. Prefer narrow revert/repair of the culprit over discarding unrelated green candidates.

## 6. Major feature discovery

Significant concept-aligned features remain permitted when higher actionable work does not dominate. A feature must:
1. strengthen the persistent personal-companion mission;
2. avoid turning Furina into an unrelated utility bundle;
3. justify complexity, maintenance, UI weight, battery/RAM/network cost;
4. protect higher-priority conversation/speed/persona/memory quality;
5. make privacy/data authority explicit and local-first when practical;
6. define measurable success and rollback.

Research sidecars may inspect primary/official sources and comparable products, but have no production write authority.

## 7. Owner-attention queue

Human-only decisions belong in `ownerAttention` with exact reason and recheck condition. RED merge authority, destructive migration, credential/signing, privacy/data-authority changes, and irreducible ambiguity block only dependent work.

## 8. Dormancy is safe

If all high-value work is blocked, budgets saturated, circuit breakers active, and no independent meaningful candidate exists, record `NO_CHANGE`. Never manufacture cosmetic churn to keep automation busy.

## 9. Required issue #42 state

Preserve when relevant:
- `unattendedMode`;
- `factoryMode`;
- `stagingSha`;
- `evidenceDebt`;
- `ownerAttention`;
- `unverifiedBehaviorBudget`;
- `releaseWindow`;
- `circuitBreakers`;
- `lastKnownGood`;
- `discoveryState`;
- current integration/release checkpoint state.

These fields coordinate work; they are not evidence by themselves.
