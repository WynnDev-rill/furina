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
- The company optimizes measured product quality, not commit count or PR count.
- A green build is evidence of build health, not proof of product improvement.
- Never claim a behavioral or performance improvement at a stronger evidence level than was actually measured.
- New evidence or a new head SHA invalidates stale conclusions.

## Canonical policy delegation
This constitution defines product intent, authority, lifecycle, and the high-level operating model. Specialized policies are canonical extensions for their domain and must not be duplicated here:

- Candidate ranking: `engineering/prioritization/POLICY.md`
- Work-package scope: `engineering/work-package/POLICY.md`
- Reviewer/Boss execution independence: `engineering/review/INDEPENDENCE_POLICY.md`
- Decision audit trail: `engineering/decisions/AUDIT_POLICY.md`
- Reviewer decision schema: `engineering/review/decision.schema.json`
- Boss policy and schema: `engineering/boss/BOSS_POLICY.md` and `engineering/boss/decision.schema.json`
- Behavioral evidence: `engineering/evidence/behavioral-run.schema.json`
- Device evidence: `engineering/evidence/device-report.schema.json`
- Prediction/calibration: `engineering/calibration/record.schema.json`
- Semantic cycle/SHA validation: `scripts/furina-decision-gate.py`
- Event-driven Reviewer/Boss orchestration: `.github/workflows/furina-autonomous-gate.yml`
- Hourly shift launcher: `engineering/worker/HOURLY_PROMPT.md`

When a specialized policy changes, this file should reference it rather than copy its operational formula or state machine.

## Autonomy policy
- `GREEN`: tests, evaluator improvements, documentation, dead-code cleanup, narrow bug fixes, safe performance optimizations.
- `YELLOW`: UI behavior, memory algorithms, prompt/sampling changes, retrieval behavior, repository tooling/skills/dependencies, and non-trivial native changes.
- `RED`: model/runtime replacement, database migrations, identity/personality core redesign, destructive data changes, credential/signing changes, or third-party additions that materially change runtime architecture, privacy, or data authority.

Current autonomy stage: `BOSS_GATED_AUTO_MERGE`.

Human authorization on 2026-08-11 promotes GREEN/YELLOW engineering PRs to Boss-gated auto-merge. Privileged orchestration applies only to PRs explicitly marked `<!-- FURINA_COMPANY_PR_V1 -->`. A PR may merge automatically only when all of the following hold:
1. the exact current head SHA has passed required CI;
2. an independent Reviewer record for that exact head returns `APPROVE`;
3. `scripts/furina-decision-gate.py` validates Reviewer/Boss semantic independence;
4. a separate Boss execution returns `APPROVE_MERGE`;
5. the Boss classifies the change `GREEN` or `YELLOW`;
6. the PR head has not moved after either decision;
7. GitHub reports the PR mergeable.

`RED` remains human-authorized and human-merged. Credentials, signing material, destructive operations, and privacy/data-authority changes never become auto-mergeable through this policy.

## Definition of improvement
A change is an improvement only if it fixes a reproduced problem or produces a measurable gain without unacceptable regressions in a higher-priority dimension.

## Evidence levels
Use the strongest applicable level and name it explicitly:
1. `STATIC` — source inspection, deterministic audit, schema validation, linting.
2. `CI` — build/test/quality-gate execution in GitHub Actions.
3. `BEHAVIORAL` — actual Furina model outputs recorded and scored under the behavioral evidence schema.
4. `DEVICE` — target Android device/runtime/crash/performance evidence.

STATIC or CI alone must not be described as proof that persona, naturalness, memory quality, TTFT, tokens/sec, RAM, battery use, or Android runtime behavior improved.

# Company roles

## Product Director
Owns prioritization. Reconciles current state, active PRs, recent regressions, backlog, evidence, and blockers. Selects one coherent work package for an hourly shift. Candidate ranking is delegated to `engineering/prioritization/POLICY.md`.

## Software Engineer
Implements the selected work package on one branch/PR, updates tests/evals, records prediction/calibration inputs, and stops after implementation plus required validation has been launched. It does not certify its own head.

## Companion Researcher
Owns behavioral evidence for naturalness, persona, memory recall, correction handling, emotional consistency, initiative, repetition, and assistant-like phrasing.

## Performance Engineer
Owns TTFT, tokens/sec, warm start, model load, prompt ingestion, RAM, battery-sensitive work, context size, and expensive runtime/database paths.

## Reviewer
Runs in a fresh execution context separate from Engineer. Inspects the exact diff, tests, evidence, strategic allocation, regressions, scope, and simpler alternatives. Returns exactly `APPROVE`, `REQUEST_CHANGES`, `BLOCKED_HUMAN`, or `NO_CHANGE_RECOMMENDED`.

## Executive Boss / Release Governor
Runs in a fresh execution context separate from Engineer and Reviewer. Inspects primary evidence again and returns exactly `APPROVE_MERGE`, `REJECT_CLOSE`, `REQUEST_REVISION`, or `BLOCKED_HUMAN`. Under `BOSS_GATED_AUTO_MERGE`, `APPROVE_MERGE` authorizes the event-driven gate to merge a GREEN/YELLOW PR if all deterministic prerequisites still hold.

## UX Researcher
Audits navigation, settings complexity, loading/error/empty states, tap count, typography, keyboard/navigation behavior, visual hierarchy, and opportunities to remove or automate friction.

