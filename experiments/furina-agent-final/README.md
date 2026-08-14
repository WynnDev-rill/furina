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

The updater uses staged validation, so an invalid new Core is rejected before it can replace the currently installed Core. Model and memory data remain separate from the active Core. Bridge updates are only offered when the installed Bridge version is actually older than the version required by the manifest.

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

## Android control — Core RC25 / Bridge RC15

The Android agent separates **understanding the complete goal**, **tracking the current UI state**, and **executing low-level Android primitives**. A multi-step request must retain every requested stage instead of being considered complete because its first action succeeded.

RC25 makes those stages state-aware. Semantic tasks can distinguish `search`, `select`, `type`, and `send`, and text input carries a field role such as `search`, `message`, or generic `input`. This prevents later message text from being written back into a still-focused search field. If the semantic parser omits an obvious transition in a send workflow, the Core repairs the generic state graph—for example a search followed by message composition requires selecting the searched result before typing into the destination UI. This repair is based on the action relationship rather than a hard-coded WhatsApp path.

A typical messaging workflow is therefore modeled as:

```text
open_app → search(contact) → select(contact) → type(message) → send
```

Bridge RC15 scores editable fields from Accessibility metadata such as hints, content descriptions and resource IDs. Search fields and message/composer fields are treated as different roles. After a `select` step the Bridge requires a material UI transition before it continues, so it will not blindly type the next payload while still on the previous search screen. Apps that expose only one poorly-labelled editable field retain a conservative single-field fallback for compatibility.

External effects remain separated from ordinary navigation. A final `send` requires a specific confirmation containing the intended target/message context. After confirmation, it is appended to the already-prepared local sequence. If the final send control cannot be verified, Furina does not automatically retry it because a retry could duplicate an external action.

RC25 also strengthens task termination when the user returns to Termux. The Core combines the foreground package, the Bridge's persistent Termux-session state, return timestamps and a bounded direct Bridge snapshot fallback while a task is active. Bridge RC15 refreshes foreground/session state from window-state, windows-changed and relevant content-change events and keeps a stable-package fallback when Android temporarily exposes no active root. This is intended to handle devices/ROMs where a Termux return does not always produce the same Accessibility event pattern.

The deterministic direct path remains only an atomic latency optimization. An exact command such as opening one known app may execute immediately, while longer requests keep their ordered semantic state graph.

The selected backend is configured under **Settings → Kontrol perangkat**. Runtime diagnostics stay in Settings and are not printed into the conversation.

- **Normal** — default. Uses native Android intents where possible and Accessibility for UI actions. No Shizuku or root is required.
- **Shizuku** — optional. Furina Bridge requests Shizuku permission only when the user selects this mode. A persistent Shizuku Binder UserService is reused for supported privileged primitives instead of starting a new remote process for every action.
- **Root** — optional. Furina Bridge requests root only when this mode is selected and keeps an authorized root shell warm for supported fixed primitives.

Shizuku/root do not expose an arbitrary remote shell through the Furina Core API. The privileged interface is restricted to explicit device-control primitives, with Accessibility/native control retained as fallback.

Natural Android tasks can be given to the Agent, for example:

```text
buka YouTube dan cari MrBeast
bka gogle trus cri makanan sehat
buka WhatsApp, cari Budi, tulis "aku pulang jam 8", lalu kirim
```

Multi-step tasks that require the screen ask for screen permission. External side effects such as Send/Post/Share remain on the guarded agent path and require a specific confirmation before execution. Dynamic tasks can fall back to the universal planner from the current real screen instead of replaying completed steps.

RC25 requires Bridge RC15 for role-aware fields, transition guards and the broader foreground tracker. Once RC15 is installed, later Core-only updates do not download the Bridge again unless the manifest's Bridge version increases.

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

AUTO routing prefers a configured online provider and falls back to local inference when online providers are unavailable within the bounded failover budget.

## Safety

Normal navigation/text input can be approved per task. External side effects such as Send/Post/Share remain on the guarded agent path and require specific confirmation. Payment, transfer, uninstall, destructive deletion, factory reset and security changes remain blocked from autonomous execution. The same guard is retained in the fallback TUI if the primary Textual chat surface cannot start. Normal mode remains the default; Shizuku/root are opt-in and initiated from Settings rather than from conversation text.
