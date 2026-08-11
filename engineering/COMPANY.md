# Furina Product Constitution

## Mission
Furina must feel like one persistent companion with a stable identity, shared history, natural conversation, and fast daily-use responsiveness. It must not degrade into a generic assistant wearing a character prompt.

## Product priorities
In descending order:
1. Natural conversation and latest-message relevance.
2. Fast perceived response time for daily use.
3. Persona consistency from the first conversation.
4. Persistent memory and relationship continuity.
5. Believable initiative, preference, and internal-state continuity.
6. Simple, calm, understandable UX.
7. Additional features only when they measurably improve the product.

## Non-negotiable principles
- Furina is already Furina on first launch. Shared history may deepen; baseline character quality must not be turn-count gated.
- Prefer one canonical source of truth for identity, memory state, emotional state, relationship state, runtime state, and engineering state.
- Prefer removing complexity over exposing more settings.
- A new feature requires a defined user benefit and a way to verify that benefit.
- Do not trade a large loss in persona or memory quality for a small latency gain.
- Do not trade a large latency regression for a cosmetic improvement.
- Keep the generation hot path minimal; expensive learning/reflection belongs in cancellable or queued maintenance.
- Every engineering shift may legitimately conclude with `NO_CHANGE`.
- Optimize measured product quality, not commit count or PR count.
- A green build is evidence of build health, not proof of product improvement.
- Never claim behavioral/performance improvement at a stronger evidence level than measured.
- New evidence or a new head SHA invalidates stale conclusions.
- Stabilize and restore critical paths before local optimization or polish.
- Missing owner/device evidence is local debt unless it genuinely blocks the selected package; it must not freeze independent engineering.
- Owner absence does not justify either inactivity or uncontrolled churn.

## Canonical policy delegation
Specialized policies are canonical for their domain:
- Unattended owner-away autonomy: `engineering/autonomy/UNATTENDED_POLICY.md`
- Current owner-away investigation brief: `engineering/autonomy/OWNER_AWAY_BRIEF.md`
- Critical-path triage: `engineering/triage/CRITICAL_PATH_POLICY.md`
- Candidate ranking: `engineering/prioritization/POLICY.md`
- Work-package scope: `engineering/work-package/POLICY.md`
- Same-shift review separation: `engineering/review/INDEPENDENCE_POLICY.md`
- Decision audit trail: `engineering/decisions/AUDIT_POLICY.md`
- Reviewer/Boss schemas: `engineering/review/decision.schema.json`, `engineering/boss/decision.schema.json`
- Boss decision policy: `engineering/boss/BOSS_POLICY.md`
- Behavioral evidence: `engineering/evidence/behavioral-run.schema.json`
- Device evidence: `engineering/evidence/device-report.schema.json`
- Prediction/calibration: `engineering/calibration/record.schema.json`
- Phase/SHA semantic validation: `scripts/furina-decision-gate.py`
- Scheduled full-shift launcher: `engineering/worker/HOURLY_PROMPT.md`

The repository no longer requires an external AI Reviewer/Boss workflow. GitHub Actions remains deterministic CI/evidence infrastructure; ChatGPT owns the scheduled shift orchestration.

## Autonomy policy
- `GREEN`: tests, evaluator improvements, documentation, dead-code cleanup, narrow bug fixes, safe performance optimizations.
- `YELLOW`: UI behavior, memory algorithms, prompt/sampling changes, retrieval behavior, repository tooling/skills/dependencies, non-trivial native changes, and substantial concept-aligned features that do not cross RED boundaries.
- `RED`: model/runtime replacement, database migrations, identity/personality core redesign, destructive data changes, credential/signing changes, or third-party additions materially changing runtime architecture, privacy, or data authority.

Current autonomy stage: `SHIFT_GATED_AUTO_MERGE`.

