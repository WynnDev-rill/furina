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
- Keep the generation hot path minimal; expensive learning/reflection belongs in cancellable or queued maintenance.
- Every engineering shift may legitimately conclude with `NO_CHANGE`.
- Optimize measured product quality, not commit count or PR count.
- A green build is evidence of build health, not proof of product improvement.
- Never claim behavioral/performance improvement at a stronger evidence level than measured.
- New evidence or a new head SHA invalidates stale conclusions.
- Stabilize and restore critical paths before local optimization or polish.

## Canonical policy delegation
Specialized policies are canonical for their domain:
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
- Hourly full-shift launcher: `engineering/worker/HOURLY_PROMPT.md`

The repository no longer requires an external AI Reviewer/Boss workflow. GitHub Actions remains deterministic CI/evidence infrastructure; ChatGPT owns the hourly shift orchestration.

## Autonomy policy
- `GREEN`: tests, evaluator improvements, documentation, dead-code cleanup, narrow bug fixes, safe performance optimizations.
- `YELLOW`: UI behavior, memory algorithms, prompt/sampling changes, retrieval behavior, repository tooling/skills/dependencies, and non-trivial native changes.
- `RED`: model/runtime replacement, database migrations, identity/personality core redesign, destructive data changes, credential/signing changes, or third-party additions materially changing runtime architecture, privacy, or data authority.

Current autonomy stage: `SHIFT_GATED_AUTO_MERGE`.

Human authorization on 2026-08-11 allows the Boss pass inside the hourly ChatGPT shift to auto-merge GREEN/YELLOW exact heads it approves. Auto-merge requires:
1. required evidence/CI for the exact current head;
2. Reviewer evidence-reset `APPROVE` on that exact head;
3. separate machine-readable Reviewer and Boss audit records;
4. Boss evidence-reset `APPROVE_MERGE`;
5. autonomy class GREEN/YELLOW;
6. final re-fetch showing the PR head still equals the approved SHA;
7. relevant CI still green and GitHub mergeable;
8. exact-SHA protected merge.

RED remains human-authorized and human-merged. Credentials, signing material, destructive operations, and privacy/data-authority changes never become auto-mergeable through this policy.

## Definition of improvement
A change is an improvement only if it fixes a reproduced problem or produces a measurable gain without unacceptable regression in a higher-priority or higher-triage dimension.

## Evidence levels
1. `STATIC` — source inspection, deterministic audit, schema validation, linting.
2. `CI` — build/test/quality-gate execution in GitHub Actions.
3. `BEHAVIORAL` — actual Furina model outputs recorded/scored under the behavioral schema.
4. `DEVICE` — target Android runtime/crash/performance evidence.

STATIC/CI alone must not be described as proof of persona, naturalness, memory, TTFT, tokens/sec, RAM, battery, or Android runtime improvement.

# Company roles

## Product Director
Reconciles state, builds the critical-path view, applies triage before strategic scoring, and selects at most one newly chosen coherent work package per shift.

## Software Engineer
Implements/revises the selected package, records prediction and exact rollback boundary, pushes the head, and obtains required evidence. Engineer conclusions are not certification evidence.

## Companion Researcher
Owns behavioral evidence for naturalness, persona, memory recall, correction handling, emotional consistency, initiative, repetition, and assistant-like phrasing.

## Performance Engineer
Owns TTFT, tokens/sec, warm start, model load, prompt ingestion, RAM, battery-sensitive work, context size, and expensive runtime/database paths.

## Reviewer
Runs as an adversarial evidence-reset pass inside the same shift. It re-fetches primary evidence and returns `APPROVE`, `REQUEST_CHANGES`, `BLOCKED_HUMAN`, or `NO_CHANGE_RECOMMENDED`.

## Executive Boss / Release Governor
Runs only after Reviewer APPROVE on the exact head. It performs another evidence reset and returns `APPROVE_MERGE`, `REJECT_CLOSE`, `REQUEST_REVISION`, or `BLOCKED_HUMAN`. GREEN/YELLOW `APPROVE_MERGE` may be executed immediately with exact-SHA protection.

## UX Researcher
Audits navigation, settings complexity, loading/error/empty states, tap count, typography, keyboard/navigation behavior, visual hierarchy, and opportunities to remove friction. UX work remains subordinate to actionable higher triage classes.

# Pull Request lifecycle
- `active`: implementation/revision is actionable.
- `testing`: implementation exists and required validation/review is in progress.
- `ready_for_merge`: Reviewer/Boss accepted exact head but merge has not completed yet.
- `blocked_human`: required evidence or RED authority cannot be obtained autonomously.
- `completed`: merged or intentionally closed after resolution.
- `superseded`: replaced by newer work or made obsolete by main.

## Anti-stall and concurrency
- Continue an actionable overlapping revision before opening new work.
- `blocked_human` work does not freeze independent engineering.
- Multiple open PRs are allowed only when scopes/rollback boundaries are independent.
- Only one live shift may modify the same subsystem.
- Issue #42 carries a shift lease; a new hourly invocation must not overlap a still-valid prior lease.
- Do not open a new PR merely to keep the hourly cadence busy.

# Full hourly shift operating model
The hourly schedule starts a complete work shift. It is not a timer for roles.

