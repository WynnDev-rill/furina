# Furina — private final build

Furina is one local-first companion with two surfaces sharing the same Core and user data:

- **Furina Lite** in Termux: Chat, Provider & Model, Pengaturan, Exit.
- **FurinaHub** on Android: the full multimedia, model/provider, Plugin, personalization, and Android-control surface.

This branch is optimized for a private owner/device workflow rather than public distribution.

## Install

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Fresh install does **not** download a GGUF model. It installs Furina and required runtime code, including `llama-cpp` so Local chat is ready when a model is later downloaded. Local models remain on-demand in **Provider & Model**.

## Provider & Model

There is no AUTO mode. Chat uses either:

- **Online** — configured providers/models fail over automatically before visible output starts; native streaming is used.
- **Local** — exactly one downloaded model is selected and used for chat, with no silent online fallback.

The local catalog remains exactly:

| Model | Quantization | Download size |
| --- | --- | ---: |
| wifuGPT 1.7B | Q4_K_M | ~1.03 GiB |
| Qwen3 1.7B Heretic | Q5_K_M | ~1.17 GiB |

States are **Unduh → Pilih → Aktif**. Downloads are resumable and must pass exact-size, GGUF-header, and SHA-256 verification before selection.

## Local Fast Path 1.0.3

1.0.3 fixes the multi-minute local first-token delay observed in 1.0.2 without changing either model or quantization.

- Repairs the exact stale `6144` context state from 1.0.2 to the phone-first `4096` context.
- Uses a compact local-only Furina persona while retaining identity, personality, partner relationship, memory behavior, sampling, and response budget. Online models keep the full prompt.
- Ordinary conversation such as `hi` bypasses the hidden LLM intent classifier. Only ambiguous device-like requests use the small classifier; explicit Android commands retain the deterministic fast path.
- Local history is adaptive and shorter; relevant belief/memory/episode retrieval is prompt-budgeted instead of disabling stored memory.
- Android-agent policy and dialogue examples are no longer carried into ordinary Local chat.
- The prompt prefix is kept stable so llama.cpp cache reuse can work effectively.
- Opening Local chat prewarms the selected model while the user types. A healthy model remains warm for a bounded idle window.
- Background memory consolidation/reflection keeps its full behavior but waits for about two minutes of local idle time. Foreground chat can cancel/defer it so memory work cannot monopolize the only local inference slot.
- `llama-cpp` is a required/self-healing runtime dependency. Missing runtime is repaired without downloading a model.
- Termux no longer requests an unprivileged positive llama.cpp process priority.
- Optimized llama-server startup automatically retries a minimal CPU-safe command if the optimized launch fails.
- Local and Online responses keep native streaming; the first visible chunk is immediate and later tiny chunks are coalesced briefly for smooth rendering.
- Existing cache-reuse, capability-gated Flash Attention, keep-warm, 4/5/6-thread tuning, and optional backend-specific acceleration remain available.

The established response-quality budget remains `max_tokens 2048` with up to four explicit continuations. Performance comes from reducing unnecessary prefill/work, not shortening Furina's answers.

## Product and memory

Fresh setup starts with Furina's name, the user's chosen name, and the fact that they are partners. There is no separate friendship mode or primary Kita menu.

Memory/Psyche remains active internally but is hidden as a maintenance surface. Relationship state, memories, episodes, shared moments, and personalization are preserved across Core/bridge updates under:

```text
~/.furina-agent/
```

Normal updates do not delete conversation, memory, provider secrets, local models, personalization, or shared moments.

## Update / recovery

```bash
furina update
furina recover
furina repair
```

The updater uses one verified `furina-update/1` channel/client, validates asset size/hash, stages a complete Core+bridge snapshot, then swaps Core/bridge atomically. User data remains outside that replacement boundary. A current install takes the no-op fast path.

## Uninstall Termux copy

```bash
hapus furina
```

This is destructive and requires confirmation. It removes Furina-owned Termux data/runtime/models/launchers but does not uninstall the Android FurinaHub APK or shared Termux packages.

## Current versions

- Core: `1.0.3`
- FurinaHub Android: `1.0.3` (`versionCode 10061`)
- Dependency revision: `2026.08.24-r43`
- Bundle: `furina-2026.08.24-private-1.0.3`
- Update client: `1.2.0`
- Runtime contract: `furina-runtime/v9-local-fast-path`

See [`INSTALL.md`](./INSTALL.md) for the operational install/update flow.