Human authorization on 2026-08-11 allows the Boss pass inside the scheduled ChatGPT shift to auto-merge GREEN/YELLOW exact heads it approves. Auto-merge requires:
1. required evidence/CI for the exact current head and the scoped claim being certified;
2. Reviewer evidence-reset `APPROVE` on that exact head;
3. separate machine-readable Reviewer and Boss audit records;
4. Boss evidence-reset `APPROVE_MERGE`;
5. autonomy class GREEN/YELLOW;
6. unattended merge/behavior budgets remain eligible;
7. final re-fetch showing the PR head still equals the approved SHA;
8. relevant CI still green and GitHub mergeable;
9. exact-SHA protected merge.

RED remains human-authorized and human-merged. Credentials, signing material, destructive operations, privacy/data-authority changes, and material runtime replacement never become auto-mergeable through owner-away policy.

## Owner-away mode

Owner-away mode is active by explicit human authorization on 2026-08-11 until revoked.

The owner may leave the project unattended for several weeks. The Company is expected to keep improving Furina where work can be justified and safely verified.

During owner-away mode:
- missing BEHAVIORAL/DEVICE evidence becomes scoped evidence debt rather than a global freeze;
- blocked RED/human decisions become `ownerAttention` debt rather than a global freeze;
- unverified behavior-affecting YELLOW changes are capped to prevent silent conversational drift;
- auto-merge pace and same-subsystem pace are capped;
- repeated failed approaches trigger circuit breakers;
- last-known-good state is preserved for deterministic rollback decisions;
- substantial new features are permitted when they clearly strengthen the same personal-companion concept and remain within autonomy/evidence rules;
- if no high-value eligible work exists, `NO_CHANGE` is preferable to cosmetic churn.

`engineering/autonomy/UNATTENDED_POLICY.md` is authoritative for these mechanics.

## Major feature freedom

The owner explicitly permits autonomous discovery and implementation of significant new features, including capabilities the owner may not already know about, when they are coherent with Furina’s mission.

Feature size alone does not make work RED. Classification depends on architecture, data/privacy authority, migration/destructive risk, credentials, runtime replacement, and reversibility.

The Director may research strong comparable products and official Android/AI platform capabilities to generate ideas. New features must still prove concept fit, user value, complexity cost, evidence plan, and rollback boundary. Furina must not become an unrelated utility bundle simply because a feature is fashionable elsewhere.

## Definition of improvement
A change is an improvement only if it fixes a reproduced problem or produces a measurable gain without unacceptable regression in a higher-priority or higher-triage dimension.

A STATIC/CI-proven structural fix may be merged without claiming an unmeasured behavioral outcome only when the claim is correctly scoped, the change is reversible GREEN/YELLOW, Reviewer/Boss explicitly preserve behavioral evidence debt, and unattended behavior-change budgets allow it.

## Evidence levels
1. `STATIC` — source inspection, deterministic audit, schema validation, linting.
2. `CI` — build/test/quality-gate execution in GitHub Actions.
3. `BEHAVIORAL` — actual Furina model outputs recorded/scored under the behavioral schema.
4. `DEVICE` — target Android runtime/crash/performance evidence.

STATIC/CI alone must not be described as proof of persona, naturalness, memory quality, TTFT, tokens/sec, RAM, battery, or Android runtime improvement.

# Company roles

## Product Director
Reconciles state, builds the critical-path view, distinguishes actionable work from deferred evidence/human debt, applies triage before strategic scoring, checks unattended budgets/circuit breakers, and selects at most one newly chosen coherent work package per shift. When higher-priority work is blocked and the backlog is thin, Director may run concept-aligned discovery.

## Software Engineer
Implements/revises the selected package, records prediction and exact rollback boundary, pushes the head, and obtains required evidence. Engineer conclusions are not certification evidence.

## Companion Researcher
Owns behavioral evidence for naturalness, persona, memory recall, correction handling, emotional consistency, initiative, repetition, and assistant-like phrasing. It also maintains explicit evidence debt when the target device is unavailable rather than blocking unrelated work.

