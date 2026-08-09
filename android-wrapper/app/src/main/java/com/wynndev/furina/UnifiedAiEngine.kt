package com.wynndev.furina

import android.os.SystemClock
import kotlinx.coroutines.CancellationException
import org.json.JSONObject

data class UnifiedGenerationResult(
    val userId: String,
    val assistantId: String,
    val metrics: JSONObject,
)

/** Single orchestration path for local and future online provider adapters. */
class UnifiedAiEngine(
    private val store: MemoryStore,
    private val contextEngine: ContextEngine,
    private val providers: Map<String, AiProvider>,
) {
    private fun provider(id: String = "local-llama"): AiProvider =
        providers[id] ?: error("Provider AI tidak tersedia: $id")

    suspend fun prepare(model: ModelSpec, sessionId: String, persona: String) {
        val query = store.lastUserMessage(sessionId)
        provider().prepare(model, contextEngine.build(sessionId, query, persona))
    }

    suspend fun generate(
        requestId: String,
        model: ModelSpec,
        sessionId: String,
        userText: String,
        persona: String,
        onToken: (String) -> Unit,
    ): UnifiedGenerationResult {
        val startedAt = SystemClock.elapsedRealtime()
        var firstTokenAt = 0L
        var tokenCount = 0
        val context = contextEngine.build(sessionId, userText, persona)
        val activeProvider = provider()
        val warmStart = activeProvider.isWarm(model, context)
        activeProvider.prepare(model, context)

        // Persist the user turn even if native generation fails; retries then retain intent.
        val userId = store.addMessage(sessionId, "user", userText)
        val reply = StringBuilder()
        val request = AiGenerationRequest(
            requestId = requestId,
            sessionId = sessionId,
            model = model,
            context = context,
            userMessage = userText,
            predictLength = responseBudgetFor(userText),
        )
        try {
            activeProvider.stream(request).collect { token ->
                if (firstTokenAt == 0L) firstTokenAt = SystemClock.elapsedRealtime()
                tokenCount += 1
                reply.append(token)
                onToken(token)
            }
        } catch (cancelled: CancellationException) {
            // Cancellation has one owner: FurinaBridge. Propagating it avoids
            // emitting both "done" and "cancelled" for the same request.
            throw cancelled
        }

        val finalText = reply.toString().trim()
        check(finalText.isNotBlank()) { "Model tidak menghasilkan jawaban" }
        val assistantId = store.addMessage(sessionId, "assistant", finalText)
        store.updateSessionSummary(sessionId)

        val finishedAt = SystemClock.elapsedRealtime()
        val firstTokenMs = if (firstTokenAt > 0L) firstTokenAt - startedAt else finishedAt - startedAt
        val decodeMs = if (firstTokenAt > 0L) (finishedAt - firstTokenAt).coerceAtLeast(1L) else 1L
        val metrics = JSONObject()
            .put("firstTokenMs", firstTokenMs)
            .put("tokensPerSecond", tokenCount * 1000.0 / decodeMs)
            .put("tokenCount", tokenCount)
            .put("warmStart", warmStart)
            .put("provider", activeProvider.id)
        return UnifiedGenerationResult(userId, assistantId, metrics)
    }

    suspend fun unload() = providers.values.forEach { it.unload() }

    private fun responseBudgetFor(message: String): Int = when {
        message.length <= 40 -> 96
        message.length <= 180 -> 192
        else -> 384
    }
}