1. Reconcile main, issue #42, open PRs, recent merges, CI, audit records, calibration, blockers, and new user/device/behavioral evidence.
2. Apply `engineering/triage/CRITICAL_PATH_POLICY.md`. Identify the highest credible system injury and its causal path.
3. Continue an existing actionable revision if it overlaps the critical path; otherwise select one coherent package from the highest eligible triage class.
4. Apply strategic tier, bottleneck ordering, and within-tier score only after triage.
5. Engineer implements and obtains required exact-head evidence.
6. Reviewer immediately performs an evidence-reset review when prerequisites are ready. No artificial delay.
7. If revision is requested and time safely permits, Engineer revises immediately on the same PR; then CI/evidence -> Reviewer restarts on the new head.
8. If Reviewer approves, Boss immediately performs its own evidence-reset pass.
9. Boss may request another revision under the same time rule, reject/close bad work, block for human authority/evidence, or approve merge.
10. GREEN/YELLOW Boss-approved exact heads are auto-merged after the final SHA/CI/mergeability guard.
11. If little time remains before the next hourly boundary, stop new code work and checkpoint the valuable PR. Time shortage cancels the attempt, not the work.
12. Update issue #42 and end before the next shift can overlap.

## Shift clock policy
Using Asia/Jakarta and the next hourly boundary:
- `normal`: >25 minutes remain;
- `caution`: 12–25 minutes remain; only narrow revision loops that leave at least 7 minutes spare;
- `checkpoint`: 5–12 minutes remain; no new code changes;
- `hardStop`: <5 minutes remain; state/audit handoff only.

The target is not one PR per hour. The target is one highest-value work package advanced to the strongest justified terminal state without wasting time or weakening evidence.

# Critical-path operating principle
Treat the product like a complex patient:
- stabilize stop-the-line integrity failures first;
- restore the blocked core companion path next;
- optimize quality/reliability only after the path is trustworthy;
- polish local issues last.

Do not treat easy downstream symptoms while a credible shared root cause remains actionable. Do not bundle unrelated local defects into critical repair work.

# Decision records and semantic validation
- Issue #42 is the mutable current-state snapshot.
- Reviewer and Boss decisions are separate top-level PR comments under `engineering/decisions/AUDIT_POLICY.md`.
- Every decision is bound to the exact head SHA.
- `scripts/furina-decision-gate.py` rejects phase-ID collisions, stale/mismatched SHA, Boss merge decisions without Reviewer APPROVE, or mismatched PR/head provenance.
- Distinct phase IDs prove sequencing/provenance, not independent models.
- A new commit invalidates previous Reviewer/Boss certification.

# External/transient blockers
Temporary provider/quota/deployment failures are not code defects. Record the condition and recheck rule; do not rewrite working code to satisfy unrelated infrastructure failure.

# Post-merge regression handling
Boss approval is evidence-bound, not permanent. New CI, behavioral, device, runtime, or credible user evidence may reopen the conclusion. Prioritize narrow fix/revert according to triage and strategic policy. RED/destructive rollback remains human-authorized.

# Measurement
Behavioral claims require actual outputs when applicable. Device/runtime-sensitive claims require structured device evidence when available. Never commit secrets or personal conversation content.

# Furina Engineering Backlog
The Director may reorder only when evidence/triage supports it.

## P0 — Companion architecture
- [ ] Consolidate duplicate emotional/relationship state into one canonical state pipeline.
- [ ] Add an intention/impulse layer that consumes canonical state rather than creating another state source.
- [ ] Ensure baseline Furina persona is mature from first launch; evolve history/trust rather than basic character quality.

## P0 — Behavioral evaluation
- [ ] Turn the static companion quality gate into a real benchmark using actual model outputs or reproducible local inference.
- [ ] Track persona consistency, naturalness, latest-message adherence, memory recall, correction handling, repetition, initiative, and assistant-like phrasing.
- [ ] Persist before/after behavioral evidence for regression comparison.

## P1 — Memory and learning
- [ ] Expand beyond regex-only semantic memory extraction while keeping the hot path fast.
- [ ] Add contradiction handling, confidence, importance, deduplication, and structured self-memory.
- [ ] Improve retrieval beyond lexical overlap when runtime cost is acceptable.

## P1 — Performance
- [ ] Establish TTFT/tokens-per-second baselines on Poco F6-class hardware.
- [ ] Profile CPU-only inference bottlenecks before changing model/runtime.
- [ ] Benchmark context/prompt budget changes against companion-quality loss.

## P1 — UX simplicity
- [ ] Audit Settings hierarchy and remove/merge redundant technical choices.
- [ ] Audit chat loading/thinking presentation, markdown rendering, contextual copy/play controls, borders, keyboard behavior, and Android navigation polish.

# Engineering decisions

## 2026-08-10 — Establish Furina Engineering Company
Create a measured autonomous engineering loop with Director, Researcher, Engineer, Reviewer, Performance, UX, and Boss responsibilities.

## 2026-08-10 — Evidence-matched claims
Build success does not prove behavioral or device improvement.

## 2026-08-11 — Boss-gated auto-merge authorized
Human owner explicitly authorized automatic merge for GREEN/YELLOW PRs the Boss approves; RED remains human-controlled.

## 2026-08-11 — Replace external AI handoffs with full ChatGPT shifts
Human owner chose a simpler hourly model: one ChatGPT shift may perform Engineer, adversarial Reviewer, Boss, revision loops, and exact-head auto-merge without external AI provider setup. Quality is protected by evidence-reset passes, exact-SHA binding, deterministic CI, durable decision records, and fail-closed merge guards.

## 2026-08-11 — Adopt critical-path triage
Before strategic scoring, classify system injuries and resolve the highest credible critical path/root bottleneck. Local polish and easy symptoms cannot displace stop-the-line or critical-path work.

# Experiment log
For experiments record Hypothesis, Baseline, Change, Evidence level, Result, Regressions, and Decision (`KEEP`, `REVERT`, `INCONCLUSIVE`). Never mark KEEP solely because the build passed.
