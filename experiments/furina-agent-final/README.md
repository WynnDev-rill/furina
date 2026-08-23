# Furina — private final build

Furina is one local-first AI companion with two surfaces that share the same Core and data:

- **Furina Lite** in Termux: fast chat, memory, provider/model, settings, system controls, backup, update and recovery.
- **FurinaHub** on Android: the full chat and multimedia experience, native image tools, model/provider controls, plugin UI, personalization and Android-agent controls.

This branch is treated as the final private build. It is optimized for one owner and one device workflow, not public distribution or store requirements.

## Install

Use a current Termux installation:

```bash
pkg update -y && pkg install -y curl
curl -fsSL https://github.com/WynnDev-rill/furina/releases/download/furina-update-stable/furina-install.sh | bash
```

After installation:

```bash
furina
```

The installer and `furina update` use the same green Furina terminal language as the main Lite UI. Interactive Termux sessions show a compact live progress bar; FurinaHub receives machine-readable progress through the same updater.

## Product model

There is no separate friendship mode and no primary **Kita** menu. A fresh setup begins with only three relationship facts: Furina's name, the user's chosen name, and that they are partners. Everything else must be learned from actual conversation or explicitly saved state.

The primary surfaces are intentionally limited:

- Chat
- Memory / Psyche
- Provider & Model
- Personalization
- Agent & Skill
- Settings / System
- Backup
- Update & Recovery

Relationship preferences and shared moments remain internal companion state instead of a second product mode.

## FurinaHub

FurinaHub uses the Core running in Termux through a narrow loopback bridge. The Android shell keeps file/content access restricted and does not rely on browser-style navigation. Zoom controls are disabled.

The full Android surface includes:

- conversation history and message actions;
- image attachment, preview, crop and canvas markup before sending;
- local model download/remove and provider configuration/testing;
- memory and personalization backed by the same data used by Furina Lite;
- Plugin/OpenConnector controls;
- Normal, Shizuku and Root device-control modes with explicit readiness and policy boundaries;
- APK/Core update status using the same update state as Termux.

The technical connection indicator is simplified to user-facing states such as **Siap**, **Terhubung**, **Menghubungkan**, or **Offline** instead of exposing implementation wording such as “Core aktif”.

## Updates

Normal update:

```bash
furina update
```

The update path is one self-updating stdlib Python client and one signed channel. It verifies hashes and sizes, stages a complete Core + bridge snapshot, validates it, then swaps Core/bridge atomically without touching user data.

A current installation takes the fast path: after checking the small channel metadata it skips package/npm/Plugin reconciliation unless a real Core update or repair is required. FurinaHub APK confirmation is tracked separately so an interrupted Android install does not falsely mark the APK as installed.

Recovery:

```bash
furina recover
```

Repair:

```bash
furina repair
```

The bootstrap keeps old recovery markers only as inert compatibility text for already-installed clients. Historical patch chains are build-time reconstruction only and are not the device update path.

## Data and performance

User data lives under:

```text
~/.furina-agent/
```

Core/bridge updates replace application code, not memories, conversations, provider secrets, models or user state.

Background memory work is handled by one ordered microbatch worker. The final build bounds its queue at 64 pending turns: normal chat remains non-blocking, while an extreme backlog applies backpressure instead of growing memory without limit.

OpenConnector remains optional at product level and loopback-scoped. Its runtime is reconciled only when a Core install/repair requires dependency validation; a no-op update does not pay that cost.

## Final architecture

```text
Furina Lite (Termux) ─┐
                      ├── ~/.furina-agent/ Core + shared data
FurinaHub (Android) ──┘            │
                                   ├── conversation / memory / Psyche
                                   ├── partner-first relationship state
                                   ├── model + provider router
                                   ├── Android Agent
                                   └── optional OpenConnector adapter

Update: furina-update/1 → verified channel → staged snapshot → atomic swap
```

## Final versions

- Core: `1.0.0`
- FurinaHub Android: `1.0.0` (`versionCode 10058`)
- Dependency revision: `2026.08.23-r40`
- Bundle: `furina-2026.08.23-private-1.0.0`
- Update client: `1.1.0`
- Runtime contract: `furina-runtime/v6-private-final`

For installation and recovery details, see [`INSTALL.md`](./INSTALL.md).
