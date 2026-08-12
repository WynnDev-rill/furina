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

## Safety

Normal navigation/text input can be approved per task. External side effects such as Send/Post/Share are confirmed again immediately before execution. Payment, transfer, uninstall, destructive deletion, factory reset and security changes remain blocked from autonomous execution.