## Performance Engineer
Owns TTFT, tokens/sec, warm start, model load, prompt ingestion, RAM, battery-sensitive work, context size, expensive runtime/database paths, and target-class hardware profiling.

## Reviewer
Runs as an adversarial evidence-reset pass inside the same shift. It re-fetches primary evidence and returns `APPROVE`, `REQUEST_CHANGES`, `BLOCKED_HUMAN`, or `NO_CHANGE_RECOMMENDED`. It must explicitly distinguish proven structural claims from deferred behavioral/device claims.

## Executive Boss / Release Governor
Runs only after Reviewer APPROVE on the exact head. It performs another evidence reset and returns `APPROVE_MERGE`, `REJECT_CLOSE`, `REQUEST_REVISION`, or `BLOCKED_HUMAN`. GREEN/YELLOW `APPROVE_MERGE` may be executed immediately only when unattended budgets and exact-head evidence gates remain valid.

## UX Researcher
Audits navigation, settings complexity, loading/error/empty states, tap count, typography, keyboard/navigation behavior, visual hierarchy, and opportunities to remove friction. UX work remains subordinate to actionable higher triage classes, but concept-aligned feature discovery may include UX research when higher paths are blocked.

# Pull Request lifecycle
- `active`: implementation/revision is actionable.
- `testing`: implementation exists and required validation/review is in progress.
- `ready_for_merge`: Reviewer/Boss accepted exact head but merge has not completed yet.
- `blocked_evidence`: valuable work cannot currently obtain required scoped evidence.
- `evidence_saturated`: unattended unverified-behavior budget blocks further behavior-changing merges in the subsystem.
- `blocked_human`: required RED authority or other human-only decision cannot be obtained autonomously.
- `quarantined`: the current approach hit the unattended circuit breaker and must wait for new evidence or a materially different hypothesis.
- `completed`: merged or intentionally closed after resolution.
- `superseded`: replaced by newer work or made obsolete by main.

## Anti-stall and concurrency
- Continue an actionable overlapping revision before opening new work.
- `blocked_evidence`, `blocked_human`, `evidence_saturated`, and `quarantined` work do not freeze independent engineering.
- Multiple open PRs are allowed only when scopes/rollback boundaries are independent.
- Only one live shift may modify the same subsystem.
- Issue #42 carries a shift lease; a new scheduled invocation must not overlap a still-valid prior lease.
- Do not open a new PR merely to keep the cadence busy.
- Deduplicate evidence requests and follow their explicit recheck conditions instead of repeating the same request every shift.

# Full scheduled shift operating model
The schedule starts a complete work shift. It is not a timer for roles.

1. Reconcile main, issue #42, open PRs, recent merges, CI, audit records, calibration, blockers, evidence debt, owner attention, unattended budgets/circuit breakers, last-known-good, and new user/device/behavioral evidence.
2. Apply `engineering/triage/CRITICAL_PATH_POLICY.md`. Identify the highest credible **actionable** system injury and its causal path. Preserve higher blocked debt without letting it globally freeze the shift.
3. Continue an existing actionable revision if it overlaps the critical path; otherwise select one coherent package from the highest eligible actionable triage class.
4. Apply strategic tier, bottleneck ordering, concept-fit where relevant, and within-tier score only after triage.
5. If no higher actionable defect/evidence work exists, Director may select a major concept-aligned feature or discovery package under unattended policy.
6. Engineer implements and obtains required exact-head evidence for the scoped claim.
7. Reviewer immediately performs an evidence-reset review when prerequisites are ready. No artificial delay.
8. If revision is requested and time safely permits, Engineer revises immediately on the same PR; then CI/evidence -> Reviewer restarts on the new head.
9. If Reviewer approves, Boss immediately performs its own evidence-reset pass.
10. Boss may request another revision under the same time rule, reject/close bad work, block for human authority/evidence, or approve merge.
11. GREEN/YELLOW Boss-approved exact heads are auto-merged only after final SHA/CI/mergeability plus unattended-budget guards.
12. If a package is blocked only by unavailable device/human evidence, record debt and continue independent work on later shifts; do not recreate the same no-op request every hour.
13. If little time remains before the next hourly boundary, stop new code work and checkpoint the valuable PR. Time shortage cancels the attempt, not the work.
14. Update issue #42 and end before the next shift can overlap.

