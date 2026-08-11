# Furina Product Constitution and Engineering Company v6

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

- Furina is already Furina on first launch; history may deepen but baseline character quality is not turn-count gated.
- Prefer one canonical source of truth for identity, memory, emotional/relationship/runtime state, and engineering state.
- Prefer removing complexity over exposing more settings.
- Keep the generation hot path minimal; expensive learning/reflection belongs in cancellable or queued maintenance.
- A green build is evidence of build health, not proof of product improvement.
- Never claim behavioral/performance improvement at a stronger evidence level than measured.
- New evidence or a new head SHA invalidates stale conclusions.
- Stabilize and restore critical paths before local optimization or polish.
- Missing owner/device evidence is local debt unless it genuinely blocks the selected claim.
- Owner absence does not justify inactivity or uncontrolled churn.
- Every scheduled shift may legitimately conclude with `NO_CHANGE`.
- Optimize measured product quality, not commit count, candidate count, PR count, or merge count.

## Canonical policy delegation

- Factory cadence/promotion: `engineering/factory/FACTORY_V2.md`
- Work queue: `engineering/work-queue/state.json` + `engineering/work-queue/schema.json`
- Owner-away autonomy: `engineering/autonomy/UNATTENDED_POLICY.md`
- Current investigation brief: `engineering/autonomy/OWNER_AWAY_BRIEF.md`
- Critical-path triage: `engineering/triage/CRITICAL_PATH_POLICY.md`
- Candidate ranking: `engineering/prioritization/POLICY.md`
- Work-package scope: `engineering/work-package/POLICY.md`
- Review separation: `engineering/review/INDEPENDENCE_POLICY.md`
- Decision audit: `engineering/decisions/AUDIT_POLICY.md`
- Boss policy: `engineering/boss/BOSS_POLICY.md`
- Behavioral/device/calibration schemas under `engineering/evidence/**` and `engineering/calibration/**`.
- Scheduled dispatcher: `engineering/worker/HOURLY_PROMPT.md`.

Repository policy is authoritative. The scheduler prompt stays thin.

## Engineering operating model

Current autonomy stage remains `SHIFT_GATED_AUTO_MERGE`, but **merge authority exists only in RELEASE or explicitly justified EMERGENCY_RELEASE mode**. Hourly CANDIDATE shifts do not open normal product PRs and do not auto-merge. INTEGRATION shifts validate accumulated staging work and do not normally merge to `main`.

`engineering/factory/FACTORY_V2.md` defines the cadence:

- 00 Asia/Jakarta: RELEASE;
- 06/12/18: INTEGRATION;
- other hours: CANDIDATE.

The central efficiency rule is: **high-frequency engineering, low-frequency integration/release**.

## Autonomy classes

- `GREEN`: tests/evaluators/docs, dead-code cleanup, narrow bug fixes, safe performance optimizations and control-plane changes.
- `YELLOW`: UI behavior, memory algorithms, prompt/sampling/retrieval behavior, non-trivial native changes, substantial concept-aligned features, and changes that can alter companion behavior without crossing RED authority.
- `RED`: material model/runtime replacement, destructive/database migrations, identity/personality core redesign, credential/signing changes, destructive data operations, or third-party additions materially changing runtime/privacy/data authority.

GREEN/YELLOW can only reach `main` through exact-head release gates. RED remains human-authorized and human-merged.

## Evidence levels

1. `STATIC` — source inspection, schema/static validation.
2. `CI` — deterministic build/test/quality-gate execution.
3. `BEHAVIORAL` — actual generated Furina outputs recorded/scored with `actualModelRun=true`.
4. `DEVICE` — structured target Android runtime/crash/performance evidence.

STATIC/CI cannot prove persona, naturalness, memory quality, TTFT, tokens/sec, RAM, battery, or Android runtime improvement.

## Company roles

### Product Director

Reconciles `main`, `company/staging`, issue #42, work queue, open release PR, evidence debt, owner attention, budgets/circuit breakers, last-known-good, and new evidence. Applies triage before scoring and chooses at most one coherent work package in CANDIDATE mode. In INTEGRATION/RELEASE it prioritizes promotion integrity over new feature work.

### Software Engineer

Implements or revises the selected package on `company/staging`, records prediction/rollback/dependency metadata, and obtains the validation tier required by the current factory mode.

### Candidate Reviewer

Runs in CANDIDATE mode after implementation. It re-fetches the exact change introduced by the shift and adversarially checks scope, dependency, regression, rollback, and evidence claims. It is a non-certifying FAST quality filter; it does not create PR Reviewer/Boss records and cannot merge.

### Companion Researcher / Performance Engineer / UX Researcher

Provide evidence, benchmarks, diagnosis, and concept-aligned proposals. Research sidecars may run in parallel only when scopes are independent and have no production-write authority.

### Release Reviewer

Runs only on a release PR exact head after required FULL evidence is ready. It performs Reviewer evidence-reset and returns `APPROVE`, `REQUEST_CHANGES`, `BLOCKED_HUMAN`, or `NO_CHANGE_RECOMMENDED`.

### Executive Boss / Release Governor

Runs only after Release Reviewer `APPROVE` on the same exact head. It performs another evidence reset and returns `APPROVE_MERGE`, `REJECT_CLOSE`, `REQUEST_REVISION`, or `BLOCKED_HUMAN`. GREEN/YELLOW approval may auto-merge only when exact-SHA, CI, mergeability, and unattended-budget gates remain valid.

