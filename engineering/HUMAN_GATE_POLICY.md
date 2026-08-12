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

Wynn is the sole authority for approving, revising, or rejecting proposed work and for authorizing merge to `main`.

No AI self-review, same-execution Reviewer, automated Boss, CI result, severity label, or autonomy class substitutes for Wynn's decision.

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

## Two-approval implementation flow

### Gate 1 — plan approval

A proposal remains read-only until Wynn explicitly approves that specific finding or package in an interactive conversation.

After Gate 1 approval, an interactive Engineer may:
1. re-fetch current `main` and relevant evidence;
2. create a fresh branch from current `main`;
3. implement only the approved scope;
4. run deterministic/static/CI checks appropriate to the claim;
5. create a **draft** pull request for evidence gathering when useful;
6. report exact head SHA, changed files, test results, unresolved risks, and any evidence still requiring a target device or human action.

Gate 1 approval is **not merge approval**.

### Gate 2 — merge approval

The implementation must stop after testing/reporting. `main` remains unchanged until Wynn explicitly approves merge for the exact reviewed head.

A new commit after Wynn's merge review invalidates the previous merge approval and requires a fresh Gate 2 decision.

CI green is evidence, not merge authority.

## Evidence truth

Use evidence labels truthfully:
- `STATIC`: source/deterministic inspection only;
- `CI`: hosted build/test evidence for exact head;
- `BEHAVIORAL`: actual model outputs with the declared model/runtime;
- `DEVICE`: structured evidence from the target Android device.

Never claim persona, naturalness, memory quality, latency, RAM, battery, thermal behavior, or crash stability from STATIC/CI alone when the claim requires behavioral/device evidence.

## Branch and staging policy

New approved implementation should normally start from current `main` on a fresh human-gated branch.

`company/staging` from Factory v2 is legacy state. Do not blindly merge or resurrect it. Any useful candidate stranded there must be selectively re-evaluated and ported onto current `main` with current tests and current evidence.

## Release and deployment authority

There is no scheduled auto-merge mode under this policy.

There is no scheduled deployment authority under this policy.

Emergency severity does not create AI merge authority. An urgent finding should be reported prominently; Wynn still authorizes implementation and merge unless a separate explicit interactive instruction says otherwise.

## Safe inactivity

`NO_NEW_FINDINGS` and fewer than five findings are valid when supported by honest inspection. Quality of findings outranks report volume.

## Success metric

Optimize released Furina product quality and decision quality per unit of user attention, engineering time, CI/deployment budget, device evidence, and regression risk. Do not optimize commits, pull requests, findings, merges, or scheduled-run count.
