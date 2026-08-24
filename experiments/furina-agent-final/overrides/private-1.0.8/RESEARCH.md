# 1.0.8 local conversation research notes

The 1.0.8 design is based on observed device behavior plus public model/platform guidance:

- `n0ctyx/wifuGPT-1.7B-GGUF` identifies itself as a Qwen3 waifu/roleplay/conversational model. Its published companion dataset contains 403 synthetic multi-turn conversations across greetings, emotional support, flirty, roleplay, and related categories. This makes roleplay priors useful for personality but also means low-information turns can over-trigger scenario completion if context is not grounded.
- Qwen3 1.7B guidance recommends non-thinking sampling around temperature 0.7, top-p 0.8, top-k 20, min-p 0, warns against greedy decoding because of repetition, and notes presence penalty as an optional repetition control with a language-mixing tradeoff at higher values.
- Character.AI's current creator/memory guidance emphasizes stable character definition, keeping memory concise, separating persistent facts/story memory from message history, removing bad chat turns from active context, and testing for drift/repetition. Its product memory also separates Facts/Story Memory/message-history usage rather than treating all prior text as equivalent truth.

Furina therefore uses Dialogue State as a provenance-aware short-term representation rather than canned replies or post-generation regex fixes. User messages are authoritative conversation evidence; prior Furina text is continuity only until confirmed. Trusted long-term memory remains a separate shared store.
