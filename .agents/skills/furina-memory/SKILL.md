---
name: furina-memory
description: Preserve Furina's long-term continuity across every conversation session.
---

# Furina Memory

Use this skill whenever changing chat persistence, retrieval, session handling, or memory extraction.

## Non-negotiable rules

1. Raw conversation history is canonical. Never replace or delete old raw messages merely because summaries exist.
2. A new conversation creates only a new `session_id`; it never resets user memory, relationship state, persona, or global history.
3. Keep inference context bounded. Retrieve a small set of relevant old messages plus recent current-session turns instead of stuffing the entire archive into the model.
4. Memory features must be local-first and work without network access.
5. Extracted facts are secondary indexes over raw history. They must be editable/rebuildable and must never become the sole source of truth.
6. Retrieval should consider relevance and recency. Avoid repeatedly injecting unrelated facts.
7. Memory work must run after or alongside the visible response when possible; never add avoidable latency to first-token time.
8. Schema changes must preserve years of historical data and include a migration path.

## Current runtime

- Raw archive: Android SQLite `furina_memory.db`.
- Full-text retrieval: SQLite FTS where available, with lexical fallback.
- Relationship continuity: derived from global turn/session history.
- Active model context: compact recent + relevant old context.

## Review checklist

- Does New Chat preserve continuity?
- Can all raw messages still be exported/restored?
- Is retrieval bounded?
- Does the change add latency before generation?
- Can the index be rebuilt from canonical data?
