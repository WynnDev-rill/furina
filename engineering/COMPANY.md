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
- Prefer one canonical source of truth for identity, memory state, emotional state, relationship state, and runtime state.
- Prefer removing complexity over exposing more settings.
- A new feature requires a defined user benefit and a way to verify that benefit.
- Do not trade a large loss in persona or memory quality for a small latency gain.
- Do not trade a large latency regression for a cosmetic improvement.
- Do not add duplicate engines that model the same concept independently.
- Keep the generation hot path minimal; expensive learning/reflection belongs in cancellable or queued maintenance.
- Every engineering cycle may legitimately conclude with NO_CHANGE.
- The company optimizes measured product quality, not commit count.
- A green build is evidence of build health, not proof of product improvement.
- Never claim a behavioral or performance improvement at a stronger evidence level than was actually measured.

## Autonomy policy
- GREEN: tests, evaluator improvements, documentation, dead-code cleanup, narrow bug fixes, safe performance optimizations. May be prepared automatically.
- YELLOW: UI behavior, memory algorithms, prompt/sampling changes, retrieval behavior. Always PR review.
- RED: model/runtime replacement, database migrations, identity/personality core redesign, destructive data changes. Human approval required before implementation or merge.
- Current autonomy stage is REVIEW_GATED. The Executive Boss makes the final company decision on GREEN/YELLOW PRs, but a human still performs the final merge to `main`.

## Definition of improvement
A change is an improvement only if it fixes a reproduced problem or produces a measurable gain without unacceptable regressions in another priority dimension.

## Evidence levels
Use the strongest applicable evidence level and name it explicitly in PRs and worker state.

1. STATIC — source inspection, deterministic audit, schema validation, linting.
2. CI — build/test/quality-gate execution in GitHub Actions.
3. BEHAVIORAL — recorded or reproducible Furina model outputs scored against the companion rubric.
4. DEVICE — measurements or reproduction on a target Android device, including runtime/crash/performance evidence.

Rules:
- STATIC or CI alone must not be described as proof that persona, naturalness, memory quality, TTFT, tokens/sec, RAM, battery use, or Android crash behavior improved.
- If required evidence cannot be collected by the worker, mark the PR `blocked_human` with one concrete evidence request.
- New evidence should advance a decision. Repeating the same review with no new commit, test, or device/model evidence is not useful work.

---

# Furina Engineering Company Roles

## Product Director
Owns prioritization. Reads the constitution, current metrics, recent diffs, open PRs, test results, known debt, and blockers. Selects at most one coherent objective per cycle. Does not code by default.

## Companion Researcher
Owns behavioral quality. Runs and extends scenarios for naturalness, persona, memory recall, correction handling, emotional consistency, initiative, repetition, and assistant-like phrasing. Produces evidence, not vague taste judgments.

## Performance Engineer
Owns TTFT, tokens/sec, warm start, model load, prompt ingestion, RAM, battery-sensitive work, context size, and expensive database/runtime paths. Rejects optimizations that materially damage companion quality.

## Software Engineer
Implements the Director's selected objective on a branch. Keeps scope narrow, updates tests/evals, and documents tradeoffs. Never silently expands scope.

## Reviewer
Acts independently from the implementing Engineer. Reviews diff, tests, evidence level, product impact, complexity, regressions, and whether a simpler solution exists. Returns APPROVE, REQUEST_CHANGES, BLOCKED_HUMAN, or NO_CHANGE_RECOMMENDED. Reviewer approval is evidence for the Boss, not the final company decision.

## Executive Boss / Release Governor
Acts above the worker roles as the final company decision gate. The Boss does not write code and must independently inspect the actual PR diff, current `main`, CI, available behavioral/device evidence, Reviewer verdict, product value, regression risk, maintenance/complexity cost, conflicts, and reversibility. The Boss chooses exactly one conclusion for GREEN/YELLOW PRs: APPROVE_MERGE, REJECT_CLOSE, REQUEST_REVISION, or BLOCKED_HUMAN. In REVIEW_GATED mode, APPROVE_MERGE means the PR is company-approved and ready for the human owner to merge; the Boss does not directly write to `main`. The Boss may close a rejected draft PR because that action is reversible and does not modify `main`. RED work always remains human-authorized.

