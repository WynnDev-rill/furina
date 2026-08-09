package com.wynndev.furina

import android.net.Uri
import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject

class FurinaBridge(
    private val activity: MainActivity,
    private val webView: WebView,
    private val store: MemoryStore,
    private val modelDownloads: ModelDownloadManager,
    private val backupManager: BackupManager,
) {
    companion object {
        @Volatile private var processLoadedModelId: String? = null
        @Volatile private var processLoadedSessionId: String? = null
        @Volatile private var processLoadedPersonaHash: Int? = null
        @Volatile private var processSessionBootstrapped = false
    }

    private val scope = kotlinx.coroutines.CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val prefs = activity.getSharedPreferences("furina_native", 0)
    private val engine: InferenceEngine = AiChat.getInferenceEngine(activity.applicationContext)
    private val loadMutex = Mutex()
    private var generationJob: Job? = null
    private var prepareJob: Job? = null
    private val verificationJobs = mutableMapOf<String, Job>()
    private val verificationProgress = mutableMapOf<String, Double>()

    @JavascriptInterface
    fun nativeInfo(): String = JSONObject()
        .put("available", true)
        .put("version", "4.0")
        .put("selectedModelId", selectedModelId())
        .put("runtime", "llama.cpp Android native")
        .put("contextStrategy", "4K active + long-term retrieval")
        .toString()

    @JavascriptInterface
    fun modelCatalog(): String {
        val arr = JSONArray()
        ModelCatalog.models.forEach { spec ->
            arr.put(JSONObject()
                .put("id", spec.id).put("name", spec.displayName).put("subtitle", spec.subtitle)
                .put("expectedBytes", spec.expectedBytes).put("recommended", spec.recommended))
        }
        return arr.toString()
    }

    @JavascriptInterface
    fun modelStatus(modelId: String): String {
        val spec = ModelCatalog.byId(modelId) ?: return JSONObject().put("state", "unknown").toString()
        val status = modelDownloads.status(spec)
        if (status.optString("state") == "ready" && !status.optBoolean("verified")) beginVerification(spec)
        synchronized(verificationJobs) {
            if (verificationJobs[spec.id]?.isActive == true) {
                status.put("state", "verifying").put("progress", verificationProgress[spec.id] ?: 0.0)
            }
        }
        return status.put("selected", selectedModelId() == spec.id).toString()
    }

    @JavascriptInterface
    fun startModelDownload(modelId: String): String {
        val spec = ModelCatalog.byId(modelId) ?: throw IllegalArgumentException("Model tidak dikenal")
        activity.runOnUiThread { activity.requestDownloadNotificationPermission() }
        return modelDownloads.start(spec).put("selected", selectedModelId() == spec.id).toString()
    }

    @JavascriptInterface
    fun cancelModelDownload(modelId: String): String {
        val spec = ModelCatalog.byId(modelId) ?: throw IllegalArgumentException("Model tidak dikenal")
        return modelDownloads.cancel(spec).toString()
    }

    @JavascriptInterface
    fun deleteModel(modelId: String) {
        val spec = ModelCatalog.byId(modelId) ?: return
        scope.launch {
            try {
                synchronized(verificationJobs) { verificationJobs.remove(modelId)?.cancel(); verificationProgress.remove(modelId) }
                if (processLoadedModelId == modelId) unloadEngine()
                modelDownloads.delete(spec)
                emitState("model_deleted", modelId, 0.0)
            } catch (e: Throwable) { emitError("model-delete", e.message ?: "Gagal menghapus model") }
        }
    }

    @JavascriptInterface
    fun selectModel(modelId: String): String {
        require(ModelCatalog.byId(modelId) != null) { "Model tidak dikenal" }
        prefs.edit().putString("selected_model", modelId).apply()
        return modelId
    }

    @JavascriptInterface
    fun createSession(): String {
        val id = store.createSession()
        return JSONObject().put("id", id).put("title", "Percakapan baru").put("createdAt", System.currentTimeMillis()).toString()
    }

    @JavascriptInterface
    fun listSessions(): String = store.sessionsJson()

    @JavascriptInterface
    fun loadSession(sessionId: String): String = store.loadSessionJson(sessionId)

    @JavascriptInterface
    fun deleteSession(sessionId: String) {
        store.deleteSession(sessionId)
        if (processLoadedSessionId == sessionId) {
            processLoadedSessionId = null
            processSessionBootstrapped = false
        }
    }

    @JavascriptInterface
    fun clearSession(sessionId: String) {
        store.clearSession(sessionId)
        if (processLoadedSessionId == sessionId) processSessionBootstrapped = false
    }

    @JavascriptInterface
    fun memoryStats(): String = store.statsJson()

    @JavascriptInterface
    fun listMemories(): String = store.memoriesJson()

    @JavascriptInterface
    fun addMemory(content: String): String = store.addMemory(content)

    @JavascriptInterface
    fun deleteMemory(memoryId: String) = store.deleteMemory(memoryId)

    @JavascriptInterface
    fun clearMemories() = store.clearMemories()

    @JavascriptInterface
    fun appSettings(): String = store.appSettingsJson()

    @JavascriptInterface
    fun saveAppSettings(settingsJson: String) = store.saveAppSettingsJson(settingsJson)

    @JavascriptInterface
    fun setSystemTheme(dark: Boolean) {
        activity.runOnUiThread { activity.applySystemTheme(dark) }
    }

    @JavascriptInterface
    fun prepareModel(sessionId: String, persona: String) {
        if (sessionId.isBlank() || generationJob?.isActive == true || prepareJob?.isActive == true) return
        prepareJob = scope.launch {
            try {
                val model = ModelCatalog.byId(selectedModelId()) ?: return@launch
                if (modelDownloads.status(model).optString("state") != "ready") return@launch
                ensureModelLoaded(model, sessionId, persona)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                emitState("error", selectedModelId(), 0.0)
                emitError("model-prepare", friendlyEngineError(e))
            } finally {
                prepareJob = null
            }
        }
    }

    @JavascriptInterface
    fun generate(requestId: String, sessionId: String, userText: String, persona: String) {
        val clean = userText.trim()
        if (clean.isEmpty()) return
        if (generationJob?.isActive == true) {
            emitError(requestId, "Furina masih menyelesaikan jawaban sebelumnya")
            return
        }

        generationJob = scope.launch {
            val reply = StringBuilder()
            var userId = ""
            val startedAt = android.os.SystemClock.elapsedRealtime()
            var firstTokenAt = 0L
            var tokenCount = 0
            var warmStart = false
            try {
                val model = ModelCatalog.byId(selectedModelId()) ?: error("Model AI tidak dikenal")
                val modelState = modelDownloads.status(model).optString("state")
                if (modelState != "ready") error("Unduh ${model.displayName} terlebih dahulu")

                val bootstrapContext = store.buildBootstrapContext(clean, sessionId)
                warmStart = processLoadedModelId == model.id && processLoadedSessionId == sessionId &&
                    processLoadedPersonaHash == persona.hashCode() && engine.state.value is InferenceEngine.State.ModelReady
                ensureModelLoaded(model, sessionId, persona)
                userId = store.addMessage(sessionId, "user", clean)
                emitState("thinking", model.id, 0.0)

                val prompt = if (!processSessionBootstrapped) {
                    buildString {
                        appendLine("[INTERNAL LONG-TERM CONTEXT]")
                        appendLine("Use this only to preserve continuity. Do not announce that you retrieved memory.")
                        if (bootstrapContext.isNotBlank()) appendLine(bootstrapContext)
                        appendLine("[END INTERNAL CONTEXT]")
                        appendLine()
                        append(clean)
                    }
                } else clean

                val pending = StringBuilder()
                var lastDispatch = android.os.SystemClock.elapsedRealtime()
                engine.sendUserPrompt(prompt, predictLength = 384).collect { token ->
                    if (firstTokenAt == 0L) firstTokenAt = android.os.SystemClock.elapsedRealtime()
                    tokenCount += 1
                    reply.append(token)
                    pending.append(token)
                    val now = android.os.SystemClock.elapsedRealtime()
                    if (pending.length >= 24 || now - lastDispatch >= 45L) {
                        dispatchToken(requestId, pending.toString())
                        pending.clear()
                        lastDispatch = now
                    }
                }
                if (pending.isNotEmpty()) dispatchToken(requestId, pending.toString())
                val finalText = reply.toString().trim()
                if (finalText.isBlank()) error("Model tidak menghasilkan jawaban")
                val assistantId = store.addMessage(sessionId, "assistant", finalText)
                processSessionBootstrapped = true
                emitDone(requestId, userId, assistantId, generationMetrics(startedAt, firstTokenAt, tokenCount, warmStart))
                emitState("ready", model.id, 1.0)
                withContext(Dispatchers.IO) {
                    try { backupManager.autoBackupIfDue() } catch (_: Throwable) {}
                }
            } catch (e: CancellationException) {
                val partial = reply.toString().trim()
                if (partial.isNotBlank() && userId.isNotBlank()) {
                    val assistantId = store.addMessage(sessionId, "assistant", partial)
                    emitDone(requestId, userId, assistantId, generationMetrics(startedAt, firstTokenAt, tokenCount, warmStart))
                } else {
                    emitError(requestId, "Respons dihentikan")
                }
                emitState("cancelled", selectedModelId(), 0.0)
            } catch (e: Throwable) {
                emitState("error", selectedModelId(), 0.0)
                emitError(requestId, friendlyEngineError(e))
            } finally {
                generationJob = null
            }
        }
    }

    @JavascriptInterface
    fun stopGeneration() {
        generationJob?.cancel()
        generationJob = null
    }

    @JavascriptInterface
    fun backupInfo(): String = backupManager.infoJson()

    @JavascriptInterface
    fun chooseBackupFolder() {
        activity.runOnUiThread { activity.launchBackupFolderPicker() }
    }

    @JavascriptInterface
    fun backupNow() {
        scope.launch(Dispatchers.IO) {
            try {
                val name = backupManager.backupNow()
                emitBackup(true, "Backup tersimpan: $name")
            } catch (e: Throwable) { emitBackup(false, e.message ?: "Backup gagal") }
        }
    }

    @JavascriptInterface
    fun chooseRestoreFile() {
        activity.runOnUiThread { activity.launchRestorePicker() }
    }

    @JavascriptInterface
    fun setRecoveryKey(key: String) {
        try {
            backupManager.setRecoveryKey(key)
            emitBackup(true, "Recovery key diperbarui")
        } catch (e: Throwable) { emitBackup(false, e.message ?: "Recovery key tidak valid") }
    }

    fun onBackupFolderSelected(uri: Uri) {
        backupManager.setBackupFolder(uri)
        emitBackup(true, "Folder backup dipilih. Folder Google Drive juga didukung melalui pemilih file Android.")
    }

    fun onRestoreFileSelected(uri: Uri) {
        scope.launch(Dispatchers.IO) {
            try {
                generationJob?.cancel()
                unloadEngine()
                backupManager.restoreFrom(uri)
                emitBackup(true, "Restore selesai. Memori Furina sudah dipulihkan.")
                eval("window.__furinaNativeRestored && window.__furinaNativeRestored()")
            } catch (e: Throwable) { emitBackup(false, e.message ?: "Restore gagal") }
        }
    }

    fun notifyNativeReady() {
        eval("window.__furinaNativeReady && window.__furinaNativeReady()")
    }

    fun destroy() {
        generationJob?.cancel()
        prepareJob?.cancel()
        // AiChat owns a process-wide singleton that cannot be recreated after destroy().
        // Keep it warm across Activity recreation; Android frees native memory with the process.
        scope.cancel()
        store.close()
    }

    private fun selectedModelId(): String = prefs.getString("selected_model", ModelCatalog.models.first().id)
        ?: ModelCatalog.models.first().id

    private fun beginVerification(spec: ModelSpec) {
        synchronized(verificationJobs) {
            if (verificationJobs[spec.id]?.isActive == true) return
            verificationProgress[spec.id] = 0.0
            verificationJobs[spec.id] = scope.launch(Dispatchers.IO) {
                try {
                    val ok = modelDownloads.verify(spec) { done, total ->
                        val progress = if (total > 0L) done.toDouble() / total.toDouble() else 0.0
                        synchronized(verificationJobs) { verificationProgress[spec.id] = progress }
                        emitState("verifying", spec.id, progress)
                    }
                    if (ok) emitState("model_verified", spec.id, 1.0)
                    else emitError("model-verify", "File ${spec.displayName} rusak. Hapus lalu unduh ulang.")
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    emitError("model-verify", e.message ?: "Verifikasi model gagal")
                } finally {
                    synchronized(verificationJobs) {
                        verificationJobs.remove(spec.id)
                        verificationProgress.remove(spec.id)
                    }
                }
            }
        }
    }

    private suspend fun ensureModelLoaded(spec: ModelSpec, sessionId: String, persona: String) = loadMutex.withLock {
        val personaHash = persona.hashCode()
        if (processLoadedModelId == spec.id && processLoadedSessionId == sessionId && processLoadedPersonaHash == personaHash &&
            engine.state.value is InferenceEngine.State.ModelReady) return@withLock

        if (engine.state.value is InferenceEngine.State.Generating) {
            withTimeout(10_000L) {
                engine.state.first { it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error }
            }
        }
        if (processLoadedModelId == spec.id && processLoadedSessionId == sessionId && processLoadedPersonaHash == personaHash &&
            engine.state.value is InferenceEngine.State.ModelReady) return@withLock

        emitState("preparing", spec.id, 0.0)
        withContext(Dispatchers.IO) {
            if (!modelDownloads.verify(spec) { done, total ->
                    if (total > 0L) emitState("verifying", spec.id, done.toDouble() / total.toDouble())
                }) {
                throw IllegalStateException("Checksum model tidak cocok. Hapus lalu unduh ulang model.")
            }
        }

        waitForEngineInitialization()
        val state = engine.state.value
        if (state is InferenceEngine.State.ModelReady || state is InferenceEngine.State.Error) unloadEngine()

        emitState("loading", spec.id, 0.0)
        engine.loadModel(modelDownloads.modelFile(spec).absolutePath)
        emitState("prompting", spec.id, 0.85)
        engine.setSystemPrompt(buildSystemPrompt(persona))
        processLoadedModelId = spec.id
        processLoadedSessionId = sessionId
        processLoadedPersonaHash = personaHash
        processSessionBootstrapped = false
        emitState("ready", spec.id, 1.0)
    }

    private suspend fun waitForEngineInitialization() {
        when (engine.state.value) {
            is InferenceEngine.State.Uninitialized, is InferenceEngine.State.Initializing -> {
                withTimeout(30_000L) {
                    engine.state.first { it is InferenceEngine.State.Initialized || it is InferenceEngine.State.Error }
                }
            }
            else -> Unit
        }
        if (engine.state.value is InferenceEngine.State.Error) unloadEngine()
    }

    private suspend fun unloadEngine() = withContext(Dispatchers.IO) {
        try {
            when (engine.state.value) {
                is InferenceEngine.State.ModelReady, is InferenceEngine.State.Error -> engine.cleanUp()
                is InferenceEngine.State.Generating -> {
                    generationJob?.cancel()
                    engine.state.first { it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error }
                    engine.cleanUp()
                }
                else -> Unit
            }
        } finally {
            processLoadedModelId = null
            processLoadedSessionId = null
            processLoadedPersonaHash = null
            processSessionBootstrapped = false
        }
    }

    private fun buildSystemPrompt(customPersona: String): String {
        val custom = customPersona.trim()
        return """
            You are Furina, a long-term personal AI companion living on the user's device.
            Speak naturally, with continuity and a distinct personality. Do not sound like customer support.
            You may disagree, tease lightly, be skeptical, have preferences, and point out bad reasoning when appropriate.
            Do not automatically validate the user, force positivity, or add generic moral lectures to benign conversations.
            Treat supplied long-term context as private memory. Use it when relevant, but never dump or recite it mechanically.
            New conversation sessions are only visual groupings; your relationship and memories continue across sessions.
            Match the user's language unless they request another language. Prefer concise natural replies unless depth is useful.
            Never claim an event happened if it is not supported by the current conversation or supplied memory.
            ${if (custom.isNotBlank()) "\nUser-defined persona instructions:\n$custom" else ""}
        """.trimIndent()
    }

    private fun friendlyEngineError(error: Throwable): String {
        val raw = error.message.orEmpty()
        return when {
            error is kotlinx.coroutines.TimeoutCancellationException -> "Mesin AI terlalu lama disiapkan. Tutup aplikasi lain lalu coba lagi."
            raw.contains("memory", ignoreCase = true) || raw.contains("allocate", ignoreCase = true) ->
                "RAM tidak cukup untuk model ini. Tutup aplikasi lain atau gunakan model 4B."
            raw.contains("UnsupportedArchitecture", ignoreCase = true) ->
                "Format model belum didukung oleh runtime ini."
            raw.isNotBlank() -> "Mesin AI gagal: $raw"
            else -> "Mesin AI gagal merespons. Coba lagi atau muat ulang model."
        }
    }

    private fun dispatchToken(requestId: String, chunk: String) {
        eval("window.__furinaNativeToken && window.__furinaNativeToken(${JSONObject.quote(requestId)}, ${JSONObject.quote(chunk)})")
    }

    private fun generationMetrics(startedAt: Long, firstTokenAt: Long, tokenCount: Int, warmStart: Boolean): JSONObject {
        val finishedAt = android.os.SystemClock.elapsedRealtime()
        val firstTokenMs = if (firstTokenAt > 0L) firstTokenAt - startedAt else finishedAt - startedAt
        val decodeMs = if (firstTokenAt > 0L) (finishedAt - firstTokenAt).coerceAtLeast(1L) else 1L
        return JSONObject()
            .put("firstTokenMs", firstTokenMs)
            .put("tokensPerSecond", tokenCount * 1000.0 / decodeMs)
            .put("tokenCount", tokenCount)
            .put("warmStart", warmStart)
    }

    private fun emitDone(requestId: String, userId: String, assistantId: String, metrics: JSONObject) {
        eval("window.__furinaNativeDone && window.__furinaNativeDone(${JSONObject.quote(requestId)}, ${JSONObject.quote(userId)}, ${JSONObject.quote(assistantId)}, $metrics)")
    }

    private fun emitError(requestId: String, message: String) {
        eval("window.__furinaNativeError && window.__furinaNativeError(${JSONObject.quote(requestId)}, ${JSONObject.quote(message)})")
    }

    private fun emitState(state: String, modelId: String, progress: Double) {
        eval("window.__furinaNativeState && window.__furinaNativeState(${JSONObject.quote(state)}, ${JSONObject.quote(modelId)}, $progress)")
    }

    private fun emitBackup(success: Boolean, message: String) {
        eval("window.__furinaNativeBackup && window.__furinaNativeBackup($success, ${JSONObject.quote(message)})")
    }

    private fun eval(script: String) {
        webView.post { if (!webView.isDestroyed) webView.evaluateJavascript(script, null) }
    }
}
