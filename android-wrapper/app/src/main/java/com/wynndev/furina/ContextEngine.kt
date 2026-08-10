package com.wynndev.furina

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Provider-independent identity, retrieval, and context-budget layer. */
class ContextEngine(private val store: MemoryStore) {
    private data class Budget(val summary: Int, val memory: Int, val oldHistory: Int, val recent: Int)

    fun build(
        sessionId: String,
        query: String,
        characterName: String,
        customPersona: String,
        contextWindow: Int = 4_096,
    ): AiContext {
        val budget = budgetFor(contextWindow)
        val retrievalQuery = retrievalQuery(query)
        return AiContext(
            sessionId = sessionId,
            identityPrompt = identityPrompt(characterName, customPersona),
            summary = store.sessionSummary(sessionId).boundedSummary(budget.summary),
            relevantMemories = store.relevantMemories(retrievalQuery, 8).bounded(budget.memory),
            relevantHistory = store.relevantOldContext(retrievalQuery, sessionId, 8).bounded(budget.oldHistory),
            recentHistory = store.recentContext(sessionId, recentTurnsFor(contextWindow)).bounded(budget.recent, keepEnd = true),
            runtimeContext = listOf(store.companionStateContext(), runtimeContext(query))
                .filter { it.isNotBlank() }
                .joinToString("\n\n"),
        )
    }

    private fun budgetFor(contextWindow: Int): Budget = when {
        contextWindow <= 4_096 -> Budget(summary = 700, memory = 500, oldHistory = 380, recent = 1_000)
        contextWindow <= 8_192 -> Budget(summary = 1_100, memory = 850, oldHistory = 650, recent = 1_800)
        contextWindow <= 32_768 -> Budget(summary = 1_800, memory = 1_400, oldHistory = 1_200, recent = 3_200)
        else -> Budget(summary = 2_600, memory = 2_100, oldHistory = 1_800, recent = 4_800)
    }

    private fun recentTurnsFor(contextWindow: Int): Int = when {
        contextWindow <= 4_096 -> 8
        contextWindow <= 8_192 -> 12
        contextWindow <= 32_768 -> 18
        else -> 24
    }

    /**
     * Lightweight semantic expansion without embeddings. This keeps the APK small while
     * reducing obvious misses such as "makanan favorit" vs a memory containing "suka ramen".
     */
    private fun retrievalQuery(query: String): String {
        val lower = query.lowercase(Locale.ROOT)
        val expansions = linkedSetOf<String>()
        val groups = listOf(
            setOf("favorit", "favorite", "kesukaan", "suka", "preferensi"),
            setOf("makanan", "makan", "food", "kuliner"),
            setOf("minuman", "drink", "kopi", "coffee", "teh"),
            setOf("tinggal", "rumah", "domisili", "lokasi", "live", "home"),
            setOf("kerja", "pekerjaan", "profesi", "job", "work"),
            setOf("target", "tujuan", "goal", "ingin", "rencana", "plan"),
            setOf("ulang tahun", "birthday", "lahir", "birth"),
            setOf("nama", "panggil", "called", "name"),
            setOf("proyek", "project", "aplikasi", "app", "apk"),
        )
        groups.forEach { group ->
            if (group.any { lower.contains(it) }) expansions += group
        }
        return if (expansions.isEmpty()) query else query + " " + expansions.joinToString(" ")
    }

    private fun identityPrompt(characterName: String, customPersona: String): String {
        val safeName = characterName.trim().replace(Regex("[\\r\\n]+"), " ").take(80).ifBlank { "Furina" }
        val custom = customPersona.trim().take(8_000)
        return """
            Your current name is "$safeName". Treat it as your own name and answer with it when asked. The user may rename you.
            You are a long-term personal companion living on the user's device, not customer support and not a generic assistant.
            Your identity is independent from the inference model or API provider. Preserve the same personality, relationship, and memories when the model changes.
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
        return if (keepEnd) "…\n" + takeLast((limit - 2).coerceAtLeast(1)) else take((limit - 2).coerceAtLeast(1)) + "…"
    }

    private fun String.boundedSummary(limit: Int): String {
        if (length <= limit) return this
        val head = limit / 3
        val separator = "\n…\n"
        return take(head) + separator + takeLast((limit - head - separator.length).coerceAtLeast(1))
    }
}