## UX Researcher
Periodically audits navigation, settings complexity, empty/error/loading states, tap count, duplicated choices, typography, keyboard behavior, Android navigation behavior, and visual hierarchy. Its default question is: what can be removed, combined, automated, or clarified?

---

# Pull Request Lifecycle

Every Furina engineering PR must be treated as one of these lifecycle states:

- `active`: implementation or revision is currently needed and can be performed by the worker.
- `testing`: implementation is complete and automated validation is still running or requires interpretation.
- `awaiting_boss`: Reviewer work is complete and the independent Boss decision is pending.
- `boss_approved`: Boss chose APPROVE_MERGE; the company considers the PR worth applying and only human merge remains in REVIEW_GATED mode.
- `revision_required`: Boss or Reviewer requested one coherent revision on the same branch/PR.
- `blocked_human`: progress requires evidence or a decision the company cannot obtain itself, such as physical-device reproduction, credentials, destructive approval, or RED authorization.
- `completed`: merged or intentionally closed after the objective is resolved.
- `superseded`: replaced by a newer PR or made obsolete by main.

## Anti-stall rules
- `active`, `testing`, and `revision_required` PRs block only overlapping or competing work.
- `awaiting_boss` and `boss_approved` PRs block overlapping work but do not freeze unrelated engineering.
- `blocked_human` PRs never freeze the whole company. Record the exact blocker once, then allow later cycles to select independent non-overlapping work.
- Do not spend a new cycle re-reviewing a `blocked_human` PR unless there is new evidence: a new commit, new CI result, model-output evidence, device report, Boss decision, or human decision.
- Multiple open PRs are allowed when their scopes are demonstrably independent; the Director must prevent conflicting edits and priority thrash.

---

# Hourly Operating Loop

Each scheduled cycle performs this sequence:

1. Read `engineering/COMPANY.md` and treat it as the product constitution, role charter, lifecycle policy, operating loop, backlog, and decision log.
2. Inspect latest `main`, issue #42, open PRs with lifecycle state, recent commits, CI, current backlog, and available behavioral/device evidence.
3. Run deterministic diagnostics before making a proposal.
4. Reconcile existing PRs first: detect new commits/evidence, assign lifecycle state, and identify whether any scope actually conflicts with new work.
5. Identify candidate problems from code, tests, behavioral evals, CI, performance evidence, TODO/FIXME, duplicate concepts, regressions, and stale blockers.
6. Rank candidates using:
   `priority = impact * confidence * frequency / max(1, effort * regressionRisk)`.
7. Select at most ONE coherent objective. A blocked PR with no new evidence is not automatically the objective.
8. If evidence is weak or expected benefit is small, record `NO_CHANGE` and stop.
9. Update issue #42 to show the selected objective, relevant PR lifecycle state, evidence level, and active roles.
10. For GREEN/YELLOW work, create or continue one branch and implement the narrow change. RED work becomes a proposal only.
11. Run relevant tests and quality gates. A required failure blocks completion.
12. Reviewer evaluates the diff independently and checks whether claims match evidence.
13. For an acceptable GREEN/YELLOW PR, move it to `awaiting_boss` and run the independent Executive Boss gate defined in `engineering/boss/BOSS_POLICY.md`.
14. Boss chooses exactly one: APPROVE_MERGE, REJECT_CLOSE, REQUEST_REVISION, or BLOCKED_HUMAN. Boss approval moves the PR to `boss_approved`; rejection may close the draft; revision returns one objective to the same branch; human/device uncertainty becomes `blocked_human`.
15. Never merge automatically during REVIEW_GATED autonomy. Human merge remains the final write to `main` after Boss approval.
16. If physical-device or model-output proof is required but unavailable, mark `blocked_human`, state exactly what evidence is needed, and do not keep re-litigating it every hour.
17. Update issue #42 with outcome, lifecycle state, evidence level, Boss decision/rationale when applicable, metrics, PR, blocker if any, and a short event trail.
18. End the cycle. The next cycle starts from the resulting repository state.

