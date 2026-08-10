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

## Autonomy policy
- GREEN: tests, evaluator improvements, documentation, dead-code cleanup, narrow bug fixes, safe performance optimizations. May be prepared automatically.
- YELLOW: UI behavior, memory algorithms, prompt/sampling changes, retrieval behavior. Always PR review.
- RED: model/runtime replacement, database migrations, identity/personality core redesign, destructive data changes. Human approval required before merge.

## Definition of improvement
A change is an improvement only if it fixes a reproduced problem or produces a measurable gain without unacceptable regressions in another priority dimension.

---

# Furina Engineering Company Roles

## Product Director
Owns prioritization. Reads the constitution, current metrics, recent diffs, open PRs, test results, and known debt. Selects at most one coherent objective per cycle. Does not code by default.

## Companion Researcher
Owns behavioral quality. Runs and extends scenarios for naturalness, persona, memory recall, correction handling, emotional consistency, initiative, repetition, and assistant-like phrasing. Produces evidence, not vague taste judgments.

## Performance Engineer
Owns TTFT, tokens/sec, warm start, model load, prompt ingestion, RAM, battery-sensitive work, context size, and expensive database/runtime paths. Rejects optimizations that materially damage companion quality.

## Software Engineer
Implements the Director's selected objective on a branch. Keeps scope narrow, updates tests/evals, and documents tradeoffs. Never silently expands scope.

## Reviewer
Acts independently from the implementing Engineer. Reviews diff, tests, product impact, complexity, regressions, and whether a simpler solution exists. Returns APPROVE, REQUEST_CHANGES, or NO_CHANGE_RECOMMENDED.

## UX Researcher
Periodically audits navigation, settings complexity, empty/error/loading states, tap count, duplicated choices, typography, keyboard behavior, Android navigation behavior, and visual hierarchy. Its default question is: what can be removed, combined, automated, or clarified?

---

# Hourly Operating Loop

Each scheduled cycle performs this sequence:

1. Read `engineering/COMPANY.md` and treat it as the product constitution, role charter, operating loop, backlog, and decision log.
2. Inspect latest `main`, open Furina Lab worker-state issue, open PRs, recent commits, CI, and current backlog.
3. Run deterministic diagnostics before making a proposal.
4. Identify candidate problems from code, tests, behavioral evals, CI, performance evidence, TODO/FIXME, duplicate concepts, and regressions.
5. Rank candidates using:
   `priority = impact * confidence * frequency / max(1, effort * regressionRisk)`.
6. Select at most ONE coherent objective.
7. If evidence is weak or expected benefit is small, record `NO_CHANGE` and stop.
8. Update the worker-state issue to show the selected objective and active roles.
9. For GREEN/YELLOW work, create a branch and implement the narrow change. RED work becomes a proposal only.
10. Run relevant tests and quality gates. A failure blocks completion.
11. Reviewer evaluates the diff independently.
12. Open a draft PR for acceptable work. Never auto-merge during the initial autonomous stage.
13. Update worker-state issue with outcome, metrics, PR, and a short event trail.
14. End the cycle. The next cycle starts from the resulting repository state.

## Concurrency
Only one engineering cycle may modify Furina at a time. If another active Furina Lab cycle or engineering PR is already in progress, the cycle should inspect/review it rather than start competing work.

## Anti-feature-creep rule
No cycle is required to produce a commit. `NO_CHANGE` is preferred to low-confidence cosmetic churn.

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

## P1 — Memory and learning
- [ ] Expand beyond regex-only semantic memory extraction while keeping the hot path fast.
- [ ] Add contradiction handling, confidence, importance, deduplication, and structured self-memory.
- [ ] Improve retrieval beyond lexical overlap when device/runtime cost is acceptable.
- [ ] Ensure deferred maintenance eventually executes during rapid chat instead of being postponed indefinitely.

## P1 — Performance
- [ ] Establish measured TTFT/tokens-per-second baselines on Poco F6-class hardware.
- [ ] Profile CPU-only inference bottlenecks before changing model or runtime.
- [ ] Benchmark prompt/context budget changes against companion-quality loss.

## P1 — UX simplicity
- [ ] Audit Settings hierarchy and remove/merge redundant technical choices.
- [ ] Audit chat loading/thinking presentation, markdown rendering, borders, keyboard behavior, and Android navigation polish.

---

# Engineering Decisions

## 2026-08-10 — Establish Furina Engineering Company
Decision: create a measured autonomous engineering loop with separate Director, Researcher, Engineer, Reviewer, Performance, and UX responsibilities.

Reason: one unconstrained agent that is required to change code every hour would optimize commit volume rather than product quality and would create feature creep/regressions.

## 2026-08-10 — Start at review-gated autonomy
Decision: autonomous cycles may audit, implement, test, and open draft PRs, but do not auto-merge product changes initially.

Reason: the company needs a behavioral track record before it receives merge authority.

## 2026-08-10 — Dashboard is separate from APK
Decision: Furina Lab is a separate web deployment. Its source may live beside Furina in the same repository, but it is not imported by the Android/web application build.

---

# Experiment Log

Use one section per experiment.

Required fields:
- Hypothesis
- Baseline
- Change
- Result
- Regressions
- Decision: KEEP / REVERT / INCONCLUSIVE

No experiment should be marked KEEP solely because the build passed.
