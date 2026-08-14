# Furina Agent by Wynn — Final Candidate

Furina Agent runs its AI core in Termux and uses a small Android Bridge APK for device control. It is isolated from the main Furina APK project.

## First install

Install/open Furina Bridge and enable Persistent Bridge + Accessibility. For a fresh Termux, run this single line:

```bash
pkg update -y && pkg install -y curl && curl -fsSL https://raw.githubusercontent.com/WynnDev-rill/furina/experiment/furina-agent-termux/experiments/furina-agent-final/install.sh | bash
```

The installer reconciles the required Termux/Python dependencies, stages and validates the Core before activation, and keeps model/memory data separate from replaceable Core files. No ZIP needs to be copied manually.

If Furina is already installed, update with:

```bash
furina update
```

After setup, daily use is:

```bash
furina
```

Maintenance commands:

```bash
furina doctor
furina repair
furina optimize
```

`furina optimize` benchmarks the local GGUF on the phone and selects a more suitable CPU thread count. It is not run on every startup.

## Android control — Core RC34 / Bridge RC18

The Android agent uses an observe → plan → act → verify loop. Accessibility remains the primary semantic control plane; visual analysis is only a fallback when the semantic tree is insufficient. The ranked Accessibility state is refreshed throughout a task instead of treating the initial screen as permanent.

Semantic tasks distinguish stages such as `open_app`, `search`, `select`, `type`, and `send`. A messaging workflow can therefore be represented as:

```text
open_app → search(contact) → select(contact) → type(message) → send
```

The final external action remains separate from preparation. A send/post/share/call requires specific authorization, and an ambiguous final send is not automatically retried because doing so could duplicate an external effect.

### RC34 chat-first intent boundary

RC34 separates ordinary conversation from device execution before AndroidAgent is allowed to start:

- Mentioning an installed application is only context for target resolution; it is never authority to execute a device action.
- Questions, explanations, reports about past actions, hypotheticals, examples, quotations, and negated commands remain ordinary chat.
- A model-generated `device` classification must also prove that the user made a current command/request and provide an exact action span from the user's message. A deterministic gate validates that evidence before Agent routing.
- If the intent parser/provider fails, the fallback is chat unless the message itself is a structurally explicit device request.
- The fast/direct executor uses the same chat guard so conversational phrases containing action verbs cannot bypass semantic classification.
- Intent-model routing uses its own `intent` role and does not replace the preferred conversation model.

Examples that remain chat:

```text
WhatsApp sekarang sering lambat menurutmu kenapa?
Tadi aku buka WhatsApp lalu chat Ariel
Kalau aku bilang "buka WhatsApp", kamu bakal apa?
Jangan buka WhatsApp
```

Examples that are device requests:

```text
Bisa buka WhatsApp?
Tolong bukain WhatsApp
Buka WhatsApp lalu cari Ariel
```

### RC32 execution boundary

RC32 remains the independent policy layer after RC34 intent routing:

- **Goal Lock** freezes the trusted task scope from the user's goal and grounded semantic intent. Text found in a webpage, message, note, notification, screenshot, or Accessibility node cannot add a new app/capability to the task.
- **Action Firewall** checks every proposed action after planning and before execution. Unknown capabilities fail closed instead of inheriting generic Bridge privileges.
- **Fresh-state resolution** reads the current screen again immediately before a state-changing action. Node IDs are not trusted by themselves; a stable selector must still resolve on the fresh UI state.
- **Package scope guard** blocks an action if the task unexpectedly moves into another installed app outside the Goal Lock.
- **IME classification** treats search submission differently from an ambiguous Enter/IME action that may send or submit data. Message-like IME actions are elevated to the external/uncertain path instead of being treated as ordinary local text input.
- **Privacy filtering** redacts password/PIN/OTP/token/API-key-like Accessibility values before compact UI state is sent to a planner. Vision fallback is disabled on screens classified as sensitive.
- **Sequence validation** checks compiled multi-step UI sequences against the same Goal Lock before the Bridge receives them.

These checks complement, rather than replace, the existing semantic send confirmation, duplicate-send protection, ranked Accessibility tree, high-confidence visual targeting, and deterministic completion gates.

### Device-control modes

The selected backend is configured under **Settings → Kontrol perangkat**. Runtime diagnostics stay in Settings and are not printed into the conversation.

- **Normal** — default. Uses native Android intents where possible and Accessibility for UI actions. No Shizuku or root is required.
- **Shizuku** — optional. Furina Bridge requests Shizuku permission only when this mode is selected and reuses a privileged UserService for supported fixed primitives.
- **Root** — optional. Root is used only when explicitly selected for supported fixed primitives.

Shizuku/root do not expose an arbitrary remote shell through the Furina Core planner API. The privileged interface remains restricted to fixed device-control primitives, with normal Android/Accessibility control retained as fallback.

Natural Android tasks can be given to the Agent, for example:

```text
buka YouTube dan cari MrBeast
bka gogle trus cri makanan sehat
buka WhatsApp, cari Budi, tulis "aku pulang jam 8", lalu kirim
```

Dynamic tasks use the current real screen instead of assuming a previously observed node is still valid. Core RC34 continues to use Bridge RC18, so no new Bridge APK is required when RC18 is already installed.

## Reminders

Reminder scheduling is owned by **Furina Bridge on Android**, not by a Termux background thread. Once a reminder has been scheduled successfully, closing Furina or Termux does not cancel it.

Natural relative forms such as these are supported:

```text
ingatkan aku minum dalam 5 menit
ingatkan aku minum 5 menit lagi
```

The Bridge persists pending reminders, schedules them with Android `AlarmManager`, and restores future alarms after reboot. On Android versions with Exact Alarm access, exact alarms are used; otherwise Android's allow-while-idle fallback is used and delivery may be less exact. Notification permission must remain enabled for Furina Bridge.

## Online provider diagnostics

Use the provider test before blaming an API key itself:

```bash
furina provider-test groq
furina provider-test nvidia
```

AUTO routing prefers a configured online provider and falls back to local inference when online providers are unavailable within the bounded failover budget.

## Safety and validation

Ordinary navigation/text preparation can be authorized per task. External side effects such as Send/Post/Share remain on the guarded path and require specific confirmation. Payment, transfer, uninstall, destructive deletion, factory reset, and security-sensitive changes remain blocked from autonomous execution.

The RC34 CI reconstructs the effective Core from the archived baseline through RC33, applies the RC34 intent boundary, and then runs behavioral regression. Tests cover normal chat containing app names/action words, reports/hypotheticals/negations, parser failure with app mentions, explicit device requests, intent commitment evidence, role isolation, RC32 package/action policy, unknown runtime capabilities, and Bridge RC18 preservation. Installer updates use Git blob verification, staged validation, and atomic Core activation.