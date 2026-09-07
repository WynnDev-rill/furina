# FurinaHub unified integration — 2026-09-05

## Evidence and scope

The previous PR #211 implemented an original native shell inspired by both apps. It did not
integrate their provider or memory implementation. This release adds traceable source adaptations
and a single repository boundary around the existing Furina SQLite/AI engine and token-authenticated
Termux API. No upstream database, launcher, secret, branded asset or unrelated service is bundled.

| Source (audited commit) | Code evaluated | Decision |
| --- | --- | --- |
| Nocticur/lianyu-app `688b0d7ce3b27ce52ebac40c6429d22fd0f5ab08` | MemoryIndex, MemoryTokenizer, ChatContextResolver, ChatPromptBuilder, Room repositories | Adapt the inverted memory index/tokenizer to Indonesian and Furina SQLite. Keep bounded UI history. Retain Furina's adaptive prompt rather than LianYu's fixed Chinese response rules. |
| adityavardhansharma/EchoFlow `549d4e27d72e45506b49b9ff7f1b1bf13a5fb655` | ProviderHttpSupport, OpenRouterStreamTransport, ChatRepository, provider/settings UI | Adapt protocol/model/error helpers. Integrate model selection and explicit request ownership. Keep Furina's free-only fallback, encrypted API keys and reasoning exclusion. |
| WynnDev-rill/furina PR #211 `e0cddab6665a223fa1c4c1a676c28a86ec774519` | NativeHubController, MemoryStore, ContextEngine, UnifiedAiEngine, bridge, updater, wallpaper | Preserve DB/engine/download validation/signing. Replace conflicting native state orchestration; expose missing history/provider/data controls. |

## Boundaries

- UI -> controller -> repository -> Android SQLite or authenticated Termux API -> immutable state.
- A generation captures its source/session. Refresh or settings cannot move an in-flight turn.
- Termux owns its memories and history. Android stores its own sessions. Provider switches within
  Android share the same memory/context/identity. Explicit exports do not include API keys or tokens.
- Core persona reads update the durable Android identity; unsynced local edits are pushed first.
- The Core API currently exposes only a recent history/memory window. This is not an unrestricted
  full database sync. Do not claim parity or complete cross-runtime history replication.
- No silent repeat of an accepted Core message through a second model; failed turns require retry.

## Exclusions

LianYu's relay credentials/security stubs, WeChat/QQ/coffee services, boot keepalive, and second
local-model runtime are not relevant. EchoFlow's multi-agent tools, browser, paid generation,
research/image/video services are not part of this companion update. Furina's Training Room stays
in Termux, preserving its existing preference learner rather than creating a second training DB.

## Verification criteria

Test database migration, history actions, persona persistence, model parsing, memory ranking,
upstream license packaging, source changes during a turn, stop/retry, draft persistence, wallpaper
replacement and lifecycle, and signed APK identity. Device/real-provider tests must be reported
separately from JVM/Robolectric/build evidence. A signed build is not a Play Store certification.
