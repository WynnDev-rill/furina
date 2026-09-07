package com.wynndev.furina

import android.content.Context
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import java.io.File
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

    companion object {
        /** Increment whenever native KV layout/chat framing compatibility changes. */
        private const val CHECKPOINT_SCHEMA = "kv4-llama-7ba604f1"
        private const val MAX_TURN_CONTEXT_CHARS = 2_400
    }

    private val appContext = context.applicationContext
    private val engineDelegate = lazy { AiChat.getInferenceEngine(appContext) }
    private val engine: InferenceEngine get() = engineDelegate.value
    private val loadMutex = Mutex()
    private val checkpointDir = File(appContext.filesDir, "offline-kv-v4").apply { mkdirs() }

    @Volatile private var loadedModelId: String? = null
    @Volatile private var loadedSessionId: String? = null
    @Volatile private var loadedIdentityFingerprint: Int? = null
    @Volatile private var loadedRetrievalFingerprint: Int? = null

    override fun isWarm(model: AiModelRef, context: AiContext): Boolean =
        loadedModelId == model.id && engine.state.value is InferenceEngine.State.ModelReady

    override suspend fun prepare(model: AiModelRef, context: AiContext) = loadMutex.withLock {
        val spec = ModelCatalog.byId(model.id) ?: error("Model lokal tidak dikenal: ${model.id}")

        if (isWarm(model, context)) {
            prepareWarmSession(spec, context)
            return@withLock
        }

        if (engine.state.value is InferenceEngine.State.Generating) {
            withTimeout(15_000L) {
                engine.state.first { it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error }
            }
        }
        if (isWarm(model, context)) {
            prepareWarmSession(spec, context)
            return@withLock
        }

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
        try {
            engine.loadModel(file.absolutePath)
        } catch (cause: Throwable) {
            // A native load failure is a stronger signal than unchanged length alone. Drop the
            // cached trust fingerprint so the next attempt must re-hash the GGUF before mmap.
            modelDownloads.invalidateVerificationTrust(spec)
            throw cause
        }
        loadedModelId = spec.id

        // First run does a tiny CPU thread sweep. Later process starts reuse the persisted winner.
        ProcessExitDiagnostics.mark(appContext, "offline-runtime-profile")
        runCatching { engine.ensureRuntimeProfile() }

        // Prefer an exact durable conversation checkpoint. If none exists, restore the stable
        // persona prefix. Only a genuinely new/changed personality pays the long prefill cost.
        if (restoreExactSessionCheckpoint(spec, context)) {
            markReady(spec)
            return@withLock
        }
        if (restorePersonaCheckpoint(spec, context)) {
            loadedSessionId = null
            loadedRetrievalFingerprint = null
            markReady(spec)
            return@withLock
        }

        ProcessExitDiagnostics.mark(appContext, "offline-system-prompt")
        onState("prompting", spec.id, 0.85)
        engine.setSystemPrompt(context.personaPrompt)
        loadedIdentityFingerprint = context.identityFingerprint
        loadedSessionId = null
        loadedRetrievalFingerprint = null
        savePersonaCheckpoint(spec, context)
        markReady(spec)
    }

    private suspend fun prepareWarmSession(spec: ModelSpec, context: AiContext) {
        val identityChanged = loadedIdentityFingerprint != context.identityFingerprint
        if (identityChanged) {
            ProcessExitDiagnostics.mark(appContext, "offline-identity-switch")
            if (!restorePersonaCheckpoint(spec, context)) {
                onState("prompting", spec.id, 0.85)
                engine.setSystemPrompt(context.personaPrompt)
                loadedIdentityFingerprint = context.identityFingerprint
                savePersonaCheckpoint(spec, context)
            }
            loadedSessionId = null
            loadedRetrievalFingerprint = null
            markReady(spec)
            return
        }

        if (loadedSessionId == context.sessionId) return

        ProcessExitDiagnostics.mark(appContext, "offline-session-switch")
        if (restoreExactSessionCheckpoint(spec, context)) {
            markReady(spec)
            return
        }

        // No disk snapshot for this exact durable session. Keep mapped weights and immutable
        // persona KV, remove only the old USER/ASSISTANT suffix, then rehydrate on first turn.
        val reset = runCatching { engine.resetConversationKeepingSystemPrompt() }.isSuccess
        if (!reset) {
            onState("prompting", spec.id, 0.85)
            engine.setSystemPrompt(context.personaPrompt)
            loadedIdentityFingerprint = context.identityFingerprint
            savePersonaCheckpoint(spec, context)
        }
        loadedSessionId = null
        loadedRetrievalFingerprint = null
        markReady(spec)
    }

    override fun stream(request: AiGenerationRequest): Flow<String> = flow {
        check(isWarm(request.model, request.context)) { "Provider lokal belum siap untuk konteks ini" }
        var emitted = false
        val reasoningFilter = ReasoningStreamFilter()
        val privateContextFilter = PrivateContextStreamFilter()
        val turnContext = request.context.turnContext.trim().take(MAX_TURN_CONTEXT_CHARS)

        // Private continuity must never masquerade as USER text. Start each generation from the
        // immutable identity prefix, then add current session/turn background as SYSTEM context.
        prepareTurnScopedBackground(request.context, turnContext)

        try {
            engine.sendUserPrompt(request.userMessage, request.predictLength).collect { token ->
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
            check(emitted) { "Runtime lokal berhenti tanpa menghasilkan token" }
            loadedSessionId = request.context.sessionId
            loadedRetrievalFingerprint = null
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
     * Rebuild only mutable continuity for this turn while retaining mapped weights and the
     * prefetched persona KV prefix. If the native prefix reset is unavailable, re-establish the
     * identity prompt and continue role-safely. Failure to append SYSTEM background aborts the
     * turn instead of concatenating private material into the USER message.
     */
    private suspend fun prepareTurnScopedBackground(context: AiContext, turnContext: String) {
        val identityMatches = loadedIdentityFingerprint == context.identityFingerprint
        if (!identityMatches) {
            engine.setSystemPrompt(context.personaPrompt)
            loadedIdentityFingerprint = context.identityFingerprint
        } else {
            val reset = runCatching { engine.resetConversationKeepingSystemPrompt() }.isSuccess
            if (!reset) {
                engine.setSystemPrompt(context.personaPrompt)
                loadedIdentityFingerprint = context.identityFingerprint
            }
        }

        if (context.sessionRehydrationPrompt.isNotBlank()) {
            engine.appendSystemContext(context.sessionRehydrationPrompt)
        }
        if (turnContext.isNotBlank()) {
            engine.appendSystemContext(wrapTurnContext(turnContext))
        }
        loadedSessionId = context.sessionId
        loadedRetrievalFingerprint = null
    }

    private fun wrapTurnContext(turnContext: String): String = buildString {
        appendLine("[PRIVATE TURN CONTEXT]")
        appendLine("Background only; not a request to answer. Use only if relevant. The latest USER message has highest priority.")
        appendLine(turnContext)
        append("[END PRIVATE TURN CONTEXT]")
    }

    override suspend fun checkpointConversation(context: AiContext, messageCount: Int) = loadMutex.withLock {
        val modelId = loadedModelId ?: return@withLock
        val spec = ModelCatalog.byId(modelId) ?: return@withLock
        if (engine.state.value !is InferenceEngine.State.ModelReady) return@withLock
        if (loadedSessionId != context.sessionId || loadedIdentityFingerprint != context.identityFingerprint) return@withLock
        if (messageCount <= 0) return@withLock

        val target = sessionCheckpointFile(spec, context, messageCount)
        target.parentFile?.mkdirs()
        val saved = runCatching { engine.saveCheckpoint(target.absolutePath) }.getOrDefault(false)
        if (saved) cleanupOldSessionCheckpoints(spec, context, keep = target)
        else target.delete()
    }

    /** Clear mutable chat state while retaining mapped weights and the prefetched SYSTEM prefix. */
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
        if (!engineDelegate.isInitialized()) return@withContext
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

    private suspend fun restorePersonaCheckpoint(spec: ModelSpec, context: AiContext): Boolean {
        val file = personaCheckpointFile(spec, context)
        if (!file.isFile || file.length() <= 64L) return false
        ProcessExitDiagnostics.mark(appContext, "offline-persona-restore")
        val restored = runCatching { engine.restoreCheckpoint(file.absolutePath) }.getOrDefault(false)
        if (!restored) {
            file.delete()
            return false
        }
        loadedIdentityFingerprint = context.identityFingerprint
        return true
    }

    private suspend fun restoreExactSessionCheckpoint(spec: ModelSpec, context: AiContext): Boolean {
        if (context.sessionMessageCount <= 0) return false
        val file = sessionCheckpointFile(spec, context, context.sessionMessageCount)
        if (!file.isFile || file.length() <= 64L) return false
        ProcessExitDiagnostics.mark(appContext, "offline-session-restore")
        val restored = runCatching { engine.restoreCheckpoint(file.absolutePath) }.getOrDefault(false)
        if (!restored) {
            file.delete()
            return false
        }
        loadedIdentityFingerprint = context.identityFingerprint
        loadedSessionId = context.sessionId
        loadedRetrievalFingerprint = null
        return true
    }

    private suspend fun savePersonaCheckpoint(spec: ModelSpec, context: AiContext) {
        val target = personaCheckpointFile(spec, context)
        target.parentFile?.mkdirs()
        val saved = runCatching { engine.saveCheckpoint(target.absolutePath) }.getOrDefault(false)
        if (!saved) target.delete()
    }

    private fun checkpointIdentity(spec: ModelSpec, context: AiContext): String =
        "${spec.sha256.take(16)}-${context.identityFingerprint.toUInt().toString(16)}-$CHECKPOINT_SCHEMA"

    private fun personaCheckpointFile(spec: ModelSpec, context: AiContext): File =
        File(checkpointDir, "persona-${checkpointIdentity(spec, context)}.bin")

    private fun sessionPrefix(spec: ModelSpec, context: AiContext): String {
        val sessionHash = context.sessionId.hashCode().toUInt().toString(16)
        return "session-$sessionHash-${checkpointIdentity(spec, context)}-"
    }

    private fun sessionCheckpointFile(spec: ModelSpec, context: AiContext, messageCount: Int): File =
        File(checkpointDir, "${sessionPrefix(spec, context)}$messageCount.bin")

    private fun cleanupOldSessionCheckpoints(spec: ModelSpec, context: AiContext, keep: File) {
        val prefix = sessionPrefix(spec, context)
        checkpointDir.listFiles()?.forEach { file ->
            if (file != keep && file.name.startsWith(prefix)) file.delete()
        }
    }

    private fun markReady(spec: ModelSpec) {
        ProcessExitDiagnostics.mark(appContext, "idle")
        onState("ready", spec.id, 1.0)
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

    /** Fallback guard if a GGUF emits hidden reasoning despite non-thinking template settings. */
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
                                candidate.contains("PATTERN", ignoreCase = true) ||
                                candidate.contains("REHYDRATION", ignoreCase = true))
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