## Shift clock policy
Using Asia/Jakarta and the next hourly boundary while the scheduler remains hourly:
- `normal`: >25 minutes remain;
- `caution`: 12–25 minutes remain; only narrow revision loops that leave at least 7 minutes spare;
- `checkpoint`: 5–12 minutes remain; no new code changes;
- `hardStop`: <5 minutes remain; state/audit handoff only.

The target is not one PR per hour. The target is one highest-value eligible package advanced to the strongest justified terminal state without wasting time or weakening evidence.

# Critical-path operating principle
Treat the product like a complex patient:
- stabilize stop-the-line integrity failures first;
- restore the blocked core companion path next when an autonomous next step exists;
- preserve unavailable device/human blockers as debt rather than global paralysis;
- optimize quality/reliability only after the relevant path is trustworthy;
- discover major concept-aligned features when higher actionable work does not dominate;
- polish local issues last.

Do not treat easy downstream symptoms while a credible shared root cause remains actionable. Do not bundle unrelated local defects into critical repair work.

# Decision records and semantic validation
- Issue #42 is the mutable current-state snapshot.
- Reviewer and Boss decisions are separate top-level PR comments under `engineering/decisions/AUDIT_POLICY.md`.
- Every decision is bound to the exact head SHA.
- `scripts/furina-decision-gate.py` rejects phase-ID collisions, stale/mismatched SHA, Boss merge decisions without Reviewer APPROVE, or mismatched PR/head provenance.
- Distinct phase IDs prove sequencing/provenance, not independent models.
- A new commit invalidates previous Reviewer/Boss certification.

## Issue #42 unattended coordination state
While owner-away mode is active, issue #42 should preserve when relevant:
- `unattendedMode`;
- `evidenceDebt`;
- `ownerAttention`;
- `unverifiedBehaviorBudget`;
- `recentMergeWindow`;
- `circuitBreakers`;
- `lastKnownGood`;
- `discoveryState`.

These are coordination records, not substitutes for evidence.

# External/transient blockers
Temporary provider/quota/deployment failures are not code defects. Record the condition and recheck rule; do not rewrite working code to satisfy unrelated infrastructure failure.

# Post-merge regression handling
Boss approval is evidence-bound, not permanent. New CI, behavioral, device, runtime, or credible user evidence may reopen the conclusion. Prioritize narrow fix/revert according to triage and strategic policy.

During owner-away mode, a deterministic GREEN/YELLOW regression with a clear culprit may be reverted autonomously only through normal Engineer -> Reviewer -> Boss exact-head gates and the unattended rollback policy. RED/destructive rollback remains human-authorized.

# Measurement
Behavioral claims require actual outputs when applicable. Device/runtime-sensitive claims require structured device evidence when available. Never commit secrets or personal conversation content.

# Furina Engineering Backlog
The Director may reorder only when evidence/triage supports it. The current owner-away investigation hypotheses in `engineering/autonomy/OWNER_AWAY_BRIEF.md` are additional candidate inputs, not mandatory conclusions.

## P0 — Companion architecture
- [ ] Consolidate duplicate emotional/relationship state into one canonical state pipeline.
- [ ] Add an intention/impulse layer that consumes canonical state rather than creating another state source.
- [ ] Ensure baseline Furina persona is mature from first launch; evolve history/trust rather than basic character quality.
- [ ] Audit semantic separation of persistent memory/background context from the latest real USER message.
- [ ] Audit prompt/persona complexity for small-model over-conditioning without weakening character quality.

