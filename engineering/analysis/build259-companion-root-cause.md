# Build #259 companion root-cause diagnosis

## Scope

This is a STATIC diagnosis package built from the canonical Build #259 behavioral/device baseline plus the current `main` source. It does not change APK/runtime behavior and does not claim that persona, memory quality, or device latency is improved.

## Canonical baseline

The accepted Build #259 evidence establishes:

- behavioral aggregate: 5.986/10;
- Furina persona mean: 4.688/10;
- latest-message mean: 8.125/10;
- every benchmark scenario reported `warmBeforePrepare=true`;
- warm prepare median: about 74.6 s, range about 52.1–114.1 s;
- first-token median: about 78.7 s;
- notable output failures include generic/customer-service tone, repeated `Hmph`, fabricated memory/canon, self-continuity fabrication, technical-help intent/usefulness failures, and visible Indonesian errors.

## Causal candidates

### C1 — session/identity rehydrate prefill is a confirmed latency boundary

**Static finding: CONFIRMED.**

`LocalLlamaProvider.prepare()` calls `engine.setSystemPrompt(context.coldStartPrompt)` whenever the model is warm but the session ID or identity fingerprint changes. `DeviceBehavioralBenchmark` intentionally gives every scenario a unique session ID, so every scenario crosses that exact production session-switch boundary while keeping model weights warm.

Therefore the measured 52–114 s `prepareMs` range is not model-file loading. It is dominated by work on the warm session-rehydrate boundary (system prompt formatting/tokenization/prefill and associated native reset work). The benchmark is representative of session switch/reopen preparation, not of every consecutive turn in one already-warm session.

**Consequence:** the UI phase described as applying personality can legitimately take a long time even with loaded weights; optimizing model load alone cannot solve this injury.

**Confidence:** 10/10 for the boundary attribution; DEVICE evidence is still required for any claim about the exact contribution of individual prompt sections or a future speedup.

### C2 — retrieved/runtime background context is semantically presented as USER text

**Static finding: CONFIRMED.**

`LocalLlamaProvider.stream()` builds `effectiveMessage` by concatenating `[PRIVATE RESPONSE CONTEXT]`, runtime/retrieval text, and the latest real user message, then sends the entire string through `engine.sendUserPrompt(...)`. The native boundary therefore receives one USER-role message containing both background knowledge and the actual user turn.

The marker text says background is not a request, but the chat role remains USER. A small model must infer the semantic distinction from prose rather than from role structure.

**Consequence:** H1 from the owner-away brief is confirmed as an architectural semantic defect/risk. It can plausibly contribute to fabricated continuity, memory overreaction, or treating remembered material as fresh user input. Behavioral causality and the best replacement framing remain unproven.

**Confidence:** 10/10 for the role/framing fact; 7/10 for contribution to observed behavioral failures.

### C3 — persona/system prompt is instruction-dense and mostly negative constraints

**Static finding: PLAUSIBLE, not yet causal.**

The stable identity prompt contains multiple sections and many simultaneous prohibitions covering canon, repetition, openings, answer length, psychoanalysis, dialect, pet names, customer-service phrasing, role-play narration, private-context leakage, and memory display, in addition to positive character traits. Runtime language/register and response-shape directives add more instructions per turn.

This is consistent with the owner-away over-conditioning hypothesis and with the low persona score, but source inspection cannot prove that shortening it improves behavior. It is also part of the warm session-rehydrate prefill payload, so its size necessarily contributes some prompt-ingestion work.

**Confidence:** 7/10 as a behavioral root-cause candidate; 10/10 that reducing stable prompt tokens would reduce the amount of prompt text to ingest, without claiming a measured device delta.

### C4 — raw Deckard model quality remains unresolved

**Finding: UNRESOLVED.**

The canonical benchmark measures the production stack, not raw model + minimal framing. Existing evidence cannot separate model-intrinsic Indonesian/typo quality from application prompt/context effects.

Do not replace the model based on Build #259 outputs alone. A raw/minimal-persona comparison remains the correct discriminator; model/runtime replacement remains RED.

### C5 — CPU/backend utilization remains a later performance candidate

**Finding: UNRESOLVED FOR THIS INJURY.**

The current runtime is CPU-oriented, but the canonical evidence shows a much narrower first root cause: an enormous warm prepare/rehydrate cost before token generation. Hardware acceleration may still be valuable, but changing runtime/backend before reducing or restructuring avoidable rehydrate work would mix two causes and cross RED boundaries if it becomes a material runtime replacement.

## Candidate ordering for the next repair package

1. **C1 rehydrate/prefill architecture** — T1 / L1 / P0_PRODUCT, dependency centrality 10, scope reach 9, evidence confidence 10. First quantify and reduce unnecessary stable/session prefill while preserving continuity semantics.
2. **C2 background-context role separation** — T1 / L1 / P0_PRODUCT, dependency centrality 9, scope reach 9, evidence confidence 10 for structural defect. Repair must preserve query-dependent retrieval without forcing a full system-prompt rehydrate every turn.
3. **C3 persona compaction** — T1 / L1 / P0_PRODUCT, dependency centrality 8, scope reach 8, evidence confidence 7. Prefer as part of a measured prompt-budget experiment rather than prose editing by intuition.
4. **C4 raw-model A/B** — T1 diagnosis, blocked for target-device model-run evidence once a capture boundary is worth requesting.
5. **C5 alternate acceleration/runtime** — P1 performance after C1 baseline is trustworthy; material runtime replacement remains RED.

## Important benchmark interpretation

The current 74.6 s median warm prepare must not be reported as the cost of every normal chat turn. It specifically measures repeated unique-session preparation. Same-session consecutive generation calls skip `setSystemPrompt` when session and identity are unchanged. The product injury is therefore cold/warm startup, session switching, identity change, evidence scenario isolation, and any path that invalidates the loaded session—not ordinary steady-state decoding by itself.

## Recommended next autonomous step

Prepare one reversible YELLOW package focused on the warm session-rehydrate boundary. Before behavior-changing implementation, add/retain exact measurements that separate stable identity prefill from session-continuity prefill and avoid solving C1 by moving continuity into the already-confirmed C2 USER-role defect. If the repair lacks target-device evidence, certify only structural/CI claims and charge the appropriate unverified-behavior slot; request fresh device evidence only at a stable verification boundary.

## Rollback boundary

This analysis file is evidence/diagnosis only and can be reverted independently with no APK/runtime effect.
