# Furina Strategic Prioritization Policy

## Purpose
The loop optimizes Furina product quality, not task convenience. Easy or visible work must not displace a more critical bottleneck.

Candidate selection is lexicographic:
1. triage class from `engineering/triage/CRITICAL_PATH_POLICY.md`;
2. strategic tier from this policy;
3. numeric score only inside the same triage class and strategic tier.

A lower class or lower tier cannot win because it is easier, safer, faster, or cheaper.

## Strategic tiers
Inside the highest eligible triage class:
1. `P0_PRODUCT` — conversation quality, latency, persona, memory/continuity, agency, or evidence required to measure them.
2. `P0_UNBLOCKER` — work demonstrably required to unblock P0 product work or stop a recurring failure that makes P0 work impossible or misleading.
3. `P1_PRODUCT` — reliability, UX, maintainability, and other product work materially affecting daily use.
4. `P2_PRODUCT` — useful but non-urgent product improvement.
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

## Meta-engineering eligibility
`META_ENGINEERING` may precede product work only when at least one is true:
- it is a concrete P0 unblocker;
- it prevents a recurring control-plane failure observed in at least two separate shifts;
- no non-blocked T0/T1/P0/P1 product or evidence candidate is actionable with sufficient evidence.

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

Without direct reproduction, benchmark, CI failure, device evidence, or repeated runtime/user signal, confidence is normally capped at 7/10. A T0/T1 hypothesis with weak reproduction should usually become diagnosis/evidence work first.

## Difficulty protection
Required evidence or repair on a T0/T1/P0 path must not be repeatedly deferred because it is difficult, device-bound, or slower than local polish. If it cannot be executed autonomously, record the narrowest blocker/evidence request and keep the critical debt visible.

## Calibration loop
Predictions must be compared with outcomes using `engineering/calibration/record.schema.json`.

Track predicted impact, expected metric/delta, verification window, observed delta, outcome, and calibration. Repeated overestimation lowers future confidence. Repeated underestimation of difficult high-value work means effort should not keep suppressing it.

## Anti-self-optimization and anti-distraction
The loop must not spend repeated shifts improving its own policies, prompts, dashboards, CI, or cosmetic details while an actionable higher triage class or higher product tier remains unresolved.

Control-plane quality is a means to improve Furina, not a competing product.
