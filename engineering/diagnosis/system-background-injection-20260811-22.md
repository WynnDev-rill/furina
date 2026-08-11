# Warm session SYSTEM/background injection proof — 2026-08-11 22:00

## Scope

This note resolves the remaining design ambiguity before wiring `resetConversationStateKeepingModel()` into ordinary local session switching. It is STATIC evidence only: no latency, persona, memory-quality, or device improvement is claimed.

## Current facts re-fetched on `company/staging`

1. `AiContext` now exposes `identitySystemPrompt` separately from `sessionRehydrationPrompt`. The latter is explicitly SYSTEM/background material and must never be merged into the latest USER turn.
2. `LocalLlamaProvider.prepare()` still uses `setSystemPrompt(coldStartPrompt)` on warm session changes, so the expensive stable identity prefix is still rebuilt.
3. The pinned llama.android formatter already supports arbitrary chat roles through `chat_add_and_format(role, content)`. Furina's deterministic runtime patch uses the model's Jinja template and computes only the incremental suffix relative to existing `chat_msgs`.
4. `processSystemPrompt()` is unsuitable for session-only continuity because it calls `reset_long_term_states()` and then updates `system_prompt_position`, making the whole identity+continuity block part of the preserved prefix.
5. The accepted reset primitive deliberately preserves KV only through `system_prompt_position`, trims template-visible history back to the first SYSTEM message, and removes everything after that position. Therefore mutable session continuity must be decoded *after* the stable identity boundary and must not advance `system_prompt_position`.

## Safe primitive

Add a narrowly scoped inference API such as:

```kotlin
suspend fun appendSystemContext(systemContext: String)
```

Its native implementation should:

- require a loaded context and a valid `system_prompt_position > 0`;
- reject blank input at the Kotlin boundary;
- format the new material with `chat_add_and_format(ROLE_SYSTEM, systemContext)` so it is represented as SYSTEM/background in the chat template;
- tokenize and decode only the incremental suffix at `current_position`;
- **not** call `reset_long_term_states()`;
- **not** update `system_prompt_position`;
- fail closed if the appended context cannot fit after the preserved identity prefix rather than silently truncating continuity;
- generate no assistant tokens and leave the engine in `ModelReady`.

This yields the intended native state:

```text
KV: [stable identity SYSTEM prefix] | [session SYSTEM/background continuity] | USER | ASSISTANT ...
     ^ system_prompt_position
```

On a session switch with unchanged identity:

```text
resetConversationKeepingSystemPrompt()
  => [stable identity SYSTEM prefix]
appendSystemContext(newSessionContinuity)
  => [stable identity SYSTEM prefix] | [new session SYSTEM/background continuity]
```

The next real user message remains a distinct USER message.

## Provider wiring boundary

`LocalLlamaProvider` should use the fast path only when the loaded model and identity fingerprint are unchanged and the runtime is known to have an identity-only preserved prefix. A provider flag such as `stableIdentityPrefixReady` is needed because the existing fail-closed fallback `setSystemPrompt(coldStartPrompt)` creates a combined identity+session prefix that must **not** later be treated as identity-only.

Recommended transition rules:

- cold load / identity change: establish `setSystemPrompt(identitySystemPrompt)`, then append `sessionRehydrationPrompt` as SYSTEM/background;
- same identity + changed session + `stableIdentityPrefixReady`: native reset, then append new session continuity;
- any reset/append failure: fall back to `setSystemPrompt(coldStartPrompt)`, mark `stableIdentityPrefixReady = false`, invalidate session/retrieval fingerprints, and make no latency claim;
- a later fast-path attempt from `stableIdentityPrefixReady = false` must first rebuild an identity-only prefix; it must never preserve an old combined prefix.

## Why the tempting USER shortcut is rejected

`LocalLlamaProvider.stream()` currently places runtime/retrieval background and the latest user text in one `sendUserPrompt()` payload. Confirmed C2 already identifies this role-sharing boundary as a quality risk. Putting session rehydration there would make long-lived private continuity indistinguishable from user intent and would increase prompt pressure on every turn. The safe path is a separate SYSTEM/background decode.

## Adversarial risks to verify during implementation

1. Consecutive SYSTEM messages must remain prefix-stable under the pinned Qwen3.5 Jinja template. The existing formatter computes an incremental suffix and has a compatibility fallback; MEDIUM compile/quality validation must confirm the patch remains deterministic.
2. `appendSystemContext` must not mutate `system_prompt_position`; otherwise the following reset would preserve stale session continuity.
3. Context overflow must fail closed. Calling the normal shifting path while adding rehydration could discard mutable tokens in surprising ways and blur the stable boundary.
4. A partial append failure must not leave provider fingerprints claiming the new session is loaded.
5. The bootstrap/AAR cache key must include changes to the deterministic warm-session patch path, or the APK could accidentally reuse an older AAR.

## Verification ladder

- FAST: exact diff inspection, deterministic replacement reasoning, provider-state invariants, no USER-role regression.
- MEDIUM: pinned AAR patch applies, Kotlin/native compile, Engineering OS + Companion Quality green on exact checkpoint head.
- DEVICE/BEHAVIORAL before performance claims: compare Build 259 baseline against cold prepare, same-identity session switch prepare, first-token latency, session isolation, latest-message relevance, persona, and crash/RAM behavior.

## Decision

The SYSTEM/background injection mechanism is technically available without rebuilding the stable identity prefix: append a second SYSTEM-formatted incremental suffix after `system_prompt_position`, keep that boundary unchanged, and let the accepted reset primitive remove the suffix on the next session switch. This is the prerequisite for the next runtime implementation candidate; no ordinary warm-session fast path should be enabled before these invariants are encoded fail-closed.