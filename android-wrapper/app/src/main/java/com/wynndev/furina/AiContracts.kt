package com.wynndev.furina

import kotlinx.coroutines.flow.Flow

enum class AiRole { SYSTEM, USER, ASSISTANT }

data class AiMessage(
    val role: AiRole,
    val content: String,
    val createdAt: Long = 0L,
)

data class AiAttachment(
    val uri: String,
    val mimeType: String,
    val displayName: String,
)

/**
 * Provider-neutral model identity. Local GGUF metadata stays in ModelSpec while the
 * orchestration layer only depends on capabilities that matter to prompting.
 */
data class AiModelRef(
    val providerId: String,
    val id: String,
    val displayName: String,
    val contextWindowTokens: Int = 4_096,
    val maxOutputTokens: Int = 1_024,
    val offline: Boolean = false,
)

/**
 * Companion context is deliberately layered instead of being one giant mutable prompt.
 *
 * - identityPrompt: stable Furina identity, temperament, style examples and boundaries.
 * - summary/recentHistory: session rehydration after a cold model load.
 * - relevantMemories/relevantHistory: query-dependent retrieval for the current turn.
 * - runtimeContext: compact relationship/emotional/situational state for the current turn.
 *
 * Stable identity and mutable session continuity are represented separately so the local
 * runtime can eventually retain an identity-only SYSTEM KV prefix across session switches.
 * coldStartPrompt intentionally composes both layers for the existing fail-closed path, so
 * this contract split alone does not change inference behavior. Query-dependent retrieval
 * is never frozen into that bootstrap prompt. Stateless online models still receive
 * systemPrompt on every request.
 */
data class AiContext(
    val sessionId: String,
    val identityPrompt: String,
    val summary: String,
    val relevantMemories: String,
    val relevantHistory: String,
    val recentHistory: String,
    val runtimeContext: String,
) {
    /** Stable SYSTEM material that is safe to fingerprint/reuse independently of a session. */
    val identitySystemPrompt: String = identityPrompt.trim()

    /**
     * Private session-scoped continuity. This is SYSTEM/background material, never a USER turn.
     * Keeping it separate prevents future warm-rehydrate optimization from contaminating the
     * latest user message merely to avoid rebuilding the stable identity prefix.
     */
    val sessionRehydrationPrompt: String = buildString {
        if (summary.isNotBlank() || recentHistory.isNotBlank()) {
            appendLine("[PRIVATE SESSION REHYDRATION]")
            appendLine("Background only. Preserve continuity without mechanically repeating it.")
            if (summary.isNotBlank()) appendLine("\nConversation summary:\n${summary.trim()}")
            if (recentHistory.isNotBlank()) appendLine("\nRecent messages:\n${recentHistory.trim()}")
            appendLine("[END PRIVATE SESSION REHYDRATION]")
        }
    }.trim()

    /** Existing cold/full-prefill behavior, now composed from explicit stable/mutable layers. */
    val coldStartPrompt: String = buildString {
        appendLine(identitySystemPrompt)
        if (sessionRehydrationPrompt.isNotBlank()) {
            appendLine()
            appendLine(sessionRehydrationPrompt)
        }
    }.trim()

    /** Stateless-provider prompt. Retrieval belongs here because it is rebuilt per request. */
    val systemPrompt: String = buildString {
        appendLine(coldStartPrompt)
        if (relevantMemories.isNotBlank() || relevantHistory.isNotBlank()) {
            appendLine()
            appendLine("[PRIVATE RELEVANT CONTINUITY]")
            appendLine("Use only details that materially help the latest user message. Newer explicit user statements win.")
            if (relevantMemories.isNotBlank()) appendLine("\nRelevant long-term memory:\n${relevantMemories.trim()}")
            if (relevantHistory.isNotBlank()) appendLine("\nRelevant older conversations:\n${relevantHistory.trim()}")
            appendLine("[END PRIVATE RELEVANT CONTINUITY]")
        }
    }.trim()

    val fingerprint: Int = systemPrompt.hashCode()
    // Preserve the pre-split fingerprint contract exactly; callers may use it for warm-state identity checks.
    val identityFingerprint: Int = identityPrompt.hashCode()
    val sessionContinuityFingerprint: Int = sessionRehydrationPrompt.hashCode()
    val retrievalFingerprint: Int = listOf(relevantMemories, relevantHistory).hashCode()

    val retrievalPrompt: String = buildString {
        if (relevantMemories.isNotBlank()) appendLine("Relevant long-term memory:\n${relevantMemories.trim()}")
        if (relevantHistory.isNotBlank()) appendLine("Relevant older conversations:\n${relevantHistory.trim()}")
    }.trim()

    val turnContext: String = buildString {
        if (runtimeContext.isNotBlank()) appendLine(runtimeContext.trim())
        if (retrievalPrompt.isNotBlank()) appendLine(retrievalPrompt)
    }.trim()
}

data class AiGenerationRequest(
    val requestId: String,
    val sessionId: String,
    val model: AiModelRef,
    val context: AiContext,
    val userMessage: String,
    val attachments: List<AiAttachment> = emptyList(),
    val predictLength: Int = 384,
)

data class AiProviderCapabilities(
    val streaming: Boolean,
    val offline: Boolean,
    val attachments: Set<String> = emptySet(),
    val systemPrompt: Boolean = true,
)

interface AiProvider {
    val id: String
    val capabilities: AiProviderCapabilities
    suspend fun prepare(model: AiModelRef, context: AiContext)
    fun stream(request: AiGenerationRequest): Flow<String>
    suspend fun unload()
    fun isWarm(model: AiModelRef, context: AiContext): Boolean
    fun resolvedModelId(): String? = null
}
