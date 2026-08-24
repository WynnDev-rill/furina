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

## Conversation sessions and memory

Furina separates short-term conversation history from long-term companion memory.

- Every new `furina` process gets a fresh Termux short-term chat thread on the first real message. A visually empty Chat therefore never silently continues the previous Termux conversation.
- `/back` only leaves the Chat screen; returning to Chat in the same running `furina` process keeps that thread so normal continuity is not lost accidentally.
- Closing the process and starting `furina` again creates a new short-term thread. Old conversations are preserved rather than deleted.
- Trusted personal memory, profile, relationship state, shared moments, provider/model selection, secrets, and local model files remain persistent across sessions.
- FurinaHub keeps its explicit persistent conversation selection. Creating a Termux session does not rewrite FurinaHub's globally active conversation.
- Local and Online engines use the same trusted long-term memory; only short-term message history is thread scoped.

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

## Local conversation quality — 1.0.7

1.0.7 adds a stricter conversation boundary around roleplay-tuned 1.7B models without changing either model or quantization.

- Fresh greetings/fillers such as `hai` or a new-thread `hmm` use a tiny Core social fast path instead of asking a local roleplay model to invent context.
- Generic Local turns no longer receive unrelated personal memory. Trusted shared memory is injected on demand for personal-recall questions such as preferences, goals, profile, or relationship facts.
- The Local system contract explicitly requires direct one-to-one chat: only Furina's utterance, no screenplay, no invented quoted user dialogue, no narration of what the user supposedly thinks or feels.
- A small prefix is held briefly before visible streaming. Script-mode signatures such as `Saya mohon izin...`, fake `User:`/`Assistant:` blocks, invented fresh-session continuity, or multiple imaginary quoted lines are blocked before display.
- If that guard triggers, Furina performs one compact low-temperature repair pass using only the latest user message and the correct thread state. Healthy answers keep normal streaming.
- Short casual Local turns use a lower temperature cap to reduce roleplay drift while deeper questions retain a wider generation budget.
- Session isolation, trusted shared long-term memory, deterministic time/date answers, anti-loop sampling, keep-warm, prompt cache, and FurinaHub in-place streaming remain intact.

The wifuGPT model card labels the model as a waifu/roleplay conversational fine-tune. 1.0.7 therefore treats roleplay formatting as a model-behavior risk at the inference boundary rather than as memory or conversation truth.

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

- Core: `1.0.7`
- FurinaHub Android: `1.0.7` (`versionCode 10065`)
- Dependency revision: `2026.08.24-r47`
- Bundle: `furina-2026.08.24-private-1.0.7`
- Update client: `1.2.0`
- Runtime contract: `furina-runtime/v13-conversation-quality-gate`

See [`INSTALL.md`](./INSTALL.md) for the operational install/update flow.
