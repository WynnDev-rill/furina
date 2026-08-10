package com.wynndev.furina

import android.os.SystemClock
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject

/** One orchestration path for local and online providers. */
class UnifiedAiEngine(
    private val store: MemoryStore,
    private val contextEngine: ContextEngine,
    private val providers: Map<String, AiProvider>,
) {
    private val providerSwitchMutex = Mutex()
    @Volatile private var activeProviderId: String? = null

    private fun provider(id: String): AiProvider = providers[id] ?: error("Provider AI tidak tersedia: $id")

    suspend fun prepare(route: AiRoute, sessionId: String, characterName: String, persona: String) {
        val model = route.models.first()
        val active = activateProvider(model.providerId)
        val query = store.lastUserMessage(sessionId)
        active.prepare(model, contextEngine.build(sessionId, query, characterName, persona, model.contextWindow))
    }

    suspend fun generate(
        requestId: String,
        route: AiRoute,
        sessionId: String,
        userText: String,
        characterName: String,
        persona: String,
        onToken: (String) -> Unit,
        onFallback: (from: AiModelRef, to: AiModelRef, reason: String) -> Unit = { _, _, _ -> },
    ): UnifiedGenerationResult {
        val startedAt = SystemClock.elapsedRealtime()
        var firstTokenAt = 0L
        var tokenCount = 0
        store.observeUserTurn(userText)

        val userId = store.addMessage(sessionId, "user", userText)
        var chosen: AiModelRef? = null
        var selectedWarmStart = false
        var finalText = ""
        val failedModels = JSONArray()
        var lastError: Throwable? = null

        for ((index, model) in route.models.withIndex()) {
            var emittedThisModel = false
            val reply = StringBuilder()
            try {
                val active = activateProvider(model.providerId)
                val context = contextEngine.build(sessionId, userText, characterName, persona, model.contextWindow)
                val warmStart = active.isWarm(model, context)
                active.prepare(model, context)
                val request = AiGenerationRequest(
                    requestId = requestId,
                    sessionId = sessionId,
                    model = model,
                    context = context,
                    userMessage = userText,
                    predictLength = responseBudgetFor(userText, model.maxOutputTokens),
                )
                active.stream(request).collect { token ->
                    if (firstTokenAt == 0L) firstTokenAt = SystemClock.elapsedRealtime()
                    emittedThisModel = true
                    tokenCount += 1
                    reply.append(token)
                    onToken(token)
                }
                val candidate = reply.toString().trim()
                check(candidate.isNotBlank()) { "Model tidak menghasilkan jawaban" }
                chosen = model
                selectedWarmStart = warmStart
                finalText = candidate
                break
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                lastError = error
                val providerError = error as? AiProviderException
                val hasNext = index < route.models.lastIndex
                val canFallback = route.automaticFallback && hasNext && !emittedThisModel && providerError?.recoverable == true
                failedModels.put(JSONObject()
                    .put("provider", model.providerId)
                    .put("model", model.id)
                    .put("status", providerError?.statusCode ?: -1)
                    .put("reason", error.message.orEmpty().take(240)))
                if (canFallback) {
                    val next = route.models[index + 1]
                    onFallback(model, next, error.message.orEmpty())
                } else {
                    throw error
                }
            }
        }

        if (chosen == null || finalText.isBlank()) throw lastError ?: IllegalStateException("Semua model fallback gagal")
        val assistantId = store.addMessage(sessionId, "assistant", finalText)
        store.updateSessionSummary(sessionId)

        val finishedAt = SystemClock.elapsedRealtime()
        val firstTokenMs = if (firstTokenAt > 0L) firstTokenAt - startedAt else finishedAt - startedAt
        val decodeMs = if (firstTokenAt > 0L) (finishedAt - firstTokenAt).coerceAtLeast(1L) else 1L
        val selected = chosen!!
        val metrics = JSONObject()
            .put("firstTokenMs", firstTokenMs)
            .put("tokensPerSecond", tokenCount * 1000.0 / decodeMs)
            .put("tokenCount", tokenCount)
            .put("warmStart", selectedWarmStart)
            .put("provider", selected.providerId)
            .put("model", selected.id)
            .put("fallbackCount", failedModels.length())
            .put("fallbacks", failedModels)
        return UnifiedGenerationResult(userId, assistantId, metrics)
    }

    suspend fun unload() {
        providers.values.forEach { runCatching { it.unload() } }
        activeProviderId = null
    }

    private suspend fun activateProvider(id: String): AiProvider = providerSwitchMutex.withLock {
        if (activeProviderId != id) {
            activeProviderId?.let { previous -> runCatching { provider(previous).unload() } }
            activeProviderId = id
        }
        provider(id)
    }

    private fun responseBudgetFor(message: String, maxOutputTokens: Int): Int {
        val normalized = message.trim().lowercase()
        val requestedWords = Regex("\\b(\\d{2,4})\\s*(kata|words?)\\b")
            .find(normalized)?.groupValues?.getOrNull(1)?.toIntOrNull()
        val providerMax = maxOutputTokens.coerceIn(96, 4_096)
        if (requestedWords != null) return (requestedWords * 3 / 2).coerceIn(128, providerMax)
        val greeting = Regex("^(hi+|hai+|halo+|hello+|hey+|pagi|siang|sore|malam|apa kabar)[!?. ,]*$")
        val longForm = Regex("\\b(esai|essay|artikel|article|cerita|story|surat|letter|email|laporan|report|rinci|mendetail|detailed|panjang|long-form)\\b")
        val wanted = when {
            greeting.matches(normalized) -> 96
            longForm.containsMatchIn(normalized) -> 768
            message.length <= 40 -> 192
            message.length <= 180 -> 320
            else -> 512
        }
        return wanted.coerceAtMost(providerMax)
    }
}

data class UnifiedGenerationResult(
    val userId: String,
    val assistantId: String,
    val metrics: JSONObject,
)
