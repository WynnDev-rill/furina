# Furina Review Separation Policy v2

## Purpose

Factory v2 distinguishes a cheap hourly **Candidate Reviewer** from certifying **Release Reviewer/Boss** passes. One ChatGPT execution is not equivalent to independent models; quality comes from evidence separation, exact-SHA binding, adversarial re-fetch, CI, and fail-closed promotion.

## Candidate Reviewer

CANDIDATE mode uses a non-certifying FAST review after implementation on `company/staging`.

The Candidate Reviewer must:
- ignore the Engineer conclusion as untrusted summary;
- re-fetch the exact staging change introduced by the shift;
- inspect root cause, scope, dependencies/conflicts, regression surface, rollback, simpler alternatives, and evidence claims;
- reject/block/revise work that is not safe enough to enter the queue.

Candidate review does not create PR decision comments, does not imply CI/behavior/device proof, and has no merge authority.

## Release same-execution separated passes

For every GREEN/YELLOW release PR exact head:
1. Engineer/integrator creates or revises the release head and records `engineerCycleId`.
2. **Reviewer evidence-reset pass** starts only after required exact-head FULL evidence is available and records a different `reviewCycleId`.
3. **Boss evidence-reset pass** starts only after Reviewer `APPROVE` on the same head and records a different `bossCycleId`.

The IDs prove ordered phase/provenance separation, not independent models.

## Evidence-reset rule

Before Reviewer certification:
- discard Engineer/candidate conclusions;
- fetch exact release PR head and diff again;
- fetch current main/base relation again;
- inspect required CI/checks directly;
- inspect behavioral/device evidence directly when applicable;
- inspect queue candidate/integration provenance;
- re-evaluate triage, root cause, aggregate scope, regression, rollback, simpler alternatives, and unattended budgets.

Before Boss certification, repeat primary-source inspection of current head, CI, Reviewer record, triage rationale, queue/integration provenance, applicable evidence, mergeability, autonomy class, and budgets.

## Head-SHA binding

Certification invariants remain:
- `reviewCycleId != engineerCycleId`;
- `bossCycleId != engineerCycleId`;
- `bossCycleId != reviewCycleId`;
- `reviewedHeadSha == current PR head SHA`;
- Boss `headSha == current PR head SHA`;
- Boss may approve merge only after Reviewer `APPROVE`.

`scripts/furina-decision-gate.py` validates these provenance/SHA invariants. A new commit invalidates both prior certifications.

## Machine-readable audit trail

Certifying Reviewer/Boss decisions remain separate top-level PR comments under `engineering/decisions/AUDIT_POLICY.md`. Never edit/reuse an old decision comment to certify a new head.

Issue #42 is mutable coordination state; work queue is candidate/integration coordination state. Neither substitutes for release evidence.

## Revision loops

Reviewer/Boss revision returns to `company/staging` and the same release PR when the clock safely permits. Any new head requires final integration as applicable, FULL CI, fresh Reviewer, and fresh Boss.

If time is low, checkpoint the valuable release attempt for the next RELEASE/emergency cycle. Time shortage cancels the current attempt, not a valuable PR.

## Auto-merge boundary

Under `SHIFT_GATED_AUTO_MERGE`, only RELEASE/EMERGENCY_RELEASE GREEN/YELLOW exact heads may auto-merge after:
- required FULL evidence is available;
- Reviewer evidence-reset returns `APPROVE`;
- Boss evidence-reset returns `APPROVE_MERGE`;
- current head still equals the expected head SHA;
- relevant CI remains green;
- GitHub reports mergeable;
- unattended budgets remain eligible.

CANDIDATE and INTEGRATION modes have no merge authority. RED remains human-authorized and human-merged.

## Anti-rubber-stamp rule

Reviewer and Boss must actively try to falsify the previous pass from primary evidence. Same-execution speed is an efficiency tradeoff, not a reason to trust prior narrative. If evidence cannot support the adversarial re-check, fail closed.
