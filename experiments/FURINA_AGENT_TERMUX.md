# Furina Agent Termux experiment

This branch is intentionally isolated from the existing Furina APK. The experiment source is stored as `experiments/furina-agent-termux.tar.gz.b64` so the current app tree, package, signing, database, OTA path, and stable workflows remain untouched.

Source bundle SHA-256 after base64 decode + gunzip archive: `02e951ff71640ee4a001e8819fd42667deff433ce084f055d5e7b3c371a5f692`.

The bundle contains:
- Termux local AI core using llama.cpp
- SQLite persistent memory + retrieval
- local Furina persona layer
- Android agent planner with approval gate
- separate Android Accessibility bridge package `com.wynndev.furinaagentbridge`
- localhost-only bridge with pairing token
- installer and uninstall helper

This branch is experimental and must not be merged into `main` until device validation is complete.