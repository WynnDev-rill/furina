# FurinaHub — Furina Agent Experimental

FurinaHub is the Android front-end for the experimental Furina Agent. The AI runtime, local models, Psyche, memory, and Android agent still live in Termux; FurinaHub provides a chat-first Android interface over the local loopback Core.

The experiment remains isolated from the main Furina APK. The layout direction is inspired by the clean, chat-first Android ergonomics of RikkaHub; FurinaHub keeps its own implementation and Furina Agent architecture.

## Install baru

From a fresh Termux:

```bash
pkg update -y && pkg install -y curl && curl -fsSL https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
```

The installer:

1. checks and reconciles only the dependencies required by the current dependency revision;
2. reconstructs and verifies Furina Core;
3. keeps the `furina` CLI and installs the `furina-hub` local GUI launcher;
4. enables the explicit Termux integration needed by the Android shell;
5. downloads the signed FurinaHub APK, verifies its release SHA-256, and opens the Android installer when possible.

The APK is also left at:

```text
~/FurinaHub.apk
```

Termux remains fully usable:

```bash
furina
```

and the local FurinaHub server can be started manually with:

```bash
furina-hub
```

## FurinaHub UI

Opening the APK goes directly to **Percakapan**. There is no dashboard or onboarding screen between the user and chat.

The navigation drawer contains:

- Percakapan
- Memori & Psyche
- Model & Provider
- Personalisasi
- Agent & Skill
- Update & Diagnostik
- Pengaturan Lanjutan

The Memori screen intentionally does **not** expose a relationship score/summary. Relationship context may still be used internally by Psyche when relevant to conversation.

## Personalization

Personalization is an expression layer, not a replacement for Psyche or persistent identity.

Base styles:

- Adaptif
- Ramah
- Langsung
- Profesional
- Playful
- Tsundere
- Cool / Dry
- Lembut
- Kustom

Each preset only supplies starting expression biases. The user can independently tune:

- Kehangatan
- Ketegasan / Langsung
- Playfulness
- Sinis / Sarkas
- Kemesraan
- Ekspresivitas
- Formalitas
- Panjang Jawaban
- Suka Menggoda
- Keterbukaan Emosi

There is also a free-form **Instruksi khusus** field.

PsycheState, memories, current emotion, and context are still allowed to change how the companion behaves naturally. Personalization never grants Android permissions or bypasses the policy layer.

## Model & provider

The APK mirrors the important Core controls that were previously Termux-only:

- local GGUF selection;
- LOCAL / AUTO / ONLINE routing;
- configured OpenRouter, Groq, NVIDIA, and Gemini providers;
- local persona/display name and user nickname;
- generation limits and performance settings under Advanced.

API keys remain stored locally in the existing protected provider store.

## Agent modes

Device-control mode can be selected from FurinaHub:

- **Biasa** — Accessibility / Android intents.
- **Shizuku** — fixed privileged primitives when explicitly enabled.
- **Root** — fixed root primitives when explicitly enabled.

There is no automatic escalation from Normal to Shizuku/root.

### Skill Agent

Skills are capability switches that can only reduce what the Agent is allowed to use:

- Navigasi Android
- Baca Konteks Layar
- Input Teks
- Workflow Semantik
- Vision Fallback
- Kontrol Privileged

Disabling a skill blocks its associated action before execution. Enabling a skill does not bypass RC32 Goal Lock, Action Firewall, external-action confirmation, privacy filtering, or destructive-action blocks.

## Update

FurinaHub has two update paths from the app:

**APK FurinaHub**
- checks release metadata;
- verifies package name, version, SHA-256, and signing certificate;
- opens the Android package installer only after verification.

**Core & dependency**
- invokes the fixed `furina update` command through Termux;
- uses the same staged Core validation as CLI updates;
- dependencies are reconciled against a versioned `dependency_revision`, not blindly upgraded.

Core RC35 targets FurinaHub Android RC19. The Android package ID and signing identity remain compatible with Bridge RC18 so the APK is an in-place upgrade rather than a separate application.

## Local architecture

```text
FurinaHub APK / WebView
        │
        │ http://127.0.0.1:8787 + per-session token
        ▼
Furina Core in Termux
  ├─ conversation
  ├─ Psyche
  ├─ memory
  ├─ model router
  └─ Android Agent
        │
        │ authenticated local Bridge
        ▼
Android / Accessibility / Shizuku / root fixed primitives
```

The FurinaHub HTTP UI binds only to `127.0.0.1`. A new per-session access token is passed by the Android shell when it starts the server; API endpoints require that token. WebView navigation is limited to the FurinaHub loopback origin and file/content access is disabled.

## Current versions

- Core: `1.0.0-rc35`
- FurinaHub Android: `1.0.0-rc19`
- Dependency revision: `2026.08.14-r1`

RC34 chat-first intent separation and RC32 execution policy remain active underneath RC35.
