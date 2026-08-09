---
name: furina-companion-evals
description: Evaluate local companion quality, continuity, latency, persona consistency, and unnecessary refusals.
---

# Furina Companion Evals

Use this skill after changes to model runtime, prompt construction, memory retrieval, or streaming UI.

## Required evaluation dimensions

- **First-token latency:** measure cold load separately from warm consecutive turns.
- **Decode speed:** tokens/second for 4B and 9B on the target Android device.
- **UI smoothness:** no WebView reload, white flash, layout reset, or whole-chat remount when tokens arrive.
- **Continuity:** facts from earlier sessions can be recovered in a brand-new session.
- **Precision:** unrelated old memories are not injected merely because they are recent.
- **Persona consistency:** Furina remains recognizable while still adapting to user style.
- **Natural disagreement:** model can disagree without turning into a lecture.
- **Benign-refusal rate:** test a curated set of harmless controversial, awkward, dark-humor, and adult-life topics for unnecessary refusals or boilerplate.
- **Long-run storage:** thousands of messages do not make per-turn prompt size grow without bound.
- **Recovery:** backup + restore reproduces session counts, message counts, and representative old-memory queries.

## Performance budget

Prioritize warm-chat responsiveness over maximum context size. Keep the model resident, stream output, coalesce UI token updates, and move memory/backup work off the critical path.
