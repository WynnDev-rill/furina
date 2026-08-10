package com.wynndev.furina

import android.os.SystemClock
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

data class UnifiedGenerationResult(
    val userId: String,
    val assistantId: String,
    val metrics: JSONObject,
)

/** Single orchestration path for local and online provider adapters. */
class UnifiedAiEngine(
    private val store: MemoryStore,
    private val contextEngine: ContextEngine,
    private val providers: Map<String, AiProvider>,
) {
    private val maintenanceScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    @Volatile private var maintenanceJob: Job? = null

    private fun provider(id: String): AiProvider =
        providers[id] ?: error("Provider AI tidak tersedia: $id")

    suspend fun prepare(
        providerId: String,
        model: AiModelRef,
        sessionId: String,
        characterName: String,
        persona: String,
    ) {
        // Prewarming must never freeze retrieval for the previous user message into the
        // local model. Empty query builds only stable identity + session rehydration.
        val context = contextEngine.build(
            sessionId = sessionId,
            query = "",
            characterName = characterName,
            customPersona = persona,
            contextWindowTokens = model.contextWindowTokens,
        )
        provider(providerId).prepare(model, context)
    }

    suspend fun generate(
        requestId: String,
        providerId: String,
        model: AiModelRef,
        sessionId: String,
        userText: String,
        characterName: String,
        persona: String,
        onToken: (String) -> Unit,
    ): UnifiedGenerationResult {
        maintenanceJob?.cancel()
        val startedAt = SystemClock.elapsedRealtime()
        var firstTokenAt = 0L
        var tokenCount = 0

        // Only lightweight deterministic state updates run before inference.
        contextEngine.observeUserTurn(sessionId, userText)
        val context = contextEngine.build(
            sessionId = sessionId,
            query = userText,
            characterName = characterName,
            customPersona = persona,
            contextWindowTokens = model.contextWindowTokens,
        )
        val activeProvider = provider(providerId)
        val warmStart = activeProvider.isWarm(model, context)
        activeProvider.prepare(model, context)

        // Persist the user turn even if generation fails; retrying keeps the user's intent.
        val userId = store.addMessage(sessionId, "user", userText)
        val reply = StringBuilder()
        val baseBudget = responseBudgetFor(userText)
        val generationBudget = if (activeProvider.capabilities.offline) baseBudget else maxOf(baseBudget, 512)
        val request = AiGenerationRequest(
            requestId = requestId,
            sessionId = sessionId,
            model = model,
            context = context,
            userMessage = userText,
            predictLength = generationBudget.coerceAtMost(model.maxOutputTokens),
        )
        try {
            activeProvider.stream(request).collect { token ->
                if (firstTokenAt == 0L) firstTokenAt = SystemClock.elapsedRealtime()
                tokenCount += 1
                reply.append(token)
                onToken(token)
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        }

        val finalText = reply.toString().trim()
        check(finalText.isNotBlank()) { "Model tidak menghasilkan jawaban" }
        val assistantId = store.addMessage(sessionId, "assistant", finalText)
        store.updateSessionSummary(sessionId)
        scheduleIdleMaintenance(sessionId, userText)

        val finishedAt = SystemClock.elapsedRealtime()
        val firstTokenMs = if (firstTokenAt > 0L) firstTokenAt - startedAt else finishedAt - startedAt
        val decodeMs = if (firstTokenAt > 0L) (finishedAt - firstTokenAt).coerceAtLeast(1L) else 1L
        val metrics = JSONObject()
            .put("firstTokenMs", firstTokenMs)
            .put("tokensPerSecond", tokenCount * 1000.0 / decodeMs)
            .put("tokenCount", tokenCount)
            .put("warmStart", warmStart)
            .put("provider", activeProvider.id)
            .put("model", activeProvider.resolvedModelId() ?: model.id)
            .put("continuity", "companion-v3-layered")
            .put("qualityFlags", qualityFlags(userText, finalText))
        return UnifiedGenerationResult(userId, assistantId, metrics)
    }

    suspend fun unload() = providers.values.forEach { it.unload() }

    /**
     * Heavy memory reconciliation/reflection is postponed until the conversation has been
     * idle. A new user turn cancels the pending job before it starts.
     */
    private fun scheduleIdleMaintenance(sessionId: String, userText: String) {
        maintenanceJob?.cancel()
        maintenanceJob = maintenanceScope.launch {
            delay(6_000L)
            runCatching { contextEngine.runMaintenance(sessionId, userText) }
        }
    }

    /** Lightweight telemetry for the future 100–300 scenario on-device quality benchmark. */
    private fun qualityFlags(userText: String, response: String): JSONArray {
        val flags = JSONArray()
        val normalizedUser = userText.replace(Regex("\\s+"), " ").trim()
        val normalizedResponse = response.replace(Regex("\\s+"), " ").trim()
        if (normalizedUser.length >= 16 && normalizedResponse.startsWith(normalizedUser, ignoreCase = true)) {
            flags.put("prompt_echo")
        }
        if (response.contains("PRIVATE RESPONSE CONTEXT", ignoreCase = true) ||
            response.contains("PRIVATE TURN STATE", ignoreCase = true) ||
            response.contains("PRIVATE SESSION REHYDRATION", ignoreCase = true)
        ) {
            flags.put("private_context_leak")
        }
        val sentences = response.split(Regex("(?<=[.!?])\\s+"))
            .map { it.replace(Regex("\\s+"), " ").trim().lowercase() }
            .filter { it.length >= 18 }
        if (sentences.groupingBy { it }.eachCount().values.any { it >= 2 }) flags.put("sentence_loop")
        return flags
    }

    private fun responseBudgetFor(message: String): Int {
        val normalized = message.trim().lowercase()
        val requestedWords = Regex("\\b(\\d{2,4})\\s*(kata|words?)\\b")
            .find(normalized)
            ?.groupValues
            ?.getOrNull(1)
            ?.toIntOrNull()
        if (requestedWords != null) return (requestedWords * 3 / 2).coerceIn(256, 1_024)

        val greeting = Regex(
            "^(hi+|hai+|halo+|hello+|hey+|pagi|siang|sore|malam|apa kabar)[!?. ,]*$"
        )
        val longForm = Regex(
            "\\b(esai|essay|artikel|article|cerita|story|surat|letter|email|laporan|report|" +
                "rinci|mendetail|detailed|panjang|long-form)\\b"
        )
        return when {
            greeting.matches(normalized) -> 96
            longForm.containsMatchIn(normalized) -> 512
            message.length <= 40 -> 192
            message.length <= 180 -> 256
            else -> 384
        }
    }
}
