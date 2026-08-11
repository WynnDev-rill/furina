# Furina Unattended Owner-Away Policy

## Status and purpose

This policy is active by explicit owner authorization on 2026-08-11 and remains active until the owner explicitly revokes or replaces it.

The owner may leave Furina unattended for days or weeks. The Engineering Company must continue useful work without turning missing target-device evidence, an unanswered human decision, or an expired evidence request into a global freeze. At the same time, unattended autonomy must not become uncontrolled feature churn, stacked unverified behavior changes, or silent RED-risk migration.

Repository policy remains authoritative. Owner-away mode changes allocation and pacing; it does **not** weaken evidence truth, exact-SHA review, privacy rules, release integrity, or RED authority.

## 1. Evidence debt is local, not a global blocker

Missing BEHAVIORAL or DEVICE evidence blocks only the claim, candidate, or subsystem decision that actually depends on it.

When required evidence cannot be obtained autonomously:
1. create or update an `evidenceDebt` entry in issue #42;
2. mark the dependent candidate `blocked_evidence` or `evidence_saturated` as applicable;
3. preserve the exact claim that cannot yet be certified;
4. continue triage among independent actionable work instead of ending every shift on the same blocker.

An unavailable device must never cause repeated `waiting_for_device_evidence` shifts when unrelated or structurally provable work remains.

### Evidence-debt record

Each active debt should carry, when applicable:
- `id`;
- `subsystem`;
- `claim`;
- `requiredLevel` (`BEHAVIORAL` or `DEVICE`);
- `targetCommit` / `targetBuild` when exact binding exists;
- `requestId` and request state;
- `createdAt` / `lastCheckedAt`;
- `recheckCondition`;
- `supersededBy` when a newer target replaces it.

### Request coalescing and anti-spam

- At most one active target-device evidence request may exist for the same purpose.
- Do not recreate the same request every shift while it is pending, valid, or waiting for the owner.
- If `main` moves, mark the old exact-build request superseded. Do not immediately create a replacement after every commit; coalesce to the newest stable eligible target when the subsystem reaches a verification boundary.
- An expired request leaves evidence debt; expiration is not a product failure.
- When the owner is absent, continue independent engineering and request fresh evidence only when it would unlock a real decision.

## 2. Unverified behavior-change budget

Structural correctness and behavioral quality are different claims. A prompt, memory, retrieval, sampling, companion-state, or inference-context change may be statically correct while its conversation-quality effect remains unverified.

To prevent weeks of plausible but unmeasured behavioral drift:
- no subsystem may accumulate more than **2 merged YELLOW behavior-affecting packages** since its last matching BEHAVIORAL/DEVICE validation;
- no more than **4 unverified behavior-affecting YELLOW packages** may be outstanding project-wide;
- after the limit is reached, mark that subsystem `evidence_saturated` and stop further behavior-changing merges there until evidence resolves debt or a safe revert reduces it;
- STATIC/CI-only instrumentation, tests, diagnosis, documentation, and independent work in other subsystems may continue.

A package counts toward this budget when it materially changes persona instructions, memory/retrieval semantics, conversation context framing, sampling/generation behavior, autonomous companion behavior, or another user-visible model-behavior path without matching behavioral/device validation.

Do not relabel a behavioral change as “structural” merely to bypass the budget.

## 3. Autonomous merge pace

During owner-away mode, correctness is more valuable than hourly output.

- Maximum **3 auto-merged change-producing PRs in any rolling 24-hour window**.
- Maximum **2 auto-merged packages touching the same L1 core-companion subsystem in a rolling 24-hour window**.
- After a merge, the next shift touching the same subsystem must first reconcile the merged exact-main CI/build/regression state before selecting another code package there.
- Research, diagnosis, evidence ingestion, review, issue-state reconciliation, and `NO_CHANGE` do not consume this merge budget.

These are ceilings, not targets. Zero merges is valid.

## 4. Circuit breaker against thrashing

