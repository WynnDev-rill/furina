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

## Conversation sessions and memory — 1.0.6

Furina now separates short-term conversation history from long-term companion memory.

- Every new `furina` process gets a fresh Termux short-term chat thread on the first real message. A visually empty Chat therefore never silently continues the previous Termux conversation.
- `/back` only leaves the Chat screen; returning to Chat in the same running `furina` process keeps that thread so normal continuity is not lost accidentally.
- Closing the process and starting `furina` again creates a new short-term thread. Old conversations are preserved rather than deleted.
- Trusted personal memory, profile, relationship state, shared moments, provider/model selection, secrets, and local model files remain persistent across sessions.
- FurinaHub keeps its explicit persistent conversation selection. Creating a Termux session does not rewrite FurinaHub's globally active conversation.
- Local and Online engines use the same trusted long-term memory; only short-term message history is thread scoped.

This follows the standard agent-memory split: conversation/session history belongs to one thread, while durable user memory can be shared across threads.

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

## Local conversation quality

The Local path preserves the 1.0.3–1.0.5 performance and quality work:

- phone-first `4096` context repair for the old `6144` state;
- compact local-only Furina persona with shared trusted memory and relationship context;
- ordinary chat bypasses the hidden device-intent LLM classifier;
- prompt history is bounded, user-led, and malformed assistant output is quarantined;
- model-authored legacy personal facts are not promoted to trusted memory without user evidence;
- deterministic current day/date/time answers do not depend on a 1.7B model guessing;
- conservative llama.cpp repetition control reduces self-reinforcing phrase loops;
- Local and Online keep native streaming and FurinaHub updates the live answer in place;
- background memory work waits for Local idle time and yields to foreground conversation;
- the selected local model remains warm for a bounded idle window.

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

- Core: `1.0.6`
- FurinaHub Android: `1.0.6` (`versionCode 10064`)
- Dependency revision: `2026.08.24-r46`
- Bundle: `furina-2026.08.24-private-1.0.6`
- Update client: `1.2.0`
- Runtime contract: `furina-runtime/v12-session-isolation`

See [`INSTALL.md`](./INSTALL.md) for the operational install/update flow.
