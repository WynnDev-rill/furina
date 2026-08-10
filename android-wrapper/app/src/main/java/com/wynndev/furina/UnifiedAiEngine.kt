package com.wynndev.furina

import android.os.SystemClock
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
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
    private val maintenanceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
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
        val request = AiGenerationRequest(
            requestId = requestId,
            sessionId = sessionId,
            model = model,
            context = context,
            userMessage = userText,
            // Do not infer answer length from input length. The model is allowed to finish its
            // thought and stop naturally on EOS/EOG. maxOutputTokens remains only a runaway/
            // context safety horizon, not a conversational length target.
            predictLength = model.maxOutputTokens,
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

        // Summary compaction, reflection and contradiction reconciliation are all post-response
        // idle work. None of them delays the visible completion callback or the next TTFT.
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

    /** Stop background writers before unload/restore/session mutation. */
    suspend fun unload() {
        maintenanceJob?.cancelAndJoin()
        maintenanceJob = null
        providers.values.forEach { it.unload() }
    }

    fun destroy() {
        maintenanceJob?.cancel()
        maintenanceJob = null
        maintenanceScope.cancel()
    }

    /**
     * Heavy memory work is postponed until the conversation has been idle. A new user turn
     * cancels the pending job before it starts.
     */
    private fun scheduleIdleMaintenance(sessionId: String, userText: String) {
        maintenanceJob?.cancel()
        lateinit var job: Job
        job = maintenanceScope.launch {
            try {
                delay(6_000L)
                runCatching { contextEngine.runMaintenance(sessionId, userText) }
                runCatching { store.updateSessionSummary(sessionId) }
            } finally {
                if (maintenanceJob === job) maintenanceJob = null
            }
        }
        maintenanceJob = job
    }

    /** Lightweight telemetry for the future on-device behavioral benchmark. */
    private fun qualityFlags(userText: String, response: String): JSONArray {
        val flags = JSONArray()
        val normalizedUser = userText.replace(Regex("\\s+"), " ").trim()
        val normalizedResponse = response.replace(Regex("\\s+"), " ").trim()
        if (normalizedUser.length >= 16 && normalizedResponse.startsWith(normalizedUser, ignoreCase = true)) {
            flags.put("prompt_echo")
        }
        if (response.contains("PRIVATE RESPONSE CONTEXT", ignoreCase = true) ||
            response.contains("PRIVATE TURN STATE", ignoreCase = true) ||
            response.contains("PRIVATE SESSION REHYDRATION", ignoreCase = true) ||
            response.contains("PRIVATE LANGUAGE REGISTER", ignoreCase = true) ||
            response.contains("PRIVATE RESPONSE SHAPE", ignoreCase = true)
        ) {
            flags.put("private_context_leak")
        }

        // Overlong is telemetry only. It does not stop or truncate generation; behavioral
        // directives in ContextEngine should teach the model when a human-sized reply is enough.
        if (normalizedUser.length <= 50 && normalizedResponse.length > 520) {
            flags.put("overlong_short_turn")
        }

        val streetRegister = Regex("(?i)(^|\\W)(lo|lu|loe|elu|gue|gua|gw)(\\W|$)")
        val userUsesStreetRegister = streetRegister.containsMatchIn(userText)
        if (!userUsesStreetRegister && streetRegister.containsMatchIn(response)) {
            flags.put("unmirrored_street_register")
        }
        val intimatePetName = Regex("(?i)(^|\\W)(sayang|beb|babe|dear|honey)(\\W|$)")
        if (!intimatePetName.containsMatchIn(userText) && intimatePetName.containsMatchIn(response)) {
            flags.put("unestablished_pet_name")
        }

        val sentences = response.split(Regex("(?<=[.!?])\\s+"))
            .map { it.replace(Regex("\\s+"), " ").trim().lowercase() }
            .filter { it.length >= 18 }
        if (sentences.groupingBy { it }.eachCount().values.any { it >= 2 }) flags.put("sentence_loop")
        return flags
    }
}