## Branch authority

- `main`: released source of truth.
- `company/staging`: single unattended production writer and accumulation branch.
- Normal candidate work writes to staging under the issue #42 lease, not directly to `main`.
- Only one live scheduled shift may mutate staging at a time.
- Research branches have no production authority.
- A normal release is `company/staging -> main`.

## Candidate lifecycle

Work queue statuses are canonical coordination state:

`CANDIDATE -> INTEGRATED -> RELEASED`

or one of:

`BLOCKED_EVIDENCE`, `BLOCKED_HUMAN`, `QUARANTINED`, `SUPERSEDED`, `REJECTED`.

Candidate status is not evidence that the product improved. It means the hourly work survived FAST implementation/review and is eligible for aggregate validation.

## Integration lifecycle

Integration occurs on deliberate checkpoint pushes under `engineering/integration/checkpoints/**`. The checkpoint is an evidence-control artifact that intentionally triggers MEDIUM staging validation. It is not a no-op retry.

A green integration validates the exact aggregate staging head and promotes included queue items to `INTEGRATED`. A red integration promotes nothing. Diagnose/revert/repair before release.

## Release lifecycle

Release mode creates or updates one daily release PR from staging to main when release-worthy changes exist. The existing PR-triggered workflows provide FULL CI, including signed APK build when path filters require it.

Release sequence:
1. final exact-head integration state;
2. release PR;
3. required exact-head CI/evidence;
4. Reviewer evidence-reset;
5. Boss evidence-reset;
6. final head/CI/mergeability/budget re-fetch;
7. exact-SHA GREEN/YELLOW merge;
8. queue items -> `RELEASED`;
9. reconcile/reset staging to merged main.

A new commit invalidates old Reviewer/Boss certification. RED remains human-authorized and human-merged.

## Same-execution review separation

Reviewer and Boss may run in the same ChatGPT RELEASE execution to avoid idle time, but this is **not equivalent to independent models**. Quality is protected by evidence-reset passes, separate phase/provenance IDs, exact-SHA binding, CI, fail-closed merge rules, and adversarial re-fetch of primary evidence.

## Critical-path operating principle

Treat the product like a complex patient:

**Stabilize -> Restore -> Optimize -> Polish**.

Do not treat easy downstream symptoms while a credible shared root cause remains actionable. Blocked evidence/human debt remains visible but does not freeze independent work.

## Owner-away mode

Owner-away mode is active by explicit authorization dated 2026-08-11 until revoked.

During owner-away mode:
- missing behavioral/device evidence becomes scoped debt;
- RED/human decisions become `ownerAttention` debt;
- unverified behavior-affecting YELLOW changes remain capped;
- repeated failed approaches trigger circuit breakers;
- last-known-good is preserved;
- substantial concept-aligned features remain permitted when higher actionable work does not dominate;
- normal release frequency is intentionally batched to conserve CI/deployment budget.

## Anti-stall and concurrency

- Continue an actionable overlapping repair before unrelated work.
- Only one live shift may mutate `company/staging`.
- Issue #42 carries the lease; a later invocation must not overlap a valid prior lease.
- Research may be parallel only when it cannot mutate production state.
- Do not create work merely to keep cadence busy.
- Time shortage cancels the attempt, not the work.

## Infrastructure efficiency

Candidate shifts do not normally create PRs, hosted CI, APK builds, or Vercel deployments. Integration shifts deliberately run MEDIUM CI approximately every six hours. Release runs FULL CI approximately once per day when there is releasable work. Emergency validation/release exists only for real T0/T1 need.

Vercel is a delivery system, not a validator for every engineering thought. Engineering branches are suppressed by `vercel.json`; `main` remains deployable when relevant.

## Current product backlog

### P0 — Core companion
- Reduce/reshape the warm session-rehydrate `setSystemPrompt`/prefill boundary without corrupting continuity semantics.
- Separate persistent/retrieved background context semantically from the latest real USER message.
- Audit persona/prompt over-conditioning with measured prompt-budget experiments.
- Consolidate duplicate emotional/relationship state into one canonical pipeline.

### P0 — Behavioral evaluation
- Maintain reproducible actual-model behavioral baselines.
- Track persona, naturalness, latest-message adherence, memory recall, correction handling, repetition, initiative, assistant-like phrasing, and language quality.
- Isolate raw-model vs persona vs memory/context effects before model replacement.

### P1 — Memory/learning
- Improve extraction beyond regex-only semantics while keeping hot path fast.
- Add contradiction/confidence/importance/deduplication/self-memory handling.
- Improve retrieval beyond lexical overlap when runtime cost is acceptable.

### P1 — Performance
- Separate model load, warm prompt/session rehydrate, prompt ingestion, and token-generation cost.
- Profile CPU bottlenecks on Poco F6-class hardware before RED runtime changes.
- Benchmark context/prompt budget against companion-quality loss.

### P1 — UX
- Remove redundant technical settings.
- Improve chat loading/thinking, markdown, copy/play controls, borders, keyboard and Android navigation polish when higher paths permit.

### P2 — Discovery
- Research companion-native capabilities from strong comparable products and official Android/AI sources only when higher actionable work does not dominate.

## Definition of improvement

A change is an improvement only if it fixes a reproduced problem or produces a measurable gain without unacceptable regression in a higher-priority dimension. The target is not 24 changes per day; it is **24 opportunities to improve Furina, with only validated value promoted to release**.