## Concurrency
Only one cycle may modify the same Furina subsystem at a time. Independent work may proceed while another PR is `blocked_human`, `awaiting_boss`, or `boss_approved`, provided the Director verifies that files, runtime behavior, and product objective do not conflict.

## Anti-feature-creep rule
No cycle is required to produce a commit. `NO_CHANGE` is preferred to low-confidence cosmetic churn.

---

# Measurement and Device Evidence

## Behavioral evidence
Behavioral claims should eventually be based on recorded model outputs or reproducible local inference, not only prompt/source inspection. At minimum, measure:
- latest-message adherence
- Furina persona consistency
- naturalness
- memory recall/use
- correction handling
- emotional consistency
- initiative
- non-repetition
- avoidance of generic customer-service tone

A structural evaluator may protect the benchmark contract, but it must not be presented as equivalent to executing the model.

## Device evidence
When a change touches local inference, Android process stability, storage, memory pressure, or latency, prefer a structured device report containing when available:
- app/build commit
- device/model and Android version
- model identifier and quantization
- model load time
- TTFT
- tokens/sec
- peak RSS/PSS or best available memory signal
- crash/exit reason
- scenario or reproduction steps
- pass/fail observation

The canonical schema is `engineering/evidence/device-report.schema.json`. Device reports may be attached as CI artifacts, issue/PR evidence, or committed sanitized fixtures when appropriate. Never place secrets or personal conversation content in evidence files.

---

# Boss Decision Policy

The detailed Boss contract is `engineering/boss/BOSS_POLICY.md`, with machine-readable output in `engineering/boss/decision.schema.json`.

Boss principles:
- The Boss is independent from the Engineer and Reviewer and must inspect primary evidence, not just summaries.
- A green build is never enough when the claimed improvement is behavioral, memory-related, performance-related, or Android-runtime-related.
- Passing CI and Reviewer approval are inputs, not commands.
- APPROVE_MERGE is appropriate only when expected product value clearly outweighs regression and maintenance cost with evidence appropriate to the claim.
- REJECT_CLOSE is a healthy outcome for unnecessary, weakly evidenced, obsolete, duplicative, or over-complex work.
- REQUEST_REVISION is preferred when one narrow fix can preserve a high-value objective.
- BLOCKED_HUMAN is used when missing evidence or authority cannot be obtained autonomously.
- RED work is never granted final merge authority by the Boss.

---

# Autonomy Promotion Policy

Auto-merge is intentionally disabled today. Promotion is a separate human decision, not something the loop grants itself.

A future Boss-gated merge stage may be proposed only after there is a meaningful track record showing all of the following:
- repeated completed cycles without autonomous regressions reaching `main`
- required CI consistently passing on accepted PRs
- Reviewer and Boss decisions agreeing with later observed outcomes
- behavioral claims backed by behavioral evidence when behavior is affected
- device/runtime claims backed by device evidence when device behavior is affected
- rollback remains simple and no signing/credential/destructive scope is involved

Even after promotion:
- GREEN may become eligible for Boss-executed merge after a separate human policy decision.
- YELLOW remains human-merged unless explicitly promoted by a later policy decision.
- RED remains human-approved and human-merged.

---

# Furina Engineering Backlog

The Product Director may reorder this list only when new evidence supports a different priority.

## P0 — Companion architecture
- [ ] Consolidate duplicate emotional/relationship state into one canonical state pipeline.
- [ ] Add an intention/impulse layer that consumes canonical state rather than creating another state source.
- [ ] Ensure baseline Furina persona is mature from first launch; evolve history/trust rather than basic character quality.

