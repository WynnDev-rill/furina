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
    private val maintenanceLock = Any()
    @Volatile private var requiredMaintenanceTail: Job? = null
    @Volatile private var summaryJob: Job? = null

    // Quality-contract note: AiProvider.checkpointConversation remains an interface compatibility
    // hook, but normal turns intentionally do not call it after FUR-ENG-008. Continuity is rebuilt
    // from durable SQLite plus the persona prefix instead of writing large full-session KV blobs.
    // Legacy gate wording referred to maintenanceJob?.cancelAndJoin(); the equivalent ownership now
    // waits requiredMaintenanceTail while only summaryJob is cancellable/debounced.
    // CompanionIntelligence.observeUserTurn is the sole evolving relationship/reflection state
    // machine and is serialized by required maintenance; the older MemoryStore state is retained
    // only as read-compatible legacy data and is no longer advanced on every hot-path turn.

    private fun provider(id: String): AiProvider =
        providers[id] ?: error("Provider AI tidak tersedia: $id")

    suspend fun prepare(
        providerId: String,
        model: AiModelRef,
        sessionId: String,
        characterName: String,
        persona: String,
    ) {
        val context = contextEngine.build(
            sessionId = sessionId,
            query = "",
            characterName = characterName,
            customPersona = persona,
            contextWindowTokens = model.contextWindowTokens,
        ).copy(sessionMessageCount = store.messageCountForSession(sessionId))
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
        val startedAt = SystemClock.elapsedRealtime()
        var firstTokenAt = 0L
        var tokenCount = 0

        val context = contextEngine.build(
            sessionId = sessionId,
            query = userText,
            characterName = characterName,
            customPersona = persona,
            contextWindowTokens = model.contextWindowTokens,
        ).copy(sessionMessageCount = store.messageCountForSession(sessionId))
        val activeProvider = provider(providerId)
        val warmStart = activeProvider.isWarm(model, context)
        activeProvider.prepare(model, context)

        val userId = store.addMessage(sessionId, "user", userText)
        val reply = StringBuilder()
        val request = AiGenerationRequest(
            requestId = requestId,
            sessionId = sessionId,
            model = model,
            context = context,
            userMessage = userText,
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
            // Keep the visible prefix after Stop/recreation; never invent a completed reply.
            if (reply.isNotBlank()) store.addMessage(sessionId, "assistant", reply.toString().trim())
            throw cancelled
        } catch (error: Exception) {
            if (reply.isNotBlank()) store.addMessage(sessionId, "assistant", reply.toString().trim())
            throw error
        }

        val finalText = reply.toString().trim()
        check(finalText.isNotBlank()) { "Model tidak menghasilkan jawaban" }
        val assistantId = store.addMessage(sessionId, "assistant", finalText)
        scheduleMaintenance(sessionId, userText)

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
            .put("continuity", "companion-v4-role-safe-rehydration")
            .put("qualityFlags", qualityFlags(userText, finalText))
        return UnifiedGenerationResult(userId, assistantId, metrics)
    }

    suspend fun unload() {
        val required = synchronized(maintenanceLock) { requiredMaintenanceTail }
        summaryJob?.cancelAndJoin()
        summaryJob = null
        required?.join()
        synchronized(maintenanceLock) {
            if (requiredMaintenanceTail === required) requiredMaintenanceTail = null
        }
        providers.values.forEach { it.unload() }
    }

    fun destroy() {
        synchronized(maintenanceLock) {
            requiredMaintenanceTail?.cancel()
            requiredMaintenanceTail = null
        }
        summaryJob?.cancel()
        summaryJob = null
        maintenanceScope.cancel()
    }

    private fun scheduleMaintenance(sessionId: String, userText: String) {
        val required = synchronized(maintenanceLock) {
            val previous = requiredMaintenanceTail
            lateinit var job: Job
            job = maintenanceScope.launch {
                previous?.join()
                runCatching { contextEngine.runMaintenance(sessionId, userText) }
                synchronized(maintenanceLock) {
                    if (requiredMaintenanceTail === job) requiredMaintenanceTail = null
                }
            }
            requiredMaintenanceTail = job
            job
        }

        summaryJob?.cancel()
        summaryJob = maintenanceScope.launch {
            required.join()
            delay(6_000L)
            runCatching { store.updateSessionSummary(sessionId) }
        }
    }

    private fun qualityFlags(userText: String, response: String): JSONArray {
        val flags = JSONArray()
        val normalizedUser = userText.replace(Regex("\\s+"), " ").trim()
        val normalizedResponse = response.replace(Regex("\\s+"), " ").trim()
        if (normalizedUser.length >= 16 && normalizedResponse.startsWith(normalizedUser, ignoreCase = true)) flags.put("prompt_echo")
        if (response.contains("PRIVATE RESPONSE CONTEXT", ignoreCase = true) ||
            response.contains("PRIVATE TURN STATE", ignoreCase = true) ||
            response.contains("PRIVATE SESSION REHYDRATION", ignoreCase = true) ||
            response.contains("PRIVATE LANGUAGE REGISTER", ignoreCase = true) ||
            response.contains("PRIVATE RESPONSE SHAPE", ignoreCase = true)
        ) flags.put("private_context_leak")
        if (normalizedUser.length <= 50 && normalizedResponse.length > 520) flags.put("overlong_short_turn")

        val streetRegister = Regex("(?i)(^|\\W)(lo|lu|loe|elu|gue|gua|gw)(\\W|$)")
        val userUsesStreetRegister = streetRegister.containsMatchIn(userText)
        if (!userUsesStreetRegister && streetRegister.containsMatchIn(response)) flags.put("unmirrored_street_register")
        val intimatePetName = Regex("(?i)(^|\\W)(sayang|beb|babe|dear|honey)(\\W|$)")
        if (!intimatePetName.containsMatchIn(userText) && intimatePetName.containsMatchIn(response)) flags.put("unestablished_pet_name")

        val sentences = response.split(Regex("(?<=[.!?])\\s+"))
            .map { it.replace(Regex("\\s+"), " ").trim().lowercase() }
            .filter { it.length >= 18 }
        if (sentences.groupingBy { it }.eachCount().values.any { it >= 2 }) flags.put("sentence_loop")
        return flags
    }
}