An approach is temporarily quarantined when any of the following occurs without stronger new evidence:
- three implementation/revision attempts hit the same substantive failure;
- three completed shifts revisit the same root-cause approach without producing stronger evidence or a materially different hypothesis;
- repeated Reviewer/Boss rejection identifies the same unresolved reason.

Record the failed approach and lesson in issue #42, then quarantine that approach for at least **6 scheduled shifts**. Work may continue on a genuinely different root cause or independent subsystem.

External/transient CI/provider failures do not count as engineering thrash unless evidence shows the code caused them.

## 5. Last-known-good and unattended rollback

Issue #42 should maintain a `lastKnownGood` record when evidence supports one:
- exact SHA;
- official build/run when applicable;
- strongest evidence level actually established;
- timestamp and scope of what “good” means.

A CI-green APK may be last-known-good for build/release integrity, but not automatically for persona, memory quality, latency, or device behavior.

When a new GREEN/YELLOW merge causes a deterministic regression with a clear culprit and a narrow, non-destructive revert is safer than forward repair, the Company may prepare, review, Boss-approve, and auto-merge that revert under the normal exact-SHA gates.

RED/destructive rollback remains human-authorized.

## 6. Major feature discovery and expansion is allowed

The owner explicitly permits the Company to discover and implement significant new features while unattended, including ideas the owner may not have known about, provided they remain coherent with Furina’s product concept.

A major feature is eligible only when it passes all concept-fit gates:
1. it directly strengthens the persistent personal-companion mission or a product priority in `engineering/COMPANY.md`;
2. it does not turn Furina into an unrelated utility bundle, generic assistant dashboard, social feed, ad surface, or novelty collection;
3. expected benefit is large enough to justify complexity, maintenance, UI weight, battery/RAM/network cost, and future migration burden;
4. higher-priority natural conversation, perceived speed, persona, and memory are protected from material regression;
5. data authority/privacy is explicit and local-first when practical;
6. success has a measurable verification plan and a clear rollback boundary.

Director may use targeted external research from primary/official sources and credible comparable products to discover useful capabilities. Research is a candidate-generation input, not proof that Furina needs the feature.

Large GREEN/YELLOW features may be implemented and auto-merged after normal Reviewer/Boss evidence-reset gates. RED work may be researched, designed, benchmarked, or prepared as a blocked PR, but may not be merged without human authority.

## 7. Owner-attention queue does not freeze the company

Human-only decisions belong in an `ownerAttention` queue in issue #42 with the exact reason and recheck condition.

Examples include RED merge authority, destructive migration, credential/signing changes, privacy/data-authority changes, or an ambiguity that cannot safely be resolved from repository/product policy.

An `ownerAttention` item blocks only dependent work. Continue independent work.

## 8. Discovery when the backlog is thin

If no higher-triage actionable defect or evidence task exists, Director may deliberately search for the next high-value product opportunity instead of manufacturing cleanup.

Discovery should inspect, as relevant:
- core companion conversation architecture;
- memory/continuity quality;
- local inference/runtime performance;
- Android-native capabilities that improve a personal companion;
- voice, multimodal, proactive/ambient interaction, accessibility, reliability, privacy, and offline UX;
- strong comparable applications or official platform capabilities that reveal a useful missing feature.

Discovery must still produce a causal product case before implementation. “Other apps have it” is not sufficient.

## 9. Dormancy is a valid safe state

If all remaining high-value work is blocked by evidence/human authority, merge budgets are saturated, circuit breakers are active, and no independent meaningful candidate exists, record `NO_CHANGE` and end.

Do not create cosmetic work, policy churn, dependency upgrades, or speculative features merely to keep the automation visibly busy.

## 10. Required unattended state in issue #42

While this policy is active, the current-state snapshot should preserve these fields when relevant:
- `unattendedMode`: `active`;
- `evidenceDebt`;
- `ownerAttention`;
- `unverifiedBehaviorBudget`;
- `recentMergeWindow`;
- `circuitBreakers`;
- `lastKnownGood`;
- `discoveryState` when discovery work is active.

Missing optional arrays may be initialized empty. State fields are coordination data, not evidence by themselves.