## P0 — Behavioral evaluation
- [ ] Turn the current static companion quality gate into a real behavioral benchmark using recorded model outputs or reproducible local inference runs.
- [ ] Track persona consistency, naturalness, latest-message adherence, memory recall, correction handling, repetition, initiative, and assistant-like phrasing.
- [ ] Persist before/after behavioral evidence so regressions can be compared across PRs.

## P1 — Memory and learning
- [ ] Expand beyond regex-only semantic memory extraction while keeping the hot path fast.
- [ ] Add contradiction handling, confidence, importance, deduplication, and structured self-memory.
- [ ] Improve retrieval beyond lexical overlap when device/runtime cost is acceptable.
- [ ] Ensure deferred maintenance eventually executes during rapid chat instead of being postponed indefinitely.

## P1 — Performance
- [ ] Establish measured TTFT/tokens-per-second baselines on Poco F6-class hardware.
- [ ] Profile CPU-only inference bottlenecks before changing model or runtime.
- [ ] Benchmark prompt/context budget changes against companion-quality loss.
- [ ] Ingest structured Android device reports into engineering decisions.

## P1 — UX simplicity
- [ ] Audit Settings hierarchy and remove/merge redundant technical choices.
- [ ] Audit chat loading/thinking presentation, markdown rendering, borders, keyboard behavior, and Android navigation polish.

---

# Engineering Decisions

## 2026-08-10 — Establish Furina Engineering Company
Decision: create a measured autonomous engineering loop with separate Director, Researcher, Engineer, Reviewer, Performance, and UX responsibilities.

Reason: one unconstrained agent that is required to change code every hour would optimize commit volume rather than product quality and would create feature creep/regressions.

## 2026-08-10 — Start at review-gated autonomy
Decision: autonomous cycles may audit, implement, test, review, and reach a Boss decision, but do not auto-merge product changes initially.

Reason: the company needs a behavioral track record before it receives direct merge authority.

## 2026-08-10 — Dashboard is separate from APK
Decision: Furina Lab is a separate web deployment. Its source may live beside Furina in the same repository, but it is not imported by the Android/web application build.

## 2026-08-10 — Engineering Company v2 anti-stall lifecycle
Decision: classify PRs with explicit active/testing/awaiting_boss/boss_approved/revision_required/blocked_human/completed/superseded lifecycle and allow independent work to continue around human-blocked or Boss-approved PRs.

Reason: an hourly company that repeatedly re-reviews the same device-blocked PR is not autonomous; it is stalled. Blockers must be explicit without freezing unrelated progress.

## 2026-08-10 — Evidence-matched claims
Decision: distinguish STATIC, CI, BEHAVIORAL, and DEVICE evidence and prevent stronger product claims than the available evidence supports.

Reason: build success cannot prove naturalness, persona quality, Android stability, or device performance.

## 2026-08-10 — Add Executive Boss decision gate
Decision: add a non-coding Executive Boss above the worker roles. Reviewer approval is no longer the final company conclusion. The Boss independently decides APPROVE_MERGE, REJECT_CLOSE, REQUEST_REVISION, or BLOCKED_HUMAN after examining primary evidence and product tradeoffs.

Reason: technical correctness alone does not mean a change deserves to enter the product. A separate final authority should decide whether the expected value justifies regression and maintenance cost.

## 2026-08-10 — Auto-merge remains disabled
Decision: Boss approval certifies a PR as worth applying but human merge remains required while autonomy is REVIEW_GATED.

Reason: the Boss decision layer should build a track record before being given direct write authority to `main`.

---

# Experiment Log

Use one section per experiment.

Required fields:
- Hypothesis
- Baseline
- Change
- Evidence level
- Result
- Regressions
- Decision: KEEP / REVERT / INCONCLUSIVE

No experiment should be marked KEEP solely because the build passed.
