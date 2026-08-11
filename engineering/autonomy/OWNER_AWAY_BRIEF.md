# Furina Owner-Away Investigation Brief

## Status

Active owner handoff, authorized 2026-08-11. This file captures current product concerns and hypotheses so they survive the conversation that produced them. They are **investigation inputs, not predetermined conclusions**. Repository evidence may confirm, refine, or reject them.

The Company may discover higher-value problems or features that are not listed here.

## Product intent to preserve

Furina should feel like a polished local-first personal AI companion rather than a generic assistant with a character prompt. The desired direction is:
- natural and responsive conversation from first launch;
- convincing Furina-like identity without repetitive caricature;
- persistent memory that the model understands as background knowledge, not as fresh user text;
- fast local inference appropriate for daily Android use;
- offline-model freedom without adding an application-level refusal/personality layer whose purpose is to re-censor an uncensored local model;
- simple UX despite sophisticated internal memory/personality/runtime systems;
- safe local data handling and reversible engineering changes.

## Current high-value hypotheses

### H1 — Memory/context role semantics may be wrong

Observed architecture should be audited for whether retrieved memory, runtime state, or other private background context is concatenated into the same native `user` message as the latest real user text.

If confirmed, investigate a semantically explicit separation such as stable system/context framing or another runtime-supported channel so the model can distinguish:
- persistent memory/background knowledge;
- historical conversation roles;
- the latest actual USER message.

Success is not merely changing labels in a string; verify the native chat-template/runtime semantics actually preserve the distinction.

### H2 — Model preparation/prefill may be doing unnecessary work

The UI phase described as “menerapkan kepribadian” may represent system-prompt tokenization and prefill, context rehydration, or repeated context rebuilds rather than a lightweight persona toggle.

Profile cold load, warm session change, identity change, memory retrieval, and first-token latency separately. Prefer keeping model weights warm and avoid repeating stable prompt work when the native runtime can safely reuse it.

### H3 — Persona may be over-conditioned

Audit whether a 4B model receives too many simultaneous negative instructions, style prohibitions, state blocks, memory rules, register rules, and response-shape directives.

Compare a compact positive identity/persona core against the current prompt. The goal is stronger natural character expression, not fewer safeguards by assumption.

### H4 — Model quality must be isolated from application architecture

Before concluding that Qwen3.5 4B Deckard Heretic is intrinsically poor, compare reproducibly:
1. raw model with minimal neutral chat framing;
2. raw model + compact Furina persona;
3. persona + clean memory/context architecture;
4. current production stack when useful as baseline.

Track typo/language quality, naturalness, persona consistency, latest-message adherence, repetition, refusal behavior, TTFT, and tokens/sec.

If the raw model is already materially worse than a strong compatible 4B alternative, model replacement may become justified. Model/runtime replacement remains RED unless policy changes.

### H5 — Hardware/runtime utilization may be leaving large performance gains unused

Current local inference should be profiled before assuming the model itself is slow. Establish CPU prompt-processing and token-generation baselines on target-class Android hardware, then investigate hardware-adaptive settings and compatible acceleration paths.

Potential directions may include better CPU topology/thread tuning, Vulkan/GPU offload for llama.cpp-compatible models, or a separate optimized runtime such as LiteRT-LM for compatible model families. Treat runtime replacement or a materially new third-party runtime architecture as RED; research/benchmarks are allowed autonomously.

### H6 — Typo and Indonesian-language quality need root-cause isolation

Do not automatically attribute typo, odd phrasing, or weak Indonesian to quantization or model size. Test raw-model output first, then prompt/persona, then memory/context framing, then sampling/runtime. Fix the earliest layer where quality degrades.

## Major-feature freedom

The owner explicitly allows the Company to add substantial new features while away when they clearly strengthen the same personal-companion concept. The Director is encouraged to discover useful capabilities from strong comparable products and official Android/AI platform capabilities rather than limiting work to the owner’s existing feature list.

Examples of areas worth investigating when triage allows include proactive companion behavior, richer multimodal interaction, better on-device voice, contextual notifications, memory transparency/control, ambient or quick-access interaction, accessibility, offline robustness, and other companion-native capabilities. These are examples only, not a mandated roadmap.

Follow `engineering/autonomy/UNATTENDED_POLICY.md` concept-fit, evidence, pacing, and RED-authority rules.

## Owner-away success condition

When the owner returns after several weeks, the desired state is not “many commits.” It is:
- current `main` still builds and remains recoverable;
- no unbounded stack of unverified behavioral changes;
- meaningful core problems were diagnosed/fixed where evidence allowed;
- blocked evidence/human decisions are clearly queued rather than repeatedly retried;
- strong new concept-aligned features may have been added when justified;
- issue #42 provides a concise explanation of what changed, what remains uncertain, and what needs the owner next.
