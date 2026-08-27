# Training prompt library

The Core ships original Indonesian test utterances curated for Furina's nine
Training Room categories. They are neutral prompt-only inputs: no assistant
answer, persona, character lore, user memory, or relationship state is stored
inside the library.

The ingestion quality gates were informed by two public conversation datasets:

- PIPPA, Apache-2.0: https://huggingface.co/datasets/PygmalionAI/PIPPA
- WildChat, ODC-By: https://huggingface.co/datasets/allenai/WildChat

No raw PIPPA, WildChat, Character.AI, Reddit, or ChatGPT conversation is bundled
with Core 1.1.25. Their adapters deliberately accept human turns only and reject
assistant output, persona definitions, lore, role-play actions, PII, NSFW,
crisis, medical, political, technical, and forum-specific content. The built-in
Indonesian entries remain the trusted offline seed; after they are exhausted,
the selected model derives a new neutral prompt under the same quality contract.
