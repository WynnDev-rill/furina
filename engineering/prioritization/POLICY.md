# Furina Strategic Prioritization Policy

## Purpose
The loop optimizes Furina product quality, not task convenience. Easy or visible work must not displace a more critical bottleneck.

Candidate selection is lexicographic:
1. actionable triage class from `engineering/triage/CRITICAL_PATH_POLICY.md`;
2. strategic tier from this policy;
3. numeric score only inside the same triage class and strategic tier.

A lower class or lower tier cannot win because it is easier, safer, faster, or cheaper. A higher-severity item that is genuinely blocked by unavailable evidence/human authority remains debt but does not consume the shift merely because its severity is higher.

## Strategic tiers
Inside the highest eligible actionable triage class:
1. `P0_PRODUCT` — conversation quality, latency, persona, memory/continuity, agency, or evidence required to measure them.
2. `P0_UNBLOCKER` — work demonstrably required to unblock P0 product work or stop a recurring failure that makes P0 work impossible or misleading.
3. `P1_PRODUCT` — reliability, UX, maintainability, and other product work materially affecting daily use.
4. `P2_PRODUCT` — useful but non-urgent product improvement, including concept-aligned feature expansion when higher priorities are not actionable.
5. `META_ENGINEERING` — repository policy, tooling, CI ergonomics, documentation, and engineering-process convenience.

A lower tier cannot outrank a higher eligible tier.

## Critical bottleneck ordering
When candidates share the same triage class and tier, compare before numeric score:
1. higher `dependencyCentrality`;
2. more or higher blocked product priorities;
3. larger credible `scopeReach`;
4. stronger evidence that the candidate is a root cause rather than a symptom;
5. numeric score.

This protects high-leverage root causes from being displaced by easy downstream symptoms.

## Blocked debt versus actionable work

Difficulty alone never makes a candidate ineligible. However, a candidate is not actionable when every useful next step depends on unavailable owner/device/RED authority or an external condition with no autonomous diagnostic path.

For such a candidate:
- preserve its original triage/severity in `evidenceDebt` or `ownerAttention`;
- record the exact recheck condition;
- avoid repeated no-op evidence requests;
- continue ranking independent actionable candidates.

If a source audit, deterministic test, instrumentation package, simulation, benchmark, or reversible structural fix can genuinely advance the high-priority path, it remains actionable and retains its priority.

## Concept-aligned discovery and major features

Owner-away mode explicitly permits significant new features under `engineering/autonomy/UNATTENDED_POLICY.md`.

Feature discovery becomes eligible when:
- no higher-triage actionable defect/restore/evidence task exists; or
- the discovered feature itself removes a higher-priority bottleneck.

A feature candidate must have:
- a direct link to the Furina persistent-companion mission;
- an explicit user benefit;
- concept-fit rationale;
- expected effect on naturalness, perceived speed, persona, memory, privacy, battery/RAM/network, and UX complexity;
- a measurable verification plan;
- rollback boundary and autonomy class.

“Popular elsewhere” or “technically interesting” is not sufficient. Targeted external research may generate candidates but does not determine priority by itself.

## Meta-engineering eligibility
`META_ENGINEERING` may precede product work only when at least one is true:
- it is a concrete P0 unblocker;
- it prevents a recurring control-plane failure observed in at least two separate shifts;
- no non-blocked T0/T1/P0/P1 product or evidence candidate is actionable with sufficient evidence;
- an unattended-control defect would otherwise cause global freezing, uncontrolled churn, stale evidence loops, or unsafe merges.

Ordinary policy cleanup, dashboard work, prompt wording, CI neatness, or convenience is not a P0 unblocker.

Non-blocking META_ENGINEERING should consume no more than one of the last six completed change-producing shifts.

## Numeric score inside the same class/tier
Use:

`withinTierScore = impact * confidence * frequency / max(1, 1 + 0.35 * (effort - 1) + 0.25 * (regressionRisk - 1))`

Use 1–10 inputs. This score is advisory and never crosses triage or tier boundaries.

## Required candidate fields
For each serious candidate record:
- `candidate`
- `category`
- `triageClass`
- `systemLayer`
- `rootCauseHypothesis`
- `blockedPriorities`
- `dependencyCentrality`
- `scopeReach`
- `criticalPathReason`
- `actionability`
- `nextAutonomousStep` or `recheckCondition`
- `strategicTier`
- `impact`
- `confidence`
- `frequency`
- `effort`
- `regressionRisk`
- `withinTierScore`
- `expectedMetric`
- `expectedDelta`
- `verificationWindow`
- `unattendedBudgetImpact` when owner-away mode is active.

Without direct reproduction, benchmark, CI failure, device evidence, repeated runtime/user signal, or strong static proof of a structural defect, confidence is normally capped at 7/10. A T0/T1 hypothesis with weak reproduction should usually become diagnosis/evidence work first when such evidence work is autonomously available.

## Difficulty protection
Required evidence or repair on a T0/T1/P0 path must not be repeatedly deferred merely because it is difficult or slower than local polish.

When it **can** be advanced autonomously, keep working the hard path. When it **cannot** be advanced because the required device/human input is absent, record the narrow blocker/evidence debt and allocate the shift to the next meaningful independent candidate instead of repeating the same checkpoint.

## Unattended pacing protection
Before implementation, candidates must also pass `engineering/autonomy/UNATTENDED_POLICY.md`:
- rolling auto-merge ceilings;
- same-subsystem merge ceiling;
- unverified behavior-change budget;
- circuit-breaker quarantine;
- owner-attention/RED authority rules.

A candidate that would exceed one of these ceilings is temporarily ineligible even if its strategic score is high, unless the package is a narrow safe revert needed to restore a deterministic regression under the unattended rollback policy.

## Calibration loop
Predictions must be compared with outcomes using `engineering/calibration/record.schema.json`.

Track predicted impact, expected metric/delta, verification window, observed delta, outcome, and calibration. Repeated overestimation lowers future confidence. Repeated underestimation of difficult high-value work means effort should not keep suppressing it.

## Anti-self-optimization and anti-distraction
The loop must not spend repeated shifts improving its own policies, prompts, dashboards, CI, or cosmetic details while an actionable higher triage class or higher product tier remains unresolved.

Control-plane quality is a means to improve Furina, not a competing product.
