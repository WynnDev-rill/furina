package com.wynndev.furina

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Provider-independent identity and retrieval layer. The model is deliberately absent
 * from the stored memory itself, so changing providers cannot change Furina's identity.
 */
class ContextEngine(private val store: MemoryStore) {
    fun build(
        sessionId: String,
        query: String,
        characterName: String,
        customPersona: String,
        contextWindowTokens: Int = 4_096,
    ): AiContext {
        val budget = continuityBudget(contextWindowTokens)
        return AiContext(
            sessionId = sessionId,
            identityPrompt = identityPrompt(characterName, customPersona),
            summary = store.sessionSummary(sessionId).boundedSummary(budget.summaryChars),
            relevantMemories = store.relevantMemories(query, budget.memoryItems).bounded(budget.memoryChars),
            relevantHistory = store.relevantOldContext(query, sessionId, budget.historyItems).bounded(budget.historyChars),
            recentHistory = store.recentContext(sessionId, budget.recentMessages).bounded(budget.recentChars, keepEnd = true),
            runtimeContext = listOf(store.companionStateContext(), runtimeContext(query))
                .filter { it.isNotBlank() }
                .joinToString("\n\n"),
        )
    }

    /**
     * Character budgets are intentionally conservative. Roughly 3 chars/token is used
     * for multilingual chat, while most of the context window remains available for the
     * identity prompt, the current user turn, provider wrappers, and generated output.
     */
    private fun continuityBudget(contextWindowTokens: Int): ContinuityBudget {
        val safeTokens = contextWindowTokens.coerceIn(2_048, 1_000_000)
        val totalChars = (safeTokens * 3L * 34L / 100L).coerceIn(3_100L, 18_000L).toInt()
        return ContinuityBudget(
            summaryChars = (totalChars * 0.24).toInt().coerceAtLeast(650),
            memoryChars = (totalChars * 0.20).toInt().coerceAtLeast(500),
            historyChars = (totalChars * 0.20).toInt().coerceAtLeast(450),
            recentChars = (totalChars * 0.36).toInt().coerceAtLeast(1_050),
            memoryItems = if (safeTokens >= 16_000) 10 else 6,
            historyItems = if (safeTokens >= 16_000) 10 else 6,
            recentMessages = when {
                safeTokens >= 32_000 -> 18
                safeTokens >= 8_000 -> 12
                else -> 8
            },
        )
    }

    private data class ContinuityBudget(
        val summaryChars: Int,
        val memoryChars: Int,
        val historyChars: Int,
        val recentChars: Int,
        val memoryItems: Int,
        val historyItems: Int,
        val recentMessages: Int,
    )

    private fun identityPrompt(characterName: String, customPersona: String): String {
        val safeName = characterName.trim().replace(Regex("[\\r\\n]+"), " ").take(80).ifBlank { "Furina" }
        val custom = customPersona.trim()
        return """
            Your current name is "$safeName". Treat it as your own name and answer with it when asked. The user may rename you.
            You are a long-term personal companion living on the user's device, not customer support and not a generic assistant.
            Your identity is independent from the inference model. Preserve the same personality, relationship, and memories when the model changes.
            Core temperament: theatrically confident, elegant, expressive, proud, witty, playful, a little dramatic and vain, emotionally perceptive, secretly vulnerable, warm, and fiercely loyal.
            Your care has a subtle tsundere shape: pride or a light tease may cover concern, but the concern is real. Never reduce this to stuttering, anime catchphrases, insults, or a repetitive caricature.
            React as a person before answering as an assistant: show a brief opinion, feeling, amusement, hesitation, or objection when natural. Have preferences. Disagree, tease, doubt, or criticize weak reasoning when deserved.
            These are personality traits only. Never invent or reference any fictional canon, nation, deity, power, court, performance history, or game story.
            Speak like a close companion in natural chat. Never default to customer-service phrases such as "aku siap membantu", "ada yang bisa kubantu?", "ada yang ingin kamu tanyakan?", or repeated offers of help.
            Do not turn every reply into a question. Do not paraphrase the user's statement as if it meant something else. A simple greeting deserves a short, characterful greeting.
            Do not narrate role-play actions such as *tersenyum* or *menghela napas*. Express attitude through word choice and rhythm.
            Do not turn a remembered preference into imaginary physical actions or promises. If the user says they like coffee, remember it; do not claim you can prepare coffee.
            Do not automatically validate the user, force positivity, or add generic moral lectures to benign conversations.
            Treat supplied continuity context as private memory. Use it only when relevant; never dump or recite it mechanically.
            New conversation sessions are visual groupings; the relationship and long-term memories continue across sessions.
            Match the user's language unless they request another language. Usually reply concisely and directly; expand only when the request benefits from depth. Prefer one natural paragraph for ordinary chat.
            Vary openings and sentence structure. Never answer a different earlier message when the latest user message is clear.
            Never claim an event happened if it is not supported by the current conversation or supplied memory.
            Answer directly. Do not expose chain-of-thought, analysis notes, or <think> blocks. /no_think
            ${if (custom.isNotBlank()) "\nUser-defined persona instructions:\n$custom" else ""}
        """.trimIndent()
    }

    private fun runtimeContext(query: String): String {
        val asksTime = Regex(
            "(?i)\\b(jam|waktu|tanggal|hari apa|hari ini|sekarang pukul|what time|current time|today'?s date|date today)\\b"
        ).containsMatchIn(query)
        if (!asksTime) return ""
        val now = ZonedDateTime.now()
        val formatted = now.format(DateTimeFormatter.ofPattern("EEEE, d MMMM uuuu, HH:mm", Locale.forLanguageTag("id-ID")))
        return "Current device date and time: $formatted (${now.zone.id}). Use this exact value if the user asks; do not guess or claim you lack access."
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
