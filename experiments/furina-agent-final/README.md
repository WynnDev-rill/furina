# Furina Agent by Wynn — Final Candidate

Furina Agent runs its AI core in Termux and uses a small Android Bridge APK for Accessibility/device control. It is isolated from the main Furina APK project.

## First install

Install/open Furina Bridge, enable Persistent Bridge + Accessibility, then run the one-line installer published in the experiment branch. No ZIP needs to be copied to internal storage and no pairing code is required.

After setup, daily use is simply:

```bash
furina
```

Maintenance:

```bash
furina update
furina doctor
furina repair
furina optimize
```

`furina optimize` benchmarks the actual local GGUF on the phone and selects a better CPU thread count. It is not run every startup.

## Android control

Furina does not require Termux:API for normal app control. The dedicated Furina Bridge already provides the installed-app list, `open_app`, Accessibility tree inspection, tap, swipe and text input directly through Android.

Natural Android tasks can therefore be given to the Agent, for example:

```text
buka YouTube dan cari MrBeast
buka WhatsApp, cari Budi, tulis "aku pulang jam 8", lalu kirim
```

The planner must verify the resulting screen after each state-changing action. For messaging apps it may prepare the recipient and message, but the final Send/Kirim action is treated as an external side effect and is confirmed again immediately before execution.

Termux:API can remain an optional future adapter for capabilities that the Bridge does not currently expose, such as selected sensors or Android system services. It is not a dependency for YouTube/WhatsApp navigation.

## Online provider diagnostics

Use the provider test before blaming the API key itself:

```bash
furina provider-test groq
furina provider-test nvidia
```

The online routing hotfix keeps model metadata type-stable so providers that return an empty `pricing` object cannot crash model ranking.

## Safety

Normal navigation/text input can be approved per task. External side effects such as Send/Post/Share are confirmed again immediately before execution. Payment, transfer, uninstall, destructive deletion, factory reset and security changes remain blocked from autonomous execution.
