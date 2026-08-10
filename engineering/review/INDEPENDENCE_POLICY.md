# Furina Review Separation Policy

## Purpose
The company now uses one ChatGPT shift to avoid idle handoff time. This is not equivalent to independent models or separate conversations, so quality must come from strict evidence separation rather than pretending role labels create independence.

## Same-shift separated passes
For every GREEN/YELLOW PR head:
1. **Engineer pass** creates or revises the exact head and records `engineerCycleId` as a phase/provenance ID.
2. **Reviewer evidence-reset pass** begins only after required evidence for that exact head is available. It records a different `reviewCycleId`.
3. **Boss evidence-reset pass** begins only after Reviewer `APPROVE` for the same head. It records a different `bossCycleId`.

The three IDs prove ordered role passes and SHA provenance. They do **not** prove independent models.

There is no minimum wall-clock delay. The next pass starts as soon as its evidence prerequisite is ready and the shift clock allows it.

## Evidence-reset rule
Before Reviewer certification, the assistant must:
- ignore the Engineer conclusion as untrusted summary;
- fetch the exact PR head and diff again;
- fetch current base/main relationship again;
- inspect required CI/checks directly;
- inspect behavioral/device evidence directly when applicable;
- re-evaluate triage selection, root cause, scope, regression risk, and simpler alternatives.

Before Boss certification, the assistant must repeat primary-source inspection of the current head, CI, Reviewer record, triage rationale, evidence, mergeability, and autonomy class. Boss must not simply inherit Reviewer reasoning.

## Head-SHA binding
Reviewer and Boss decisions are valid only for the exact PR head they inspected. Any new commit invalidates both.

Semantic invariants remain:
- `reviewCycleId != engineerCycleId`
- `bossCycleId != engineerCycleId`
- `bossCycleId != reviewCycleId`
- `reviewedHeadSha == current PR head SHA`
- Boss `headSha == current PR head SHA`
- Boss may approve merge only after Reviewer `APPROVE`

`scripts/furina-decision-gate.py` validates these provenance/SHA invariants. Distinct IDs are phase separation, not a claim of model independence.

## Machine-readable audit trail
Reviewer and Boss decisions remain separate top-level PR comments under `engineering/decisions/AUDIT_POLICY.md`.

Issue #42 is the mutable current-state pointer. Never edit an old decision comment to certify a new head.

## Revision loops
A Reviewer or Boss request for revision returns to Engineer on the same PR when the shift time budget safely permits it. A new head restarts validation and invalidates prior certification.

If little time remains, cancel the current **attempt** and checkpoint the PR for the next shift. Do not close valuable work merely because the hourly boundary is near.

## Auto-merge boundary
Under `SHIFT_GATED_AUTO_MERGE`, only GREEN/YELLOW exact heads may auto-merge, and only after:
- required evidence is available;
- Reviewer evidence-reset returns `APPROVE`;
- Boss evidence-reset returns `APPROVE_MERGE`;
- the current head still equals the approved SHA;
- relevant CI remains green;
- GitHub reports the PR mergeable.

RED remains human-authorized and human-merged.

## Anti-rubber-stamp rule
A same-shift design is accepted as an efficiency tradeoff, not mislabeled as full independence. Reviewer and Boss must actively try to falsify the previous pass using primary evidence. If the evidence cannot support that adversarial re-check, fail closed instead of approving.
