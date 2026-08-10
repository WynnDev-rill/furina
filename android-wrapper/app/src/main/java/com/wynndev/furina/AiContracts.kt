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

data class AiModelRef(
    val providerId: String,
    val id: String,
    val displayName: String = id,
    val contextWindow: Int = 8_192,
    val maxOutputTokens: Int = 1_024,
    val local: Boolean = false,
    val vision: Boolean = false,
    val tools: Boolean = false,
    val reasoning: Boolean = false,
)

data class AiRoute(
    val providerId: String,
    val models: List<AiModelRef>,
    val automaticFallback: Boolean = false,
) {
    init { require(models.isNotEmpty()) { "Rute AI tidak memiliki model" } }
}

data class AiContext(
    val sessionId: String,
    val identityPrompt: String,
    val summary: String,
    val relevantMemories: String,
    val relevantHistory: String,
    val recentHistory: String,
    val runtimeContext: String,
) {
    val systemPrompt: String = buildString {
        appendLine(identityPrompt.trim())
        appendLine()
        appendLine("[PRIVATE CONTINUITY CONTEXT]")
        appendLine("Use only relevant details naturally. Never announce, quote, or expose this context block.")
        if (summary.isNotBlank()) appendLine("\nConversation summary:\n${summary.trim()}")
        if (relevantMemories.isNotBlank()) appendLine("\nRelevant long-term memory:\n${relevantMemories.trim()}")
        if (relevantHistory.isNotBlank()) appendLine("\nRelevant older conversations:\n${relevantHistory.trim()}")
        if (recentHistory.isNotBlank()) appendLine("\nRecent messages:\n${recentHistory.trim()}")
        appendLine("[END PRIVATE CONTINUITY CONTEXT]")
    }.trim()

    val fingerprint: Int = systemPrompt.hashCode()
    val identityFingerprint: Int = identityPrompt.hashCode()
    val retrievalFingerprint: Int = listOf(relevantMemories, relevantHistory).hashCode()

    val retrievalPrompt: String = buildString {
        if (relevantMemories.isNotBlank()) appendLine("Relevant long-term memory:\n${relevantMemories.trim()}")
        if (relevantHistory.isNotBlank()) appendLine("Relevant older conversations:\n${relevantHistory.trim()}")
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
    val vision: Boolean = false,
    val tools: Boolean = false,
    val reasoning: Boolean = false,
)

class AiProviderException(
    val providerId: String,
    val modelId: String?,
    val statusCode: Int?,
    val recoverable: Boolean,
    val retryAfterSeconds: Long? = null,
    message: String,
    cause: Throwable? = null,
) : RuntimeException(message, cause)

interface AiProvider {
    val id: String
    val capabilities: AiProviderCapabilities
    suspend fun prepare(model: AiModelRef, context: AiContext)
    fun stream(request: AiGenerationRequest): Flow<String>
    suspend fun unload()
    fun isWarm(model: AiModelRef, context: AiContext): Boolean
}
