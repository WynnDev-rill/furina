# Turn-scoped background channel diagnosis — 2026-08-12 03:00

## Problem

`LocalLlamaProvider.stream()` currently concatenates `runtimeContext` and query-dependent retrieval into `effectiveMessage`, then passes the whole payload to `sendUserPrompt()`. This makes private background data structurally USER-role material (confirmed C2).

The existing `appendSystemContext()` primitive cannot be reused naively for per-turn retrieval. It appends SYSTEM-formatted tokens and a SYSTEM chat message after the stable identity boundary, and that mutable suffix remains in chat/KV state until `resetConversationKeepingSystemPrompt()`.

## Evidence boundary

Current runtime already has the primitives needed for a safer design:

1. `resetConversationKeepingSystemPrompt()` can return KV/chat state to the identity-only SYSTEM boundary when `stableIdentityPrefixReady` is true.
2. `appendSystemContext()` can append mutable SYSTEM/background material without advancing `system_prompt_position`.
3. `AiContext.sessionRehydrationPrompt` already contains session summary/recent history and is explicitly SYSTEM/background material.
4. `AiContext.turnContext` already combines runtime context plus query-dependent retrieval for the current request.

Therefore C2 does not require a new native mid-KV deletion primitive if local inference treats mutable conversation state as **turn-scoped** rather than accumulating USER/ASSISTANT KV indefinitely.

## Safe candidate architecture

At the beginning of every local generation turn:

1. Ensure an identity-only SYSTEM prefix exists. If not, rebuild it with `setSystemPrompt(identitySystemPrompt)` and mark `stableIdentityPrefixReady=true` only after success.
2. Call `resetConversationKeepingSystemPrompt()` so all prior session/retrieval/USER/ASSISTANT suffix state is removed.
3. Append the request's current `sessionRehydrationPrompt` as SYSTEM/background.
4. Append the request's current `turnContext` as a separate SYSTEM/background block when non-blank.
5. Call `sendUserPrompt(request.userMessage, ...)` with **only the literal latest user message**.
6. Do not persist retrieval fingerprints as proof that retrieval KV remains usable on later turns; each turn reconstructs current background from the request.

The next turn repeats the reset and therefore removes the previous turn's retrieval/runtime background before new retrieval is injected. Prior conversation continuity is reconstructed from `sessionRehydrationPrompt` (summary + recent history), which the orchestration layer already refreshes in `AiContext`.

## Why this is safer than middle-KV surgery

Attempting to remove only a temporary SYSTEM block after generation would require deleting a token range that precedes newly generated USER/ASSISTANT KV and then repairing positions/chat-template history. That creates a new correctness surface around KV compaction and template-state synchronization. The identity-reset primitive already provides a known boundary and avoids that complexity.

## Tradeoff

This architecture intentionally stops relying on indefinitely accumulated local USER/ASSISTANT KV between turns. Each turn re-prefills only mutable session continuity + current retrieval, while retaining the expensive stable identity prefix. This may cost more prompt processing than retaining every prior turn in KV, but it prevents stale retrieval and role contamination while preserving the main warm-session optimization target: identity prefix reuse.

## Fail-closed requirements

- If identity-only prefix establishment fails: do not mark readiness.
- If reset fails: invalidate readiness and fall back to full `coldStartPrompt` behavior; do not inject private context as USER.
- If session or turn SYSTEM append fails: fall back to a semantically safe full prompt path or abort the local turn; never concatenate background into `userMessage`.
- `loadedRetrievalFingerprint` must not be used to skip current-turn retrieval injection under this design.
- No latency, persona, memory-quality, or device claim is valid until MEDIUM compile plus DEVICE/BEHAVIORAL comparison.

## Implementation scope for the next runtime candidate

Prefer a provider-only change first. Reuse the accepted native reset/append primitives; no new JNI/C++ behavior should be added unless provider-only implementation proves insufficient. FAST review must specifically check first-turn cold state, identity change, reset failure, append failure, cancellation/error cleanup, and whether `request.userMessage` reaches `sendUserPrompt()` unmodified.
