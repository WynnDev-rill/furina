# Furina Agent by Wynn — Final Candidate

Furina Agent runs its AI core in Termux and uses a small Android Bridge APK for device control. It is isolated from the main Furina APK project.

## First install

Install/open Furina Bridge and enable Persistent Bridge + Accessibility. For a fresh Termux, run this single line:

```bash
pkg update -y && pkg install -y curl && curl -fsSL https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
```

That one command bootstraps `curl`, then the Furina installer automatically reconciles all required Termux packages and Python dependencies, installs the Core, validates it before activation, and keeps the model/data directories separate. No ZIP needs to be copied to internal storage and no pairing code is required.

If Furina is already installed, normal maintenance remains:

```bash
furina update
```

The updater uses the same dependency bootstrap and staged validation, so a missing package is repaired automatically and an invalid new Core is rejected before it can replace the currently installed Core.

After setup, daily use is simply:

```bash
furina
```

Other maintenance commands:

```bash
furina doctor
furina repair
furina optimize
```

`furina optimize` benchmarks the actual local GGUF on the phone and selects a better CPU thread count. It is not run every startup.

## Android control — RC13

RC13 uses a **direct-first** control path. Clear low-risk commands are executed by the Bridge before Furina spends time on an LLM planner. The full agent remains the fallback for ambiguous, multi-step, external or sensitive tasks.

Examples that can use the direct path include opening an installed app, Back/Home/Recents, simple scrolling, an unambiguous tap target, and text input into a clear editable field. Commands such as Send/Post/Share/Delete/Pay/Transfer/Login remain on the guarded full-agent path.

The selected backend is configured under **Settings → Kontrol perangkat**. Runtime diagnostics stay in Settings and are not printed into the conversation.

- **Normal** — default. Uses native Android intents where possible and Accessibility for UI actions. No Shizuku or root is required.
- **Shizuku** — optional. Furina Bridge requests Shizuku permission only when the user selects this mode. A persistent Shizuku Binder UserService is reused for supported privileged primitives instead of starting a new remote process for every action.
- **Root** — optional. Furina Bridge requests root only when this mode is selected and keeps an authorized root shell warm for supported fixed primitives.

Shizuku/root do not expose an arbitrary remote shell through the Furina Core API. The privileged interface is restricted to explicit device-control primitives, with Accessibility/native control retained as fallback.

Natural Android tasks can still be given to the Agent, for example:

```text
buka YouTube dan cari MrBeast
buka WhatsApp, cari Budi, tulis "aku pulang jam 8", lalu kirim
```

Complex tasks may still require planning, but straightforward actions should begin without waiting for a planner round-trip. External side effects remain guarded.

## Reminders

Reminder scheduling is owned by **Furina Bridge on Android**, not by a Termux background thread. Once a reminder has been scheduled successfully, closing Furina or Termux does not cancel it.

Natural relative forms such as these are supported:

```text
ingatkan aku minum dalam 5 menit
ingatkan aku minum 5 menit lagi
```

The Bridge persists pending reminders, schedules them with Android `AlarmManager`, and restores future alarms after reboot. On Android versions with Exact Alarm access, exact alarms are used; otherwise Android's allow-while-idle fallback is used and delivery may be less exact. Notification permission must remain enabled for Furina Bridge.

## Online provider diagnostics

Use the provider test before blaming the API key itself:

```bash
furina provider-test groq
furina provider-test nvidia
```

The online routing hotfix keeps model metadata type-stable so providers that return an empty `pricing` object cannot crash model ranking.

## Safety

Normal navigation/text input can be approved per task. External side effects such as Send/Post/Share remain on the guarded agent path. Payment, transfer, uninstall, destructive deletion, factory reset and security changes remain blocked from autonomous execution. Normal mode remains the default; Shizuku/root are opt-in and initiated from Settings rather than from conversation text.