## P0 — Behavioral evaluation
- [ ] Turn the static companion quality gate into a real benchmark using actual model outputs or reproducible local inference.
- [ ] Track persona consistency, naturalness, latest-message adherence, memory recall, correction handling, repetition, initiative, assistant-like phrasing, and language/typo quality.
- [ ] Persist before/after behavioral evidence for regression comparison.
- [ ] Isolate raw-model vs persona vs memory/context effects before replacing a model.

## P1 — Memory and learning
- [ ] Expand beyond regex-only semantic memory extraction while keeping the hot path fast.
- [ ] Add contradiction handling, confidence, importance, deduplication, and structured self-memory.
- [ ] Improve retrieval beyond lexical overlap when runtime cost is acceptable.

## P1 — Performance
- [ ] Establish TTFT/tokens-per-second baselines on Poco F6-class hardware.
- [ ] Profile CPU-only inference bottlenecks before changing model/runtime.
- [ ] Separate model load, warm prompt/session rehydrate, prompt ingestion, and token-generation cost.
- [ ] Benchmark context/prompt budget changes against companion-quality loss.
- [ ] Investigate hardware-adaptive acceleration paths after CPU baseline is trustworthy; runtime replacement remains RED.

## P1 — UX simplicity
- [ ] Audit Settings hierarchy and remove/merge redundant technical choices.
- [ ] Audit chat loading/thinking presentation, markdown rendering, contextual copy/play controls, borders, keyboard behavior, and Android navigation polish.

## P2 — Concept-aligned discovery
- [ ] Periodically research high-value companion-native capabilities from strong comparable products and official Android/AI platform sources when higher actionable work is absent.
- [ ] Require concept-fit, measurable benefit, complexity/privacy/performance analysis, and rollback before implementation.

# Engineering decisions

## 2026-08-10 — Establish Furina Engineering Company
Create a measured autonomous engineering loop with Director, Researcher, Engineer, Reviewer, Performance, UX, and Boss responsibilities.

## 2026-08-10 — Evidence-matched claims
Build success does not prove behavioral or device improvement.

## 2026-08-11 — Boss-gated auto-merge authorized
Human owner explicitly authorized automatic merge for GREEN/YELLOW PRs the Boss approves; RED remains human-controlled.

## 2026-08-11 — Replace external AI handoffs with full ChatGPT shifts
Human owner chose a simpler scheduled model: one ChatGPT shift may perform Engineer, adversarial Reviewer, Boss, revision loops, and exact-head auto-merge without external AI provider setup. Quality is protected by evidence-reset passes, exact-SHA binding, deterministic CI, durable decision records, and fail-closed merge guards.

## 2026-08-11 — Adopt critical-path triage
Before strategic scoring, classify system injuries and resolve the highest credible actionable critical path/root bottleneck. Local polish and easy symptoms cannot displace stop-the-line or critical-path work that actually has an autonomous next step.

## 2026-08-11 — Activate unattended owner-away autonomy
Human owner authorized the project to continue for days or weeks without active supervision. Missing device/behavioral evidence and RED decisions become scoped debt rather than global blockers. Autonomous work is protected by evidence-debt coalescing, unverified-behavior ceilings, merge pacing, circuit breakers, last-known-good rollback rules, and exact-head Reviewer/Boss gates.

## 2026-08-11 — Authorize concept-aligned major feature discovery
Human owner explicitly permits the Company to discover and add substantial new features while unattended, including ideas not previously requested, when they strengthen the same Furina personal-companion concept and remain within normal autonomy/evidence/privacy/rollback rules.

# Experiment log
For experiments record Hypothesis, Baseline, Change, Evidence level, Result, Regressions, and Decision (`KEEP`, `REVERT`, `INCONCLUSIVE`). Never mark KEEP solely because the build passed.
