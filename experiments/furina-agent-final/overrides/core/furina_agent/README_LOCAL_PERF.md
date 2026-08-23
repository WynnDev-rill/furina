# Local Performance V2

Runtime goals for the private Furina companion build:

- no model work on a normal `furina` TUI launch unless Local is selected;
- background prewarm when Local becomes active or its chat surface opens;
- keep the selected 1.7B model warm for a bounded idle window;
- first visible stream chunk is never artificially delayed;
- later tiny chunks are coalesced for smoother Termux/Android rendering;
- 4K phone-first context baseline with retrieval preserving relevant memory;
- prompt/KV reuse enabled in llama-server;
- Flash Attention delegated to llama.cpp auto detection by default;
- optional benchmark chooses 4/5/6 threads and only opts into an accelerator after a healthy result;
- stop generation closes the active HTTP stream without unloading the model;
- CPU is always a safe fallback.

The selected model files and quantizations are deliberately unchanged by this performance layer.
