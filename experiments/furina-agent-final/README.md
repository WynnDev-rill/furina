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

## Android control — Core RC24 / Bridge RC14

RC23 separates **understanding the user's goal** from **executing Android primitives**. The Core first preserves a device request as a semantic intent with ordered conceptual steps. This prevents a multi-step request from being declared complete merely because its first action, such as opening an app, succeeded.

The semantic parser is intended to tolerate casual phrasing, abbreviations, mixed language and minor typos without growing a large hard-coded vocabulary. Fuzzy matching is limited to resolving an app hint against the actual installed-app list. Once the intent is understood, predictable low-risk steps are compiled into the persistent Bridge executor so the model is not called between every tap.

RC24 adds a terminal lifecycle around that executor. After Furina has genuinely left Termux, returning to Termux becomes an explicit stop signal in roughly a tenth of a second rather than leaving enough time for another planner cycle. The Core keeps the last external screen as evidence: if the deterministic goal contract is already satisfied the visible result becomes `Berhasil.`; otherwise Furina stops cleanly instead of replaying an app launch. Successful completion also closes the return watcher so completed tasks do not leave a background watcher alive.

Bridge RC14 adds the same rule locally to continuous UI sequences. Once a sequence has left Termux, if Termux becomes foreground again the Bridge aborts remaining steps and reports `cancelled_user_return` to the Core. Tap, text, IME and scroll sequence primitives are guarded from continuing against the Termux UI after that return.

The deterministic direct path is only an atomic latency optimization. An exact command such as opening one known app may execute immediately, while a request such as `buka Google dan cari makanan sehat` must retain both `open_app` and `search` before Furina can report completion.

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

RC24 requires Bridge RC14 for the local sequence circuit breaker. Once RC14 is installed, later Core-only updates do not download the Bridge again unless the manifest's Bridge version increases.

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
