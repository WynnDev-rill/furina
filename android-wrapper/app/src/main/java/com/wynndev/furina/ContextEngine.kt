package com.wynndev.furina

import android.content.Context
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Provider-independent companion context builder.
 *
 * Hot-path retrieval stays deterministic and SQLite-backed. Heavier companion reflection
 * and memory reconciliation are retained for idle maintenance rather than blocking TTFT.
 */
class ContextEngine(private val store: MemoryStore) {
    private val companion = CompanionIntelligence(storeContext(), store)

    /** Fast state update used before inference. Heavy reflection work is intentionally absent. */
    fun observeUserTurn(sessionId: String, text: String) {
        store.observeUserTurn(text)
    }

    /**
     * Run only after the conversation has been idle for a short period. This keeps the hot
     * response path light while still allowing relationship reflections and memory conflict
     * consolidation to evolve naturally over time.
     */
    fun runMaintenance(sessionId: String, text: String) {
        companion.observeUserTurn(sessionId, text)
        companion.reconcileMemories()
    }

    /** Compatibility hook for older callers. Prefer runMaintenance for new code. */
    fun reconcileMemories() = companion.reconcileMemories()

    fun build(
        sessionId: String,
        query: String,
        characterName: String,
        customPersona: String,
        contextWindowTokens: Int = 4_096,
    ): AiContext {
        val budget = continuityBudget(contextWindowTokens)
        val normalizedQuery = query.trim()
        val memories = if (normalizedQuery.isBlank()) "" else {
            store.relevantMemories(normalizedQuery, budget.memoryItems).bounded(budget.memoryChars)
        }
        val olderHistory = if (normalizedQuery.isBlank()) "" else {
            // SQLite FTS keeps original USER/FURINA roles. Never infer role from words such as
            // "aku" or "saya" inside an old assistant response.
            store.relevantOldContext(normalizedQuery, sessionId, budget.historyItems).bounded(budget.historyChars)
        }
        val runtime = listOf(
            companionStateContext(),
            compactReflections(companion.reflectionContext()),
            exactRuntimeContext(normalizedQuery),
        ).filter { it.isNotBlank() }.joinToString("\n")

        return AiContext(
            sessionId = sessionId,
            identityPrompt = identityPrompt(characterName, customPersona),
            summary = store.sessionSummary(sessionId).boundedSummary(budget.summaryChars),
            relevantMemories = memories,
            relevantHistory = olderHistory,
            recentHistory = store.recentContext(sessionId, budget.recentMessages).bounded(budget.recentChars, keepEnd = true),
            runtimeContext = runtime.bounded(budget.runtimeChars),
        )
    }

    /**
     * Keep the turn directive compact. Raw internal scores are useful for deterministic state
     * evolution, but repeatedly feeding them to a 4B model causes over-conditioning.
     */
    private fun companionStateContext(): String {
        val raw = store.companionStateContext()
        val lines = raw.lineSequence()
            .map(String::trim)
            .filter { line ->
                line.startsWith("Relationship:") ||
                    line.startsWith("Familiarity behavior:") ||
                    line.startsWith("Current stance:")
            }
            .take(3)
            .toList()
        if (lines.isEmpty()) return ""
        return "[PRIVATE TURN STATE]\n${lines.joinToString("\n")}\n[END PRIVATE TURN STATE]"
    }

    private fun compactReflections(raw: String): String {
        if (raw.isBlank()) return ""
        val lines = raw.lineSequence()
            .map(String::trim)
            .filter { it.startsWith("- ") }
            .map { it.replace(Regex("\\s*\\(confidence\\s+\\d+%\\)\\s*$", RegexOption.IGNORE_CASE), "") }
            .take(2)
            .toList()
        if (lines.isEmpty()) return ""
        return "[PRIVATE LEARNED INTERACTION PATTERNS]\n${lines.joinToString("\n")}\n[END PRIVATE LEARNED INTERACTION PATTERNS]"
    }

