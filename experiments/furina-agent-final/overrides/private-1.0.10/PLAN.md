# Furina 1.0.10 plan

- Fix local repetition/self-anchoring by reducing assistant-text replay and moving persona from trope labels to behavioral logic.
- Introduce one shared Core personality system with 20 independent selectable traits and unlimited combinations.
- Add Termux personalization toggle UI under Settings.
- Replace FurinaHub personalization with the same 20 shared toggles.
- Remove FurinaHub update-check/update controls and periodic update polling; Termux `furina update` becomes the sole update orchestrator for Core + FurinaHub APK.
- Repair FurinaHub local model selection so it writes the same Core routing/model state as Termux.
- Eliminate repeated Hub task/process churn by keeping chat/model/status work in the existing Core process and bounding polling/state cleanup.
- Preserve three current local models, shared memory, dialogue state, streaming, user data, session isolation and update rollback.
- Promote Core/FurinaHub to 1.0.10 after exact-head regressions and signed release validation.
