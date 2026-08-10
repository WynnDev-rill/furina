# Furina Strategic Prioritization Policy

## Purpose
The engineering loop must optimize Furina product quality, not the ease of the next task. Low-effort control-plane work must not outrank difficult product work merely because effort and regression risk appear in the denominator of a score.

This specialized policy is authoritative for candidate ranking. Where the generic ranking text in `engineering/COMPANY.md` conflicts with this file, this file supersedes it until the constitution is consolidated in a later reviewed change.

## Lexicographic strategic tiers
Candidate selection is two-stage. First choose the highest eligible strategic tier; only then compare numeric scores inside that tier.

1. `P0_PRODUCT` — direct work on the top product priorities: conversation quality, latency, persona, memory/continuity, agency, or evidence required to measure those dimensions.
2. `P0_UNBLOCKER` — work that is demonstrably required to unblock a `P0_PRODUCT` objective or prevent a recurring failure that makes P0 work impossible or misleading.
3. `P1_PRODUCT` — reliability, UX, maintainability, and other product work that materially affects daily use.
4. `P2_PRODUCT` — useful but non-urgent product improvements.
5. `META_ENGINEERING` — repository policy, tooling, CI ergonomics, developer convenience, documentation, and other work whose primary beneficiary is the engineering process rather than the Furina user.

A lower tier cannot outrank a higher eligible tier because it is easier, safer, faster, or cheaper.

## Meta-engineering eligibility
`META_ENGINEERING` is eligible before product work only when at least one is true:
- it is a `P0_UNBLOCKER` with concrete evidence showing that P0 work cannot proceed correctly without it;
- it prevents a recurring control-plane failure observed in at least two separate cycles;
- no non-blocked `P0_PRODUCT` or `P1_PRODUCT` candidate has sufficient evidence to act on.

Do not classify ordinary convenience, policy cleanup, dashboard work, prompt wording, or CI neatness as `P0_UNBLOCKER`.

As an anti-self-optimization budget, non-blocking `META_ENGINEERING` should consume no more than one of the last six completed change-producing cycles. Reviewer-only, Boss-only, human merge, `NO_CHANGE`, and evidence-only observation cycles do not count as change-producing cycles.

## Numeric score inside a tier
Within the same strategic tier, rank using:

`withinTierScore = impact * confidence * frequency / max(1, 1 + 0.35 * (effort - 1) + 0.25 * (regressionRisk - 1))`

Use 1–10 inputs. Effort and risk matter, but they are deliberately damped so a difficult high-value objective is not suppressed by orders of magnitude.

The score is advisory. A Director must reject obviously self-serving scoring and explain any manual override.

## Required candidate fields
Every ranked candidate recorded in issue #42 must include:
- `candidate`
- `category`
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

If `expectedMetric` or `expectedDelta` cannot be stated for a claimed improvement, confidence should normally be reduced or the candidate should remain investigation-only.

For each non-trivial numeric score, record the evidence or assumption supporting it. If there is no direct reproduction, benchmark, CI failure, device evidence, or repeated runtime/user signal, confidence is capped at 7/10. Simplicity alone is not evidence for 9–10 confidence.

## Difficulty protection
A required measurement/evidence task for a P0 product priority must not be repeatedly deferred because it is expensive, device-bound, or technically difficult. When it cannot be executed autonomously, create the narrowest evidence request and continue independent work, but keep the P0 objective visible as strategic debt.

## Calibration loop
Predictions must be compared with outcomes after merge or after sufficient evidence becomes available using `engineering/calibration/record.schema.json`.

For each accepted work package, record:
- predicted impact;
- expected metric and delta;
- verification window;
- observed delta when available;
- outcome: `better`, `neutral`, `worse`, or `inconclusive`;
- calibration: `overestimated`, `calibrated`, `underestimated`, or `inconclusive`.

When a class of work is repeatedly overestimated, lower future confidence for similar candidates. When difficult work repeatedly produces larger gains than predicted, do not continue penalizing it merely because effort is high.

## Anti-self-optimization rule
The loop must not spend repeated cycles improving its own policies, prompts, dashboards, or CI while higher-tier product/evidence work remains actionable. Control-plane quality is a means to improve Furina, not an independent product goal.
