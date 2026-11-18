# NVIDIA NIM Main Chat Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add NVIDIA NIM as an optional main-chat provider, preserving Furina's existing glass settings, context, and background integrations.

**Architecture:** Reuse the key settings card and add the same provider dropdown already used by background jobs. Separate main-chat NVIDIA keys, activation, and durable routing state from background jobs. Intersect authenticated `/v1/models` access with NVIDIA's live catalog Free Endpoint/chat metadata; no partner endpoint or paid-provider fallback. Keep the last successful model/key across messages; bounded attempts and persisted cooldowns handle failures.

**Tech stack:** Existing React/Radix/TanStack Start, Supabase service-only tables, AES-GCM key protection, native fetch/AbortSignal, node:test. No additional runtime dependencies.

**Constraints and decisions:**

- Retain existing Gemini/Lovable behavior unless NVIDIA is explicitly selected. Preserve the existing eligibility policy for optional main-chat keys.
- NVIDIA is strict: disabled, exhausted, or unknown free status produces a recoverable error instead of charging Lovable/Gemini automatically.
- Use only the fixed NVIDIA hosted inference origin and fresh verified free catalog metadata; never follow inference redirects or trust user-supplied endpoints.
- Current API metadata has no pricing field; use the same `nim_type_preview`/PREVIEW metadata NVIDIA uses for the Free Endpoint badge, then intersect with the authenticated model list. Fail closed when catalog verification is unavailable or expired.
- Free hosted access is for prototyping/evaluation per NVIDIA's current FAQ, not a promise of unlimited free production use. Show that limitation in settings and document the research date.
- Reuse the exact already-built system persona, memories, age context, history, quote and image payload across all attempts. Never display reasoning text.
- NVIDIA keys for main chat are stored independently from background keys. Only suffix/invalid status crosses into settings responses.
- Model/key rotation returns one normalized completion only. Do not stream partial attempts; honor Retry-After/cooldowns and stop on terminal input/auth/safety failures.

## Review focus

1. Catalog changes, paid-only listings, empty/malformed responses and withdrawn active models must fail closed or select another live free candidate.
2. Multi-key rate limits must not cause key storms or repeatedly retry an account-wide exhausted free tier.
3. Timeouts, thinking-only/empty replies and incompatible model inputs must not create duplicate bubbles or lose image/context.
4. Switching provider/account or removing a key must not reuse another account's credentials, stale state, or enable a different channel.
5. Existing Gemini fallback policy and default settings must remain unchanged for old rows/users.

## Tasks

- [x] **Discovery/evaluation:** Probe NVIDIA model/catalog APIs and compare MiniMax/Nemotron with isolated Furina fixtures; record latency, compatibility, and limitations without credentials.
- [x] **Catalog and routing core:** Add pure catalog parsing/ranking and bounded sticky model/key routing. Test free intersection, freshness, cooldowns, Retry-After, busy/missing/timeout/empty/terminal responses, images and single-response behavior before implementation.
- [x] **Persistence/server integration:** Add additive migration, main-chat key settings endpoints, encrypted storage and persisted active model/cooldowns; update types and usage provider constraint. Test isolated migration and owner-only access. Integrate NVIDIA using the same assembled chat messages.
- [x] **Settings UI:** Add Gemini/NVIDIA dropdown, reuse the current key card, independent activation/removal and model status. Verify mobile widths 320/412 and desktop 1024, glass styles, keyboard/focus and account-switch behavior.
- [x] **Verification/handoff:** Run full test suite, TypeScript, frozen install/build and affected-file lint. Perform independent code review, update AGENTS.md and docs, and create a PR with results and deployment/migration steps. Never commit the supplied test key.

## Verification ledger

- 111/111 node tests pass, including isolated PostgreSQL migration/permissions and original handler/provider transitions; TypeScript and production build pass.
- Chromium component tests pass at 320/412/1024, light/dark, including delayed poll responses after deletion/provider mutation; Impeccable detector reports no findings for the two components.
- Independent review findings fixed with regression tests: public model-list authentication false positive, moderation/refusal, HTTP 408/503 Retry-After/402 backoff, lazy discovery/fresh eligibility, inactive last key, unreadable key quarantine, image capability metadata, and stale UI polling.
- AVAILABLE=false was not treated as hosted endpoint withdrawal: NVIDIA's own client uses it for downloadable NIM. PREVIEW and authenticated inference are the hosted controls; live MiniMax completions succeeded with AVAILABLE=false.
- Live tests used only hidden-stdin credentials, synthetic dialogs and a public icon. Validation succeeded, fake key failed, fault-injected failover retained the successful model on the next message, and image inference succeeded.

- Release preparation: PR #238 created. Migration 20261118021140 applied atomically to the existing Furina Lovable database and recorded in migration history. Targeted metadata checks confirmed RLS, no anon/authenticated table/RPC access, service-role access, and zero stored main-chat keys. No production account fixture or supplied key was inserted.