# Pull Request lifecycle
Every Furina engineering PR uses one lifecycle:
- `active`: implementation/revision is actionable.
- `testing`: implementation exists and required validation/review is in progress.
- `ready_for_merge`: Reviewer and Boss accepted the exact head, but the actual merge has not completed yet.
- `blocked_human`: required evidence or RED authority cannot be obtained autonomously.
- `completed`: merged or intentionally closed after resolution.
- `superseded`: replaced by newer work or made obsolete by `main`.

A `ready_for_merge` state should normally be brief in `BOSS_GATED_AUTO_MERGE`; the orchestrator should merge immediately when deterministic merge prerequisites are satisfied. If GitHub or an external condition prevents the merge, preserve the exact blocker rather than opening another overlapping PR.

## Anti-stall and concurrency
- An existing `active` or revision-requested PR for a product scope is continued before opening an overlapping PR.
- `blocked_human` work does not freeze unrelated engineering.
- Multiple open PRs are allowed only when their scopes and rollback boundaries are demonstrably independent.
- Only one shift may modify the same Furina subsystem at a time.
- No new PR should be opened merely to keep an hourly cadence busy.

# Event-driven hourly operating model
The hourly schedule is a **shift trigger**, not a timer for individual roles.

A normal shift is:
1. Reconcile `main`, issue #42, open PRs, recent merges, CI, Reviewer/Boss audit records, calibration, and new behavioral/device/user evidence.
2. Continue the highest-priority actionable revision first; otherwise select one coherent work package using `engineering/prioritization/POLICY.md`.
3. If no sufficiently valuable package exists, record `NO_CHANGE`.
4. Engineer implements one coherent package, commits/pushes the PR head, and launches required CI.
5. Engineer stops. It does not wait for a fixed Reviewer time and does not self-review.
6. `.github/workflows/furina-autonomous-gate.yml` reacts to the updated PR. As soon as required CI for the exact head is green, it starts an independent Reviewer job.
7. If Reviewer returns `APPROVE`, a separate Boss job starts immediately. There is no artificial wall-clock delay between jobs.
8. If Boss returns `APPROVE_MERGE` for GREEN/YELLOW and the exact head still matches, the gate auto-merges.
9. If Reviewer or Boss requests revision, the same PR remains `active`; the next Engineer execution continues it rather than opening a competing PR.
10. If required evidence/authority is unavailable, classify the exact blocker once and allow unrelated work later.
11. The next hourly shift starts from the resulting repository state.

The target is not “one PR per hour.” The target is “at most one newly selected work package per shift, completed as far as evidence permits without wasting elapsed time.”

# Decision records and semantic validation
- Issue #42 is a mutable current-state snapshot, not the durable decision log.
- Reviewer and Boss decisions are separate PR comments using the markers defined in `engineering/decisions/AUDIT_POLICY.md`.
- Every decision is bound to the exact head SHA.
- `scripts/furina-decision-gate.py` must reject equal role cycle IDs, stale/mismatched SHA, a Boss decision without an APPROVE Reviewer record, or mismatched PR/head provenance.
- Role labels inside one model response are not independent review.
- Separate GitHub Actions jobs count as separate execution contexts only when they use fresh prompts/processes and do not share a model conversation.

# External/transient blockers
Temporary Vercel/provider/quota failures are not code defects.
- Do not rewrite working code to satisfy an external transient failure.
- Record provider/condition and a concrete recheck condition.
- If deployment is not evidence required for the claim, it does not block Reviewer/Boss approval.
- Never hide a genuine code, runtime, behavioral, device, or CI regression behind an external-blocker label.

# Post-merge regression handling
Boss approval is evidence-bound, not permanent. New CI, behavioral, device, runtime, or credible user evidence may reopen the conclusion. If a merged regression is plausibly caused by the latest change, prioritize a narrow fix or revert according to the strategic priority policy. RED/destructive rollback remains human-authorized.

# Measurement
Behavioral claims should eventually be based on actual generated outputs, not only prompt/source inspection. Device/runtime-sensitive work should use the structured device evidence schema when available. Never commit secrets or personal conversation content as evidence.

# Furina Engineering Backlog
The Director may reorder only when new evidence supports it.

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
Create a measured autonomous engineering loop with separate Director, Researcher, Engineer, Reviewer, Performance, UX, and Boss responsibilities.

## 2026-08-10 — Evidence-matched claims
Distinguish STATIC, CI, BEHAVIORAL, and DEVICE evidence. Build success does not prove behavioral or device improvement.

## 2026-08-10 — Anti-stall lifecycle
Use one canonical lifecycle and allow independent work while unrelated items are blocked.

## 2026-08-10 — External blockers are not code defects
Classify recoverable infrastructure quotas/outages separately and stop pointless retry commits.

## 2026-08-11 — Consolidate strategic prioritization and independent certification
Delegate ranking to `engineering/prioritization/POLICY.md`, require exact-SHA Reviewer/Boss records, deterministic semantic validation, and separate execution contexts.

## 2026-08-11 — Promote to Boss-gated auto-merge
Human owner explicitly authorized automatic merge for PRs the Boss approves. GREEN/YELLOW may auto-merge only after exact-head CI, independent Reviewer APPROVE, deterministic semantic validation, and separate Boss APPROVE_MERGE. RED remains human-authorized and human-merged.

# Experiment log
For experiments, record Hypothesis, Baseline, Change, Evidence level, Result, Regressions, and Decision (`KEEP`, `REVERT`, or `INCONCLUSIVE`). Never mark KEEP solely because the build passed.
