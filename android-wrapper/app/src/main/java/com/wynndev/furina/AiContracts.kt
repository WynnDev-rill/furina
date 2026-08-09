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

data class AiContext(
    val sessionId: String,
    val identityPrompt: String,
    val summary: String,
    val relevantMemories: String,
    val relevantHistory: String,
    val recentHistory: String,
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
}

data class AiGenerationRequest(
    val requestId: String,
    val sessionId: String,
    val model: ModelSpec,
    val context: AiContext,
    val userMessage: String,
    val attachments: List<AiAttachment> = emptyList(),
    val predictLength: Int = 384,
)

data class AiProviderCapabilities(
    val streaming: Boolean,
    val offline: Boolean,
    val attachments: Set<String> = emptySet(),
)

interface AiProvider {
    val id: String
    val capabilities: AiProviderCapabilities
    suspend fun prepare(model: ModelSpec, context: AiContext)
    fun stream(request: AiGenerationRequest): Flow<String>
    suspend fun unload()
    fun isWarm(model: ModelSpec, context: AiContext): Boolean
}
