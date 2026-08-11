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

/** Provider-neutral model identity and inference limits. */
data class AiModelRef(
    val providerId: String,
    val id: String,
    val displayName: String,
    val contextWindowTokens: Int = 4_096,
    val maxOutputTokens: Int = 1_024,
    val offline: Boolean = false,
)

/**
 * Companion context is layered so local llama.cpp can keep one immutable persona KV prefix.
 * Session rehydration and query-dependent retrieval are mutable turn context and therefore do
 * not force the expensive personality prefix to be decoded again after every process restart.
 */
data class AiContext(
    val sessionId: String,
    val identityPrompt: String,
    val summary: String,
    val relevantMemories: String,
    val relevantHistory: String,
    val recentHistory: String,
    val runtimeContext: String,
    val sessionMessageCount: Int = 0,
) {
    /** Stable local SYSTEM prefix. Its fingerprint is suitable for persistent KV checkpoints. */
    val personaPrompt: String = identityPrompt.trim()

    /** Mutable session continuity. Local mode injects this only when a session needs rehydration. */
    val sessionRehydrationPrompt: String = buildString {
        if (summary.isNotBlank() || recentHistory.isNotBlank()) {
            appendLine("[PRIVATE SESSION REHYDRATION]")
            appendLine("Background only. Preserve continuity without mechanically repeating it.")
            if (summary.isNotBlank()) appendLine("\nConversation summary:\n${summary.trim()}")
            if (recentHistory.isNotBlank()) appendLine("\nRecent messages:\n${recentHistory.trim()}")
            appendLine("[END PRIVATE SESSION REHYDRATION]")
        }
    }.trim()

    /** Full stateless-provider bootstrap retained for online adapters. */
    val coldStartPrompt: String = buildString {
        appendLine(personaPrompt)
        if (sessionRehydrationPrompt.isNotBlank()) {
            appendLine()
            appendLine(sessionRehydrationPrompt)
        }
    }.trim()

    /** Stateless-provider prompt. Retrieval is rebuilt per request. */
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
    val identityFingerprint: Int = personaPrompt.hashCode()
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

    /** Called only after a complete assistant turn has been durably stored. */
    suspend fun checkpointConversation(context: AiContext, messageCount: Int) = Unit
}
