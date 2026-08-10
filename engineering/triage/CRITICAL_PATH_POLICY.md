# Furina Critical-Path Triage Policy

## Purpose
The engineering company must treat Furina like a complex system under triage: stabilize the most dangerous failure and restore the critical path before spending capacity on local bruises, cosmetic polish, or convenient engineering work.

This policy runs **before** strategic-tier scoring. It determines which problems are eligible to compete for the current shift.

## Triage classes
Classify every credible candidate into exactly one class:

1. `T0_STOP_THE_LINE` — credible risk of data loss/corruption, privacy/security breach, unrecoverable storage damage, app unable to launch, critical build/release breakage, or catastrophic runtime failure that prevents normal use.
2. `T1_CRITICAL_PATH` — a failure that blocks or invalidates a P0 product path or the evidence needed to judge it. Examples: chat cannot generate, local model cannot load reliably, latest-message handling is fundamentally broken, memory persistence/retrieval is non-functional, or measurement is so broken that product decisions become misleading.
3. `T2_MAJOR` — materially degrades frequent daily use but the core product still functions. Examples: repeated latency spikes, recurring lifecycle/download failures, substantial UX blockers, or broad reliability defects.
4. `T3_LOCAL` — localized defect or friction with limited reach and no dependency on a higher-severity path.
5. `T4_POLISH` — cosmetic refinement, low-impact convenience, documentation neatness, or meta-engineering that does not unblock higher classes.

The highest credible non-blocked class wins. Lower classes are temporarily ineligible unless they directly diagnose, stabilize, or unblock the winning critical path.

## System layers
Record which layer is affected:
- `L0_INTEGRITY` — data safety, privacy, storage authority, crash/boot viability, build/release viability.
- `L1_CORE_COMPANION` — generation, latest-message relevance, persona baseline, memory continuity, local inference viability.
- `L2_CONTINUITY` — lifecycle, background work, downloads, network/offline transitions, persistence scheduling.
- `L3_EXPERIENCE` — interaction flow, loading/error states, settings, markdown/rendering, navigation and usability.
- `L4_POLISH_META` — cosmetic work and engineering-process convenience.

Layer is descriptive; triage class is the hard eligibility gate.

## Critical-path graph
For the highest eligible triage class, build a small causal graph before implementation:

`suspected root cause -> affected subsystem -> blocked product priority/evidence -> user-visible consequence`

For each candidate record:
- `triageClass`
- `systemLayer`
- `rootCauseHypothesis`
- `blockedPriorities`
- `dependencyCentrality` from 1–10
- `scopeReach` from 1–10
- `evidenceConfidence` from 1–10
- `criticalPathReason`

Prefer a credible shared root cause over separately treating many downstream symptoms. If root-cause confidence is too weak, spend the shift on the narrowest evidence-gathering step that can distinguish competing causes instead of patching symptoms blindly.

## Stabilize -> Restore -> Optimize -> Polish
Work proceeds in this order when applicable:
1. **Stabilize** — stop further damage, preserve data/state, restore boot/build/runtime safety.
2. **Restore** — make the blocked critical product path work correctly again.
3. **Optimize** — improve quality, latency, reliability, or maintainability after the critical path is trustworthy.
4. **Polish** — cosmetic/local refinements only after higher-severity work is not actionable.

A later phase must not displace an actionable earlier phase merely because it is easier to finish.

## Anti-distraction rule
While `T0_STOP_THE_LINE` or `T1_CRITICAL_PATH` work is actionable:
- do not add unrelated cleanup;
- do not fix incidental cosmetic defects merely because the files are already open;
- do not expand the package with local bugs that require separate validation or rollback;
- do not optimize a subsystem whose measurements are invalidated by the unresolved critical problem.

A tiny incidental edit is allowed only when it is required for the critical fix or adds effectively zero separate risk, evidence burden, and rollback complexity.

## Bottleneck rule
When several problems share the same triage class, prefer the candidate that removes the largest bottleneck across higher product priorities. Use dependency centrality and blocked-priority count before effort or convenience.

This prevents the company from repeatedly treating a visible hand bruise while a head injury still controls the outcome.

## Evidence and uncertainty
Severity without evidence can create panic-driven churn. Therefore:
- credible user/runtime/device/CI reproduction may justify high triage immediately;
- a hypothesis without reproduction normally caps `evidenceConfidence` at 6/10;
- if a claimed T0/T1 cannot be reproduced and no strong causal evidence exists, prioritize diagnosis rather than invasive repair;
- absence of evidence must not silently downgrade a known device-bound critical issue; keep it visible as blocked critical debt.

## Completion rule
A critical-path item is complete only when the blocking condition is removed or evidence shows the original diagnosis was wrong. A green build alone does not prove behavioral/device restoration when those dimensions were the injury.

## Relationship to strategic prioritization
Triage class is evaluated first. `engineering/prioritization/POLICY.md` then chooses strategic tier and within-tier score **inside the highest eligible triage class**. Numeric scoring never allows a lower triage class to jump ahead of a credible higher one.
