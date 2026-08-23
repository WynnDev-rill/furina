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

Provider/API routing stays automatic among configured online providers and models. An online failure never silently changes the chat to a local model.

**Local**

Exactly one downloaded local model is selected for chat. Furina does not start or pre-warm the model merely because `furina` is opened; the selected model is loaded lazily when the first local-chat message actually needs it.

The supported local catalog contains exactly two chat models:

| Model | Quantization | Download size | State before download |
| --- | --- | ---: | --- |
| wifuGPT 1.7B | Q4_K_M | ~1.03 GiB | `Unduh` |
| Qwen3 1.7B Heretic | Q5_K_M | ~1.17 GiB | `Unduh` |

After a verified download the action becomes `Pilih`; the selected model shows `Aktif`. A partially downloaded or invalid file cannot be selected. Downloads support resume and are checked against the pinned byte size, GGUF header and SHA-256 before activation.

The previous Furina-owned Qwen3.5 4B Deckard/legacy catalog files are retired during migration. Furina does not delete unrelated GGUF files that the user placed in the models directory manually.

## Product model

There is no separate friendship mode and no primary **Kita** menu. A fresh setup begins with only Furina's name, the user's chosen name, and the fact that they are partners. Other memory develops from conversation or explicit saved state.

Relationship state, memory, Psyche, shared moments and personalization continue to work behind the simplified surfaces; hiding a maintenance screen does not disable the companion systems.

## FurinaHub

FurinaHub uses the same Core and model catalog in Termux through the local bridge. The Android model screen mirrors Furina Lite:

- Online or one selected local model;
- wifuGPT 1.7B Q4_K_M and Qwen3 1.7B Heretic Q5_K_M only;
- `Unduh`, `Pilih`, and `Aktif` states;
- resumable, size/SHA-verified local downloads;
- automatic provider/API failover only while Online is selected.

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
                                   ├── Online provider router
                                   ├── one selected local GGUF (optional)
                                   ├── Android Agent
                                   └── optional OpenConnector adapter

Update: furina-update/1 → verified channel → staged snapshot → atomic swap
```

## Current versions

- Core: `1.0.1`
- FurinaHub Android: `1.0.1` (`versionCode 10059`)
- Dependency revision: `2026.08.23-r41`
- Bundle: `furina-2026.08.23-private-1.0.1`
- Update client: `1.2.0`
- Runtime contract: `furina-runtime/v7-local-model-on-demand`

For installation and recovery details, see [`INSTALL.md`](./INSTALL.md).
