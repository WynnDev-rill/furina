# FurinaHub — Furina Agent Experiment

FurinaHub is the Android-facing UI for the Furina Agent experiment. The AI Core still runs in Termux, while the APK provides a chat-first interface, Android Bridge services, device permissions, app update flow, and settings.

The experiment remains isolated from the main Furina APK project.

## Install baru

Open Termux and run:

```bash
pkg update -y && pkg install -y curl && curl -fsSL https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
```

The installer:

1. installs/reconciles the required Termux dependencies;
2. reconstructs and verifies Furina Core;
3. preserves model, memory, Psyche, and provider data;
4. installs the `furina` CLI and the `furinahub` local UI launcher;
5. enables the Termux RUN_COMMAND integration needed for one-tap APK startup;
6. downloads the signed FurinaHub APK release and opens Android's installer when available.

After installation, both entry points remain valid:

```bash
furina
```

and, for the local web UI without the APK:

```bash
furinahub serve
```

## FurinaHub RC19 + Core RC35

Opening the FurinaHub APK goes directly to Chat. There is no onboarding dashboard.

The APK is a restricted WebView shell around a Core-owned loopback UI at `127.0.0.1:8787`. FurinaHub starts that UI through Termux's explicit RUN_COMMAND integration using a fixed `furinahub serve` command. The page receives a per-install random token from the native shell; mutation API endpoints require that token.

FurinaHub keeps Android-native responsibilities in the APK:

- Persistent Bridge foreground service
- Accessibility service
- Shizuku/root-backed fixed primitives
- Termux start integration
- signed APK update check/install flow
- Android permission surfaces

The Termux Core continues to own:

- conversation and model routing
- local/online models
- Psyche Engine and memory
- chat-vs-Agent intent boundary
- Android Agent planning
- RC32 Goal Lock and Action Firewall
- personalization state
- Agent Skill restrictions
- Core/dependency updates

## UI sections

FurinaHub uses a chat-first Material-style layout inspired by modern Android LLM clients without copying another project's source or branding.

- **Chat** — default landing page. Device tasks remain inside the same conversation.
- **Memori** — stored memories, learned preferences, and open goals. No relationship-summary score is shown.
- **Model & Provider** — local GGUF choice, Local/AUTO/Online routing, and provider API keys.
- **Personalisasi** — base style, companion archetype presets, characteristics, and custom instructions.
- **Agent & Skills** — Normal/Shizuku/Root mode and user-toggleable Agent capabilities.
- **Pengaturan & Update** — assistant/user names, FurinaHub APK update, Core update, dependency reconciliation, and diagnostics.

Settings written from FurinaHub use the same Core config/data files as the Termux CLI, so switching between APK and `furina` does not create two separate identities.

## Personalization

RC35 separates conversational personalization from device authority.

Base styles include Adaptive, Friendly, Efficient, Professional, Playful, Calm, and Cynical. Optional character presets include Berkembang Alami, Tsundere, Deredere, Kuudere, Suka Menggoda, Elegan, Playful/Chaotic, and Custom.

Characteristics are independently adjustable:

- warmth
- intimacy
- expressiveness
- playfulness
- sarcasm
- directness
- formality
- verbosity
- emotional sensitivity

Presets are soft presentation biases rather than hard personality scripts. PsycheState and experience can still change expression over time. Custom instructions can affect conversation style but cannot grant device permission, disable confirmations, or change the Action Firewall.

## Agent Skills

Agent Skills are opt-in restrictions over capabilities the Agent already has; they are not downloadable executable code in RC35.

Available toggles include:

- app control
- UI navigation
- screen inspection
- text input
- messaging/external workflows
- privileged control
- vision fallback

Turning a skill off can only remove capability. It cannot add Android permissions or bypass RC32 policy.

## Updates

### FurinaHub APK

The native updater downloads signed release metadata, verifies package name, version, SHA-256, and signing certificate, then opens Android's package installer. RC19 retains the same package ID and release signing identity as Bridge RC18, allowing an in-place rename/update.

### Core

FurinaHub can start the existing verified `furina update` flow. Core activation remains staged and atomic.

### Dependencies

The app can run the `furinahub-deps` helper, which reconciles only the dependencies FurinaHub currently requires instead of performing an uncontrolled full-device update.

## Current safety boundaries

RC34's chat-first intent guard remains active: mentioning an app or discussing an action is not authority to run the Agent.

RC32 remains the action boundary after routing:

- Goal Lock freezes trusted task scope.
- Action Firewall checks proposed device actions.
- unknown capabilities fail closed.
- fresh-state resolution verifies targets before state-changing actions.
- external/uncertain actions receive fresh confirmation.
- sensitive UI data is redacted before planner use.
- personality, memory, or Agent Skills cannot create new privileges.

Current versions:

```text
Core       1.0.0-rc35
FurinaHub  1.0.0-rc19
```
