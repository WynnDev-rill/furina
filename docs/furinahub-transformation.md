# FurinaHub 5 — architecture and verification record

Baseline: signed APK 4.1.365, commit d756f467e063e7bcb0c8dc5f28af737c5329de52.
This transformation builds on the earlier source adaptations documented in
furinahub-integration.md. It does not bundle donor applications.

## Product decisions

- Replace the four-tab dashboard with a conversation workspace, searchable history drawer,
  and dedicated model, appearance, memory, persona, data and Termux pages.
- Own the Furina blue palette with light/dark/system themes. Preserve private photo/video
  wallpaper imports and existing media verification rather than introducing another player.
- Show readiness based on validated provider configuration or a locally available model.
  A new install must not advertise that the companion is ready before a model is configured.
- Keep the verified GGUF/llama.cpp runtime. Gallery's LiteRT-LM formats are incompatible
  with the user's existing model; a second runtime would add size and a parallel lifecycle.
- Add user-configured OpenAI-compatible endpoints to the existing provider adapter.
  A Termux-hosted server can now use Android's conversation, persona, memory and context
  through this endpoint, without a second chat database.
- Keep the existing authenticated Furina Core bridge for accessing Furina Lite's own archive
  and Training Room. Full bidirectional replication of that archive remains unsupported.

## Donor audit

| Repository and pinned revision | Evaluated | Adoption |
| --- | --- | --- |
| Nocticur/lianyu-app 688b0d7ce3b27ce52ebac40c6429d22fd0f5ab08 | MemoryIndex/Tokenizer, ChatContextResolver, MessagePipeline | Retain previously adapted retrieval index. Use explicit request ownership and durable completion. Do not import fixed Chinese persona, chat relay, or unrelated validation/encryption pipelines. |
| adityavardhansharma/EchoFlow 549d4e27d72e45506b49b9ff7f1b1bf13a5fb655 | ProviderHttpSupport, ChatRepository, model UI | Extend the previously adapted shared transport to custom endpoints; preserve Furina's context and secrets. Keep history scoped to its owner. |
| google-ai-edge/gallery 33721326a9ff1682f66110430cebcc765c92d3fe | LlmChatModelHelper, ModelImportDialog, ModelDownloadStatus | Reference explicit download/preparation/release states and byte progress; implement them around the existing verified GGUF runtime. Do not copy Gallery's partially written model import or incompatible runtime. No Google source or branded assets are bundled. |
| nextlevelbuilder/ui-ux-pro-max-skill f3ac195224eac1eb0dfe1a3059c2a6add78ffbe3 | Native Compose guidance, accessibility and performance rules | Apply native controls, 48dp targets, scalable text, concise copy, dedicated routes. Its generated marketing-page patterns were unsuitable for chat and rejected. |

## Durable turns and migration

SQLite schema 6 adds a pending_turns journal without rewriting history, memory or persona.
Provider output is checkpointed at the first chunk and at most every 400 ms thereafter.
Completion commits the user/assistant pair and removes the journal in one transaction.
Stop/errors preserve a visible partial answer. At process restart, the journal is reconciled
before another generation can begin. A request with no output becomes a draft; a newer draft
is preserved separately. Recovery never automatically repeats a network request.
The last fraction of a second after a checkpoint can be lost on abrupt process death.

Backup validation accepts versions 1 through 6. Existing encrypted backup format, package ID
and signing identity are retained. API credentials are not added to portable backups.
Tests exercise upgrade from schema 4 and 5, idempotent recovery, interrupted output,
preservation of a newer composer draft, history branching and backup validation.

## Endpoint policy

External endpoints require HTTPS; HTTP is allowed only for 127.0.0.1 or localhost.
URLs with embedded credentials, query strings or fragments are rejected. A change of address
removes the previous endpoint's stored key. Validation binds address, model and key fingerprint.
Custom endpoints use only the explicitly configured model and never enter free-model fallback.
Connection testing sends a short real request, disclosed beside the form.

## Device QA

scripts/qa/android_blackbox.py installs actual signed APKs with adb install -r on Android 35,
first baseline and then candidate, collecting screenshots, UIAutomator hierarchy, logcat,
startup, meminfo and gfxinfo evidence. It exercises keyboard/draft restart, navigation,
large fonts, dark mode, landscape and dedicated settings pages.

The deterministic localhost HTTP/SSE fixture is QA infrastructure, not bundled app code.
It is designed to exercise real UI -> provider transport -> memory/context -> SQLite -> UI,
including Stop, process death and rate-limit recovery without external credentials or fees.
Passing fixture scenarios does not establish real LLM response quality or provider quota.

Emulator timing and software-rendered frame statistics cannot establish performance on a
physical Poco F6. Real GGUF inference, GPU/thermal behavior, authenticated external providers
and an installed Furina Lite/Termux deployment require separate evidence.
