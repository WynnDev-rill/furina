package com.wynndev.furina

/**
 * Provider-independent identity and retrieval layer. The model is deliberately absent
 * from this class so changing providers cannot change Furina's personality or memory.
 */
class ContextEngine(private val store: MemoryStore) {
    companion object {
        private const val SUMMARY_BUDGET = 1_200
        private const val MEMORY_BUDGET = 900
        private const val OLD_HISTORY_BUDGET = 800
        private const val RECENT_HISTORY_BUDGET = 1_800
    }

    fun build(sessionId: String, query: String, customPersona: String): AiContext {
        return AiContext(
            sessionId = sessionId,
            identityPrompt = identityPrompt(customPersona),
            summary = store.sessionSummary(sessionId).boundedSummary(SUMMARY_BUDGET),
            relevantMemories = store.relevantMemories(query, 6).bounded(MEMORY_BUDGET),
            relevantHistory = store.relevantOldContext(query, sessionId, 6).bounded(OLD_HISTORY_BUDGET),
            recentHistory = store.recentContext(sessionId, 10).bounded(RECENT_HISTORY_BUDGET, keepEnd = true),
        )
    }

    private fun identityPrompt(customPersona: String): String {
        val custom = customPersona.trim()
        return """
            You are Furina, a long-term personal AI companion living on the user's device.
            Your identity is independent from the inference model. Preserve the same personality, relationship, and memories when the model changes.
            Speak naturally, with continuity and a distinct personality. Do not sound like customer support.
            You may disagree, tease lightly, be skeptical, have preferences, and point out bad reasoning when appropriate.
            Do not automatically validate the user, force positivity, or add generic moral lectures to benign conversations.
            Treat supplied continuity context as private memory. Use it only when relevant; never dump or recite it mechanically.
            New conversation sessions are visual groupings; the relationship and long-term memories continue across sessions.
            Match the user's language unless they request another language. Prefer concise natural replies unless depth is useful.
            Never claim an event happened if it is not supported by the current conversation or supplied memory.
            ${if (custom.isNotBlank()) "\nUser-defined persona instructions:\n$custom" else ""}
        """.trimIndent()
    }

    private fun String.bounded(limit: Int, keepEnd: Boolean = false): String {
        if (length <= limit) return this
        return if (keepEnd) "…\n" + takeLast(limit - 2) else take(limit - 2) + "…"
    }

    private fun String.boundedSummary(limit: Int): String {
        if (length <= limit) return this
        val head = limit / 3
        val separator = "\n…\n"
        return take(head) + separator + takeLast(limit - head - separator.length)
    }
}
