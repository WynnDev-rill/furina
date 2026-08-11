package com.wynndev.furina

import android.content.Context
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

class LocalLlamaProvider(
    context: Context,
    private val modelDownloads: ModelDownloadManager,
    private val onState: (String, String, Double) -> Unit,
) : AiProvider {
    override val id = "local-llama"
    override val capabilities = AiProviderCapabilities(streaming = true, offline = true)

    private val appContext = context.applicationContext
    private val engine: InferenceEngine = AiChat.getInferenceEngine(appContext)
    private val loadMutex = Mutex()

    @Volatile private var loadedModelId: String? = null
    @Volatile private var loadedSessionId: String? = null
    @Volatile private var loadedIdentityFingerprint: Int? = null
    @Volatile private var loadedRetrievalFingerprint: Int? = null

    override fun isWarm(model: AiModelRef, context: AiContext): Boolean =
        loadedModelId == model.id && engine.state.value is InferenceEngine.State.ModelReady

    override suspend fun prepare(model: AiModelRef, context: AiContext) = loadMutex.withLock {
        val spec = ModelCatalog.byId(model.id) ?: error("Model lokal tidak dikenal: ${model.id}")
        if (isWarm(model, context)) {
            // Keep native chat/KV history warm. Only session or identity changes justify
            // rebuilding the stable bootstrap prompt. Query retrieval stays per-turn.
            if (loadedSessionId != context.sessionId || loadedIdentityFingerprint != context.identityFingerprint) {
                ProcessExitDiagnostics.mark(appContext, "offline-prompt-rehydrate")
                onState("prompting", spec.id, 0.85)
                engine.setSystemPrompt(context.coldStartPrompt)
                loadedSessionId = context.sessionId
                loadedIdentityFingerprint = context.identityFingerprint
                loadedRetrievalFingerprint = null
                ProcessExitDiagnostics.mark(appContext, "idle")
                onState("ready", spec.id, 1.0)
            }
            return@withLock
        }

        if (engine.state.value is InferenceEngine.State.Generating) {
            withTimeout(15_000L) {
                engine.state.first { it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error }
            }
        }
        if (isWarm(model, context)) return@withLock

        ProcessExitDiagnostics.mark(appContext, "offline-verify")
        onState("preparing", spec.id, 0.0)
        withContext(Dispatchers.IO) {
            if (!modelDownloads.verifySerialized(spec) { done, total ->
                    if (total > 0L) onState("verifying", spec.id, done.toDouble() / total.toDouble())
                }) {
                throw IllegalStateException("Checksum model tidak cocok. Hapus lalu unduh ulang model.")
            }
        }

        ProcessExitDiagnostics.mark(appContext, "offline-storage-migrate")
        val file = withContext(Dispatchers.IO) {
            modelDownloads.ensureRuntimeModel(spec) { done, total ->
                if (total > 0L) onState("verifying", spec.id, done.toDouble() / total.toDouble())
            }
        }

        waitForInitialization()
        if (engine.state.value is InferenceEngine.State.ModelReady || engine.state.value is InferenceEngine.State.Error) {
            unload()
        }

        require(file.exists() && file.canRead()) { "File model tidak dapat dibaca: ${file.absolutePath}" }
        ProcessExitDiagnostics.mark(appContext, "offline-engine-load")
        onState("loading", spec.id, 0.15)
        engine.loadModel(file.absolutePath)
        ProcessExitDiagnostics.mark(appContext, "offline-system-prompt")
        onState("prompting", spec.id, 0.85)
        engine.setSystemPrompt(context.coldStartPrompt)
        loadedModelId = spec.id
        loadedSessionId = context.sessionId
        loadedIdentityFingerprint = context.identityFingerprint
        loadedRetrievalFingerprint = null
        ProcessExitDiagnostics.mark(appContext, "idle")
        onState("ready", spec.id, 1.0)
    }

    override fun stream(request: AiGenerationRequest): Flow<String> = flow {
        check(isWarm(request.model, request.context)) { "Provider lokal belum siap untuk konteks ini" }
        var emitted = false
        val reasoningFilter = ReasoningStreamFilter()
        val privateContextFilter = PrivateContextStreamFilter()
        val retrievalChanged = loadedRetrievalFingerprint != request.context.retrievalFingerprint

        val turnContext = buildString {
            if (request.context.runtimeContext.isNotBlank()) appendLine(request.context.runtimeContext.trim())
            if (retrievalChanged && request.context.retrievalPrompt.isNotBlank()) appendLine(request.context.retrievalPrompt.trim())
        }.trim().take(1_600)

        val effectiveMessage = if (turnContext.isBlank()) {
            request.userMessage
        } else {
            buildString {
                appendLine("[PRIVATE RESPONSE CONTEXT]")
                appendLine("Background only; not a request to answer. Use only if relevant. The user's text after this block has highest priority.")
                appendLine(turnContext)
                appendLine("[END PRIVATE RESPONSE CONTEXT]")
                appendLine()
                append(request.userMessage)
            }
        }

        try {
            engine.sendUserPrompt(effectiveMessage, request.predictLength).collect { token ->
                val visible = privateContextFilter.accept(reasoningFilter.accept(token))
                if (visible.isNotEmpty()) {
                    emitted = true
                    emit(visible)
                }
            }
            val tail = privateContextFilter.accept(reasoningFilter.finish()) + privateContextFilter.finish()
            if (tail.isNotEmpty()) {
                emitted = true
                emit(tail)
            }
            loadedRetrievalFingerprint = request.context.retrievalFingerprint
            check(emitted) { "Runtime lokal berhenti tanpa menghasilkan token" }
        } finally {
            if (engine.state.value !is InferenceEngine.State.ModelReady || !emitted) {
                loadedSessionId = null
                loadedRetrievalFingerprint = null
            }
        }
    }.onCompletion { cause ->
        if (cause != null) {
            loadedSessionId = null
            loadedRetrievalFingerprint = null
        }
        if (cause == null && engine.state.value is InferenceEngine.State.Error) {
            throw IllegalStateException("Runtime lokal masuk ke status error setelah generasi")
        }
    }

    /**
     * Clear mutable USER/ASSISTANT chat state while retaining mapped model weights and the
     * already-prefilled SYSTEM prefix. A successful reset deliberately preserves the identity
     * fingerprint; session/retrieval fingerprints are invalidated so callers must rehydrate the
     * next session. Failure invalidates identity too and forces the existing full prompt fallback.
     */
    suspend fun resetConversationStateKeepingModel(): Boolean = loadMutex.withLock {
        if (loadedModelId == null || engine.state.value !is InferenceEngine.State.ModelReady) {
            loadedSessionId = null
            loadedIdentityFingerprint = null
            loadedRetrievalFingerprint = null
            return@withLock false
        }
        return@withLock try {
            engine.resetConversationKeepingSystemPrompt()
            loadedSessionId = null
            loadedRetrievalFingerprint = null
            true
        } catch (_: Throwable) {
            loadedSessionId = null
            loadedIdentityFingerprint = null
            loadedRetrievalFingerprint = null
            false
        }
    }

    override suspend fun unload() = withContext(Dispatchers.IO) {
        try {
            when (engine.state.value) {
                is InferenceEngine.State.ModelReady, is InferenceEngine.State.Error -> engine.cleanUp()
                else -> Unit
            }
        } finally {
            loadedModelId = null
            loadedSessionId = null
            loadedIdentityFingerprint = null
            loadedRetrievalFingerprint = null
        }
    }

    private suspend fun waitForInitialization() {
        when (engine.state.value) {
            is InferenceEngine.State.Uninitialized, is InferenceEngine.State.Initializing -> withTimeout(30_000L) {
                engine.state.first { it is InferenceEngine.State.Initialized || it is InferenceEngine.State.Error }
            }
            else -> Unit
        }
        if (engine.state.value is InferenceEngine.State.Error) unload()
    }

    private class ReasoningStreamFilter {
        private enum class Mode { UNDECIDED, THINKING, ANSWER }
        private var mode = Mode.UNDECIDED
        private val pending = StringBuilder()

        fun accept(chunk: String): String {
            if (chunk.isEmpty()) return ""
            pending.append(chunk)
            val output = StringBuilder()
            while (true) {
                when (mode) {
                    Mode.UNDECIDED -> {
                        val raw = pending.toString()
                        val leading = raw.indexOfFirst { !it.isWhitespace() }.let { if (it < 0) raw.length else it }
                        val candidate = raw.substring(leading)
                        when {
                            candidate.startsWith("<think>") -> {
                                pending.delete(0, leading + "<think>".length)
                                mode = Mode.THINKING
                            }
                            "<think>".startsWith(candidate) -> break
                            else -> mode = Mode.ANSWER
                        }
                        continue
                    }
                    Mode.THINKING -> {
                        val end = pending.indexOf("</think>")
                        if (end >= 0) {
                            pending.delete(0, end + "</think>".length)
                            while (pending.isNotEmpty() && pending.first().isWhitespace()) pending.deleteCharAt(0)
                            mode = Mode.ANSWER
                        } else {
                            if (pending.length > 16) pending.delete(0, pending.length - 16)
                            break
                        }
                    }
                    Mode.ANSWER -> {
                        output.append(pending)
                        pending.clear()
                        break
                    }
                }
            }
            return output.toString()
        }

        fun finish(): String = when (mode) {
            Mode.UNDECIDED, Mode.ANSWER -> pending.toString()
            Mode.THINKING -> ""
        }.also { pending.clear() }
    }

    private class PrivateContextStreamFilter {
        private var bracketOpen = false
        private var suppressPrivateBlock = false
        private val bracket = StringBuilder()

        fun accept(chunk: String): String {
            if (chunk.isEmpty()) return ""
            val output = StringBuilder()
            chunk.forEach { char ->
                if (!bracketOpen) {
                    if (char == '[') {
                        bracketOpen = true
                        bracket.append(char)
                    } else if (!suppressPrivateBlock) {
                        output.append(char)
                    }
                } else {
                    bracket.append(char)
                    if (char == ']' || bracket.length >= 160) {
                        val candidate = bracket.toString()
                        val privateMarker = candidate.contains("PRIVATE", ignoreCase = true) &&
                            (candidate.contains("CONTEXT", ignoreCase = true) ||
                                candidate.contains("CONTINUITY", ignoreCase = true) ||
                                candidate.contains("STATE", ignoreCase = true) ||
                                candidate.contains("PATTERN", ignoreCase = true))
                        val endMarker = privateMarker && candidate.contains("END", ignoreCase = true)
                        if (privateMarker) suppressPrivateBlock = !endMarker
                        else if (!suppressPrivateBlock) output.append(candidate)
                        bracket.clear()
                        bracketOpen = false
                    }
                }
            }
            return output.toString()
        }

        fun finish(): String {
            if (!bracketOpen) return ""
            val candidate = bracket.toString()
            bracket.clear()
            bracketOpen = false
            return if (suppressPrivateBlock || candidate.contains("PRIVATE", ignoreCase = true)) "" else candidate
        }
    }
}
