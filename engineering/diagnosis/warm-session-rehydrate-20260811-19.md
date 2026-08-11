# Warm session rehydrate boundary — static diagnosis

Timestamp: 2026-08-11T19:08:00+07:00
Scope: P0 local-companion latency / continuity
Evidence level: STATIC (device latency values below are previously recorded primary evidence; this record does not create new DEVICE evidence)

## Confirmed observations

1. The current target-device baseline recorded in issue #42 reports `warmPrepareMedianMs = 74600.5` and `firstTokenMedianMs = 78660` for official build 259.
2. `LocalLlamaProvider.prepare()` keeps mapped model weights warm, but when either `loadedSessionId` or `loadedIdentityFingerprint` changes it calls `engine.setSystemPrompt(context.coldStartPrompt)` before returning ready.
3. `AiContext.coldStartPrompt` contains both the stable identity prompt and private session rehydration (`summary` + recent USER continuity). Therefore a session switch currently couples stable identity prefill to mutable session continuity.
4. `InferenceEngineImpl.setSystemPrompt()` serializes onto the llama dispatcher, changes state to `ProcessingSystemPrompt`, and invokes native `processSystemPrompt()` for the whole supplied prompt.
5. Native `processSystemPrompt()` resets long-term and short-term chat state before processing the system prompt. There is currently no exposed lightweight API that preserves an already-prefilled stable system prefix while replacing only session-scoped continuity.
6. `LocalLlamaProvider.resetConversationStateKeepingModel()` is not a usable shortcut today: it calls `engine.setSystemPrompt("")`, while `InferenceEngineImpl.setSystemPrompt()` explicitly rejects blank prompts with `require(prompt.isNotBlank())`. The function therefore falls into its failure path rather than providing a zero-prefill reset.
7. The already-confirmed C2 defect means session/background context must not be moved into the latest USER payload as a latency shortcut. That would reduce role separation and make the known semantics problem worse.

## Causal graph

`session/identity change -> full coldStartPrompt setSystemPrompt -> native chat/KV reset + stable identity re-prefill + session rehydrate prefill -> ~74.6 s warm prepare on recorded target-device baseline -> daily conversation/session switching becomes impractically slow`

## Repair decision

Do not optimize this by deleting continuity or concatenating session rehydration into the USER message.

The safest next implementation direction is to introduce an explicit native/runtime boundary that can preserve a validated stable identity/system prefix while resetting conversation state and applying session-scoped continuity with SYSTEM/background semantics. The API must fail closed when the system prefix is unavailable or identity changes, in which case the existing full `setSystemPrompt(coldStartPrompt)` path remains the rollback/fallback.

A narrower prerequisite repair may also replace the currently impossible blank-prompt reset with a real native reset primitive, but it must not be misrepresented as solving warm session rehydrate unless device evidence shows the stable system prefix is actually reused.

## Required verification for a future implementation

FAST/STATIC:
- exact session switch cannot inherit prior USER/ASSISTANT KV/chat history;
- identity change still forces full system re-prefill;
- private session continuity remains outside the latest USER message;
- cancellation/error fallback invalidates reusable session state;
- no secret/private conversation content is committed.

MEDIUM/CI:
- native overlay compiles and deterministic companion-quality checks pass on the exact checkpoint head.

DEVICE/BEHAVIORAL before claiming product improvement:
- compare warm prepare median and first-token median against build-259 baseline;
- verify conversation continuity after switching between at least two existing sessions;
- verify no cross-session leakage;
- rerun persona/latest-message behavioral scenarios because prompt-boundary changes can alter behavior.

## Prediction

A runtime primitive that reuses the stable system prefix should remove repeated stable-identity prefill from ordinary session switches. The magnitude is intentionally not claimed from STATIC evidence. Target for the eventual DEVICE experiment: at least 50% reduction in warm session-prepare median without regression in continuity, cross-session isolation, persona mean, or latest-message mean.

## Rollback boundary

This diagnosis artifact is control/evidence text only. A future runtime implementation must remain independently revertible to the current full `setSystemPrompt(coldStartPrompt)` behavior.
