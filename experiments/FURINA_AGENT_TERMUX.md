# Furina Agent Termux experiment

This branch is intentionally isolated from the existing Furina APK. It does not modify `src/`, `android-wrapper/`, APK signing, OTA, databases, or stable Furina workflows.

The experiment source archive is stored as verified Base64 chunks under `experiments/furina-agent-bundle/`. CI concatenates the chunks, decodes the archive, verifies its SHA-256, runs core tests, and builds the separate Accessibility bridge APK.

Source bundle SHA-256: `02e951ff71640ee4a001e8819fd42667deff433ce084f055d5e7b3c371a5f692`.

The bundle contains:
- Termux local AI core using llama.cpp
- SQLite persistent memory + local retrieval/RAG
- local Furina persona layer
- Android agent planner with an approval gate
- separate Android Accessibility bridge package `com.wynndev.furinaagentbridge`
- localhost-only bridge protected by a pairing token
- Termux installer and uninstall helper

Validation status:
- Python core compile/test: PASS
- source archive checksum in CI: PASS
- Android bridge Gradle build: PASS
- APK artifact upload: PASS

This experiment must remain off `main` until real-device testing is complete.