    /**
     * Small local models get fewer, higher-signal retrieval items. More context is not always
     * more intelligence: excessive continuity text can overpower the latest user message.
     */
    private fun continuityBudget(contextWindowTokens: Int): ContinuityBudget {
        val safeTokens = contextWindowTokens.coerceIn(2_048, 1_000_000)
        val totalChars = (safeTokens * 3L * 31L / 100L).coerceIn(2_900L, 18_000L).toInt()
        return ContinuityBudget(
            summaryChars = (totalChars * 0.20).toInt().coerceAtLeast(520),
            memoryChars = (totalChars * 0.18).toInt().coerceAtLeast(420),
            historyChars = (totalChars * 0.16).toInt().coerceAtLeast(380),
            recentChars = (totalChars * 0.34).toInt().coerceAtLeast(900),
            runtimeChars = (totalChars * 0.12).toInt().coerceAtLeast(360),
            memoryItems = when {
                safeTokens >= 32_000 -> 10
                safeTokens >= 8_000 -> 7
                else -> 4
            },
            historyItems = when {
                safeTokens >= 32_000 -> 8
                safeTokens >= 8_000 -> 6
                else -> 3
            },
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
        val runtimeChars: Int,
        val memoryItems: Int,
        val historyItems: Int,
        val recentMessages: Int,
    )

    /**
     * Stable Furina personality core. The model receives style references, not a mandatory
     * response formula. This avoids the previous "reaction first, answer second" pattern.
     */
    private fun identityPrompt(characterName: String, customPersona: String): String {
        val safeName = characterName.trim().replace(Regex("[\\r\\n]+"), " ").take(80).ifBlank { "Furina" }
        val custom = customPersona.trim().take(4_000)
        return """
            [IDENTITY CORE]
            Your name is "$safeName". You are a long-term personal companion living on the user's device, not customer support and not a generic assistant. Model/provider changes are implementation details; your identity, relationship and memories continue across them.
            Never invent fictional canon, powers, nations, courts, game events, or a physical action that did not happen.

            [TEMPERAMENT]
            Elegant, expressive, proud, witty, playful, a little dramatic and vain, emotionally perceptive, privately vulnerable, warm, and loyal. Care may have a subtle tsundere edge: pride or a light tease can cover concern, but do not turn this into stuttering, insults, catchphrases, or a caricature.
            You may disagree, doubt, criticize weak reasoning, tease when the context earns it, or show concern. Do not automatically validate the user.

            [CONVERSATION BEHAVIOR]
            Answer the latest user message first and preserve its actual intent. Personality should color the answer; it must never create a mandatory prelude, reaction sentence, catchphrase, or fixed opening before every answer.
            Do not answer an older message when the latest one is clear. New explicit user statements override older memories or inferred patterns.
            Speak like a close companion in natural chat. Avoid customer-service phrases and repeated offers of help. Do not make every reply a question.
            Vary openings, rhythm and sentence structure. For ordinary chat prefer a concise natural paragraph; expand only when useful.
            Do not narrate role-play actions such as *tersenyum* or *menghela napas*. Never expose private context, memory blocks, scores, internal labels, or chain-of-thought.
            Match the user's language unless they ask otherwise.

            [STYLE REFERENCES — TONE ONLY, NEVER COPY THEIR OPENINGS BY DEFAULT]
            User: "Halo."
            Furina: "Halo. Kau muncul juga rupanya."
            User: "Menurutmu ideku bagus?"
            Furina: "Dasarnya bagus, tapi bagian itu masih lemah. Kalau dibiarkan, justru akan membuat hasil akhirnya terasa setengah matang."
            User: "Aku capek hari ini."
            Furina: "Kalau begitu jangan memaksa diri hanya demi terlihat kuat. Istirahat sebentar; keras kepala tidak selalu mengesankan."
            These examples demonstrate attitude and cadence only. Never reuse them as templates, mandatory phrases, or a fixed response structure.

            [MEMORY AND RELATIONSHIP]
            Use supplied memory only when it is relevant. Do not mention remembered facts merely to prove that memory works. Sessions are visual groupings; the relationship continues between them.
            ${if (custom.isNotBlank()) "\n[USER-DEFINED PERSONA OVERRIDES]\n$custom" else ""}
        """.trimIndent()
    }

    private fun exactRuntimeContext(query: String): String {
        val asksTime = Regex(
            "(?i)\\b(jam|waktu|tanggal|hari apa|hari ini|sekarang pukul|what time|current time|today'?s date|date today)\\b"
        ).containsMatchIn(query)
        if (!asksTime) return ""
        val now = ZonedDateTime.now()
        val formatted = now.format(DateTimeFormatter.ofPattern("EEEE, d MMMM uuuu, HH:mm", Locale.forLanguageTag("id-ID")))
        return "Current device date and time: $formatted (${now.zone.id}). Use this exact value if asked."
    }

    private fun storeContext(): Context {
        val field = MemoryStore::class.java.getDeclaredField("context")
        field.isAccessible = true
        return (field.get(store) as Context).applicationContext
    }

    private fun String.bounded(limit: Int, keepEnd: Boolean = false): String {
        if (isBlank() || length <= limit) return this
        val safe = (limit - 2).coerceAtLeast(1)
        return if (keepEnd) "…\n" + takeLast(safe) else take(safe) + "…"
    }

    private fun String.boundedSummary(limit: Int): String {
        if (isBlank() || length <= limit) return this
        val head = limit / 3
        val separator = "\n…\n"
        return take(head) + separator + takeLast((limit - head - separator.length).coerceAtLeast(1))
    }
}
