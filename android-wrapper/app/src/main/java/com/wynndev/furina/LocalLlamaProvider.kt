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

    private val engine: InferenceEngine = AiChat.getInferenceEngine(context.applicationContext)
    private val loadMutex = Mutex()

    @Volatile private var loadedModelId: String? = null
    @Volatile private var loadedSessionId: String? = null
    @Volatile private var loadedContextFingerprint: Int? = null

    override fun isWarm(model: ModelSpec, context: AiContext): Boolean =
        loadedModelId == model.id && engine.state.value is InferenceEngine.State.ModelReady

    override suspend fun prepare(model: ModelSpec, context: AiContext) = loadMutex.withLock {
        if (isWarm(model, context)) {
            if (loadedSessionId != context.sessionId || loadedContextFingerprint != context.fingerprint) {
                onState("prompting", model.id, 0.85)
                engine.setSystemPrompt(context.systemPrompt)
                loadedSessionId = context.sessionId
                loadedContextFingerprint = context.fingerprint
                onState("ready", model.id, 1.0)
            }
            return@withLock
        }

        if (engine.state.value is InferenceEngine.State.Generating) {
            withTimeout(15_000L) {
                engine.state.first { it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error }
            }
        }
        if (isWarm(model, context)) return@withLock

        onState("preparing", model.id, 0.0)
        withContext(Dispatchers.IO) {
            if (!modelDownloads.verify(model) { done, total ->
                    if (total > 0L) onState("verifying", model.id, done.toDouble() / total.toDouble())
                }) {
                throw IllegalStateException("Checksum model tidak cocok. Hapus lalu unduh ulang model.")
            }
        }

        waitForInitialization()
        if (engine.state.value is InferenceEngine.State.ModelReady || engine.state.value is InferenceEngine.State.Error) {
            unload()
        }

        val file = modelDownloads.modelFile(model)
        require(file.exists() && file.canRead()) { "File model tidak dapat dibaca: ${file.absolutePath}" }
        onState("loading", model.id, 0.15)
        engine.loadModel(file.absolutePath)
        onState("prompting", model.id, 0.85)
        engine.setSystemPrompt(context.systemPrompt)
        loadedModelId = model.id
        loadedSessionId = context.sessionId
        loadedContextFingerprint = context.fingerprint
        onState("ready", model.id, 1.0)
    }

    override fun stream(request: AiGenerationRequest): Flow<String> = flow {
        check(isWarm(request.model, request.context)) { "Provider lokal belum siap untuk konteks ini" }
        var emitted = false
        engine.sendUserPrompt(request.userMessage, request.predictLength).collect { token ->
            if (token.isNotEmpty()) {
                emitted = true
                emit(token)
            }
        }
        check(emitted) { "Runtime lokal berhenti tanpa menghasilkan token" }
    }.onCompletion { cause ->
        if (cause == null && engine.state.value is InferenceEngine.State.Error) {
            throw IllegalStateException("Runtime lokal masuk ke status error setelah generasi")
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
            loadedContextFingerprint = null
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
}
