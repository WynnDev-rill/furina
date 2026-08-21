# FurinaHub — Furina Agent Experimental

Furina is a relationship-first AI companion. **Furina Lite** in Termux remains a complete, lightweight chat client; **FurinaHub Full** adds the Android experience, multimedia, native controls, and richer relationship settings. Both surfaces use the same local Core, memory, relationship state, and shared moments.

The experiment remains isolated from the main Furina APK. The layout direction is inspired by clean, chat-first Android ergonomics similar to RikkaHub, while FurinaHub keeps its own implementation and Furina Agent architecture.

## Install baru

From a fresh Termux:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

The installer:

1. checks only dependencies required by the current dependency revision;
2. downloads and verifies one complete Core + bridge snapshot;
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

The local Core UI server can still be started manually with:

```bash
furina-hub
```

## Android RC21: unified FurinaHub shell

FurinaHub Android RC21 keeps the offline-first startup from RC20 and adds a shared Core state so settings changed in Termux are reflected when FurinaHub opens or resumes.

Opening the APK goes directly to **Percakapan**. If Core has not been connected yet, chat shows a compact offline state and the rest of the application remains navigable.

To connect:

1. open **Pengaturan**;
2. tap **Hubungkan ke Termux**;
3. FurinaHub requests `com.termux.permission.RUN_COMMAND` only at that moment;
4. after permission is granted, FurinaHub starts `furina-hub` with a fresh session token and verifies the loopback health endpoint;
5. Core-backed screens become active.

FurinaHub remembers the session token. On later launches it only probes an existing Core; it does not automatically execute a Termux command during APK startup.

If Termux integration itself is not prepared, the user can open Termux from the same settings card and run the verified FurinaHub installer once.

## FurinaHub UI

The navigation drawer contains:

- Percakapan
- Kita
- Memori & Psyche
- Model & Provider
- Personalisasi
- Agent & Skill
- Pengaturan

RC21 fills the main product gaps in those screens:

- the chat header no longer shows the Core status chip while a conversation is open;
- long-pressing a message exposes copy, edit/resend, regenerate, and branch deletion actions;
- the `+` button accepts bounded UTF-8 text attachments through Android's document picker;
- important memories can be added or removed from the same Core database used by Termux;
- provider keys can be configured and tested from the APK;
- Normal, Shizuku, and Root now show requested vs effective mode and require an explicit readiness probe;
- personalization migrates from the legacy JSON file into shared Core state and re-syncs with CLI config;
- OpenConnector can be configured on loopback with a local runtime token and read-first action policy.

The **Pengaturan** page now centralizes:

- connection to Termux Core;
- light/dark/system theme;
- FurinaHub APK update;
- Core/dependency update;
- advanced local-model settings when Core is connected.

The Memori screen intentionally does **not** expose a relationship score. The **Kita** screen identifies the relationship as **Pasangan** and exposes only useful controls: conversation pace, affection style, initiative, rituals, a shared note, and explicitly saved moments.

## Relationship Core v3

Core RC67 makes the initial relationship unambiguous: Furina and the user start as partners, not friends choosing a later mode. A fresh memory contains only Furina's name, the user's chosen name, and the partner relationship; upgrades preserve every existing user memory.

The updater now installs one verified full Core + bridge snapshot from any prior or incomplete version. It no longer walks a fragile chain of historical foundation patches.

Core RC66 changed the product center from tasks to long-term casual and romantic companionship:

- casual conversation is the default intent; work/task behavior only activates when explicitly requested;
- Romantic mode requires an explicit 18+ confirmation and never implies automatic sexual escalation;
- affection, banter, vulnerability, technical discussion, and high-risk situations receive different bounded dialogue guidance without a second model call;
- long-pressing a message can save it as a shared moment or propose it for reviewed memory;
- the existing Focus data remains intact for compatibility, but Focus is no longer a primary navigation item;
- no streak, guilt, forced jealousy, exclusivity demand, or punishment for absence is used to drive engagement.

The Android shell follows the repository-scoped **UI UX Pro Max v2.15.0** design system: minimum 44px interaction targets, semantic status feedback, restrained motion, responsive text, reduced-motion support, sparse surfaces, and progressive disclosure of technical controls. The persisted project rules are in `design-system/furinahub/MASTER.md`.

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
- configured online providers;
- companion display name and user nickname;
- generation limits and performance settings under Settings.

Provider secrets remain stored locally in the existing protected provider store.

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
- works even when Core is offline;
- checks release metadata;
- verifies package name, version, SHA-256, and signing certificate;
- opens the Android package installer only after verification.

**Core & dependency**
- becomes available after Termux Core is connected;
- invokes the fixed `furina update` command through Termux;
- uses the same staged Core validation as CLI updates;
- dependencies are reconciled against a versioned `dependency_revision`, not blindly upgraded.

If the normal updater cannot start, use:

```bash
furina recover
```

For an older installation that does not have that command yet, stream the installer directly instead of writing to Android's invalid global `/tmp` path:

```bash
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

Core RC67 targets FurinaHub Android RC55. The Android package ID and signing identity remain unchanged, so RC55 is an in-place upgrade rather than a separate application.

## Local architecture

```text
FurinaHub APK
  ├─ bundled offline UI shell
  ├─ native permission/update connector
  └─ native localhost API proxy
             │
             │ 127.0.0.1:8787 + per-session token
             ▼
Furina Core in Termux
  ├─ conversation
  ├─ Relationship Core v3
  ├─ shared moments
  ├─ Psyche
  ├─ memory
  ├─ model router
  ├─ Android Agent
  └─ OpenConnector adapter (optional, loopback only)
             │
             ▼
Android / Accessibility / Shizuku / root fixed primitives
```

The WebView does not directly navigate to localhost. The bundled shell calls a narrow native API proxy, which adds the session token to requests sent to `127.0.0.1:8787`. File/content access remains disabled in WebView; RC21 text attachments are read by a size-bounded native document picker. OpenConnector credentials remain inside its runtime, while FurinaHub stores only an optional runtime token in a mode-0600 Termux file.

## Current versions

- Core: `1.0.0-rc67`
- FurinaHub Android: `1.0.0-rc55`
- Dependency revision: `2026.08.22-r37`

RC65 shared workspace, RC53 persistent companion state, RC34 chat-first intent separation, and RC32 execution policy remain active underneath Relationship Core v3.
