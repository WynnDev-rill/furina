# Furina Human-Gated Engineering Policy

## Status and authority

This is the active authority model for scheduled Furina engineering. It supersedes any older unattended Factory/Reviewer/Boss text for scheduling, write authority, promotion, or merge authority.

Legacy Factory v2 documents may remain temporarily as historical engineering context while migration is completed. They do not grant a scheduled task permission to write, commit, push, open or modify pull requests, change issues, deploy, release, or merge.

## Roles

### Engineer — scheduled, read-only

The hourly Engineer is an inspection and diagnosis role only. It may read repository state, branches, commits, pull requests, checks, engineering evidence, issue state, architecture, runtime code, UX code, and relevant external technical evidence.

It must never mutate repository or deployment state. Specifically, a scheduled Engineer must not:
- edit or create repository files;
- commit or push;
- create, update, close, or merge pull requests;
- create or edit issues/comments;
- change branches, refs, rules, workflows, secrets, releases, or deployments;
- start implementation merely because it found a plausible improvement.

### Wynn — sole Reviewer/Boss

Wynn is the sole authority for approving, revising, or rejecting proposed work.

An explicit Wynn `APPROVE` for a specific finding or package in an interactive conversation is a **single authorization covering both implementation and merge** of that approved scope, provided all required validation gates pass and no material scope expansion or unresolved blocker appears.

No AI self-review, same-execution Reviewer, automated Boss, CI result, severity label, or autonomy class can create approval by itself.

## Hourly discovery target

Furina remains under active development, so each hourly report should actively search broadly enough to find **at least 5 distinct new or materially changed MEDIUM-to-HIGH value findings when legitimate findings exist**.

The target is a discovery floor, not permission to manufacture work. If fewer than five legitimate findings exist after broad inspection, report the real number and state that reaching five would require lowering quality.

Prioritize:
1. correctness and regressions;
2. offline AI quality, TTFT/token throughput, RAM/thermal/crash behavior;
3. persona, memory, context, retrieval, and natural conversation behavior;
4. Android/device/runtime reliability;
5. model download, storage, update/install, backup, privacy, and security;
6. user-visible UX blockers;
7. build/release reliability and major engineering bottlenecks.

Do not use cosmetic trivia, duplicate symptoms, speculative churn, or meta-engineering work to fill the quota.

## Required finding format

Each proposed finding must have a stable ID and include:
- priority/severity;
- exact evidence;
- explicit separation of FACT vs HYPOTHESIS;
- likely root cause;
- proposed change;
- expected benefit;
- risks and blast radius;
- exact files/subsystems likely affected;
- validation/tests required;
- confidence;
- recommendation;
- status `AWAITING WYNN APPROVAL`.

Unchanged findings should not be repeated merely to fill an hourly report. A materially changed finding keeps its stable ID and is reported as an update.

## Single-approval implementation flow

### Gate — Wynn approval

A proposal remains read-only until Wynn explicitly approves that specific finding or package in an interactive conversation.

That approval authorizes the interactive Engineer to:
1. re-fetch current `main` and relevant evidence;
2. create a fresh branch from current `main`;
3. implement only the approved scope;
4. make follow-up fixes that are necessary to complete that same approved scope;
5. run deterministic/static/CI/behavioral/device checks appropriate to the claims;
6. create or update a pull request for evidence gathering and review when useful;
7. merge the exact validated implementation head to `main` without asking Wynn for a second approval, once every mandatory gate is green and no unresolved blocker remains;
8. report the final merged SHA, changed files, validation results, and remaining non-blocking evidence debt.

Wynn approval is therefore **implementation approval and merge approval for the approved scope**.

A fresh Wynn approval is required before merge when any of the following occurs:
- implementation materially expands beyond the approved finding/package;
- the risk class or blast radius materially increases;
- a required validation fails in a way that changes the proposed design rather than requiring a narrow repair;
- new evidence shows the approved change is no longer the recommended action;
- the requested merge would include unrelated changes that Wynn did not approve.

A new commit does not by itself invalidate approval when it is a narrow repair inside the already approved scope. However, the exact final head must itself pass every mandatory merge gate before merge.

CI green is evidence, not independent authority. Merge authority comes from Wynn's prior approval; CI and other required evidence determine whether that authority may safely be exercised on the final head.

## Evidence truth

Use evidence labels truthfully:
- `STATIC`: source/deterministic inspection only;
- `CI`: hosted build/test evidence for exact head;
- `BEHAVIORAL`: actual model outputs with the declared model/runtime;
- `DEVICE`: structured evidence from the target Android device.

Never claim persona, naturalness, memory quality, latency, RAM, battery, thermal behavior, or crash stability from STATIC/CI alone when the claim requires behavioral/device evidence.

If the approved change has a mandatory device- or behavioral-specific acceptance criterion, lack of that evidence blocks merge unless Wynn explicitly approved a scope that does not require that criterion.

## Branch and staging policy

New approved implementation should normally start from current `main` on a fresh human-gated branch.

`company/staging` from Factory v2 is legacy state. Do not blindly merge or resurrect it. Any useful candidate stranded there must be selectively re-evaluated and ported onto current `main` with current tests and current evidence.

## Release and deployment authority

There is no scheduled auto-merge mode under this policy. Scheduled runs remain read-only.

Interactive work that Wynn has explicitly approved may merge automatically after its required gates pass, within the approved scope.

There is no scheduled deployment authority under this policy. Deployment requires the same explicit interactive scope authorization when deployment is part of the approved package.

Emergency severity does not create approval. An urgent finding should be reported prominently; Wynn still authorizes the package before interactive implementation or merge begins unless Wynn has already explicitly approved that same scope.

## Safe inactivity

`NO_NEW_FINDINGS` and fewer than five findings are valid when supported by honest inspection. Quality of findings outranks report volume.

## Success metric

Optimize released Furina product quality and decision quality per unit of user attention, engineering time, CI/deployment budget, device evidence, and regression risk. Do not optimize commits, pull requests, findings, merges, or scheduled-run count.
