# Furina — private final build

Furina is one local-first AI companion with two surfaces that share the same Core and user data:

- **Furina Lite** in Termux: a deliberately small terminal surface for chat, provider/model selection, settings, update and recovery.
- **FurinaHub** on Android: the full chat and multimedia experience, native image tools, provider/model controls, Plugin UI, personalization and Android-agent controls.

This branch is optimized for a private owner/device workflow rather than app-store distribution.

## Install

Use a current Termux installation:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
furina
```

Fresh installation does **not** download a local LLM. The installer only prepares Furina itself, required runtime/dependencies, and the FurinaHub APK. Local chat models are optional and are downloaded later from **Provider & Model**.

The installer and `furina update` use the same green **Furina By Wynn** terminal language as Furina Lite. Interactive Termux sessions show compact progress; FurinaHub receives machine-readable progress from the same updater.

## Furina Lite

The top-level menu is intentionally limited to four items:

```text
Chat
Provider & Model
Pengaturan
Exit
```

Memory/Psyche remains active internally but is not exposed as a maintenance screen. Less-frequent controls are grouped under **Pengaturan**:

- Identitas
- Kontrol perangkat
- Sistem
- Backup
- Update & Recovery

This keeps the terminal UI focused on what is used during normal conversation without removing the underlying capabilities.

## Provider & Model

There is no `AUTO` mode. Chat runs in exactly one of two routing modes:

**Online**

Provider/API routing stays automatic among configured online providers and models. Failover is allowed before visible output begins; after the first streamed text is shown, Furina keeps that response bound to the same provider so text is never duplicated or silently rewritten. Online chat uses native provider streaming and renders the first visible chunk immediately.

**Local**

Exactly one downloaded local model is selected for chat. Opening the generic `furina` TUI still does no model work. When Local is explicitly selected, Furina begins preparing the selected model in the background; if chat is opened before it is ready, the UI shows `Menyiapkan model lokal…` rather than appearing frozen. A healthy local runtime is kept warm for a bounded idle window so follow-up messages avoid repeated GGUF loading.

The supported local catalog contains exactly two chat models:

| Model | Quantization | Download size | State before download |
| --- | --- | ---: | --- |
| wifuGPT 1.7B | Q4_K_M | ~1.03 GiB | `Unduh` |
| Qwen3 1.7B Heretic | Q5_K_M | ~1.17 GiB | `Unduh` |

After a verified download the action becomes `Pilih`; the selected model shows `Aktif`. A partially downloaded or invalid file cannot be selected. Downloads support resume and are checked against the pinned byte size, GGUF header and SHA-256 before activation.

The previous Furina-owned Qwen3.5 4B Deckard/legacy catalog files are retired during migration. Furina does not delete unrelated GGUF files that the user placed in the models directory manually.

## Local Performance V2

The 1.0.2 runtime focuses on latency without changing either selected model or its quantization:

- phone-first `4096` context baseline while relevant memory continues to be selected by retrieval instead of disabling memory;
- llama.cpp prompt/KV cache reuse when the installed server exposes the capability;
- Flash Attention set to capability-gated `auto`;
- first streamed local token is not intentionally delayed; later tiny deltas are coalesced in a short render window to reduce Termux/WebView repaint overhead;
- local runtime remains warm for up to 600 seconds of idle time and can be stopped without deleting the selected model;
- optional device benchmark compares 4, 5 and 6 CPU threads on the exact downloaded GGUF;
- OpenCL/Vulkan are considered only when a real backend-specific llama-server build is present and benchmarked healthy; CPU always remains the fallback;
- stopping an active generation closes only its response stream, not the warm local model.

The 1.0.1 answer budget is deliberately preserved (`max_tokens 2048`, up to four explicit length continuations). Performance is gained from startup, prefill, caching and rendering rather than shortening answers.

## Product model

There is no separate friendship mode and no primary **Kita** menu. A fresh setup begins with only Furina's name, the user's chosen name, and the fact that they are partners. Other memory develops from conversation or explicit saved state.

Relationship state, memory, Psyche, shared moments and personalization continue to work behind the simplified surfaces; hiding a maintenance screen does not disable the companion systems.

## FurinaHub

FurinaHub uses the same Core and model catalog in Termux through the local bridge. The Android model screen mirrors Furina Lite:

- Online or one selected local model;
- wifuGPT 1.7B Q4_K_M and Qwen3 1.7B Heretic Q5_K_M only;
- `Unduh`, `Pilih`, and `Aktif` states;
- resumable, size/SHA-verified local downloads;
- contextual background preparation after a local model is selected;
- automatic provider/API failover only while Online is selected and before visible streamed text begins.

The direct Memory/Psyche navigation is hidden here as well, while memory remains part of the shared Core. FurinaHub still includes conversation history, image attachment/preview/crop/markup, Plugin/OpenConnector controls, personalization, device-control modes, and APK/Core update status.

## Update and recovery

Normal update:

```bash
furina update
```

Recovery:

```bash
furina recover
```

Repair:

```bash
furina repair
```

The update path uses one self-updating stdlib Python client and one signed channel. It verifies hashes and sizes, stages a complete Core + bridge snapshot, validates it, then swaps Core/bridge atomically without replacing user data. A current installation takes the fast path and avoids unnecessary package/npm/Plugin reconciliation.

Historical patch chains remain build-time reconstruction only. Old installer markers are retained solely as inert recovery compatibility for devices that already have older Furina versions.

## Uninstall from Termux

To remove Furina completely from Termux:

```bash
hapus furina
```

The command asks for destructive confirmation and then removes Furina-owned Termux data, memories, conversations, provider secrets, models, backups, runtime files and Furina launchers. It does **not** remove shared Termux packages and does **not** uninstall the Android FurinaHub APK.

## Data and performance

User data lives under:

```text
~/.furina-agent/
```

Normal Core/bridge updates preserve that data. Background memory work uses one ordered queue bounded at 64 pending turns, preventing unlimited backlog growth while preserving turn ordering.

## Architecture

```text
Furina Lite (Termux) ─┐
                      ├── ~/.furina-agent/ Core + shared data
FurinaHub (Android) ──┘            │
                                   ├── conversation / hidden memory / Psyche
                                   ├── partner-first relationship state
                                   ├── Online provider router + native stream
                                   ├── one selected local GGUF + warm runtime
                                   ├── Android Agent
                                   └── optional OpenConnector adapter

Update: furina-update/1 → verified channel → staged snapshot → atomic swap
```

## Current versions

- Core: `1.0.2`
- FurinaHub Android: `1.0.2` (`versionCode 10060`)
- Dependency revision: `2026.08.24-r42`
- Bundle: `furina-2026.08.24-private-1.0.2`
- Update client: `1.2.0`
- Runtime contract: `furina-runtime/v8-local-performance-v2`

For installation and recovery details, see [`INSTALL.md`](./INSTALL.md).
