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
    private val scope = kotlinx.coroutines.CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val prefs = activity.getSharedPreferences("furina_native", 0)
    private val engine: InferenceEngine = AiChat.getInferenceEngine(activity.applicationContext)
    private val loadMutex = Mutex()
    private var generationJob: Job? = null
    private var loadedModelId: String? = null
    private var loadedSessionId: String? = null
    private var loadedPersonaHash: Int? = null
    private var sessionBootstrapped = false
    private val verificationJobs = mutableMapOf<String, Job>()
    private val verificationProgress = mutableMapOf<String, Double>()

    @JavascriptInterface
    fun nativeInfo(): String = JSONObject()
        .put("available", true)
        .put("version", "4.0")
        .put("selectedModelId", selectedModelId())
        .put("runtime", "llama.cpp Android native")
        .put("contextStrategy", "8K active + long-term retrieval")
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
                if (loadedModelId == modelId) unloadEngine()
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
        if (loadedSessionId == sessionId) {
            loadedSessionId = null
            sessionBootstrapped = false
        }
    }

    @JavascriptInterface
    fun memoryStats(): String = store.statsJson()

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
            try {
                val model = ModelCatalog.byId(selectedModelId()) ?: error("Model AI tidak dikenal")
                val modelState = modelDownloads.status(model).optString("state")
                if (modelState != "ready") error("Unduh ${model.displayName} terlebih dahulu")

                val bootstrapContext = store.buildBootstrapContext(clean, sessionId)
                ensureModelLoaded(model, sessionId, persona)
                userId = store.addMessage(sessionId, "user", clean)
                emitState("thinking", model.id, 0.0)

                val prompt = if (!sessionBootstrapped) {
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
                engine.sendUserPrompt(prompt, predictLength = 768).collect { token ->
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
                sessionBootstrapped = true
                emitDone(requestId, userId, assistantId)
                withContext(Dispatchers.IO) {
                    try { backupManager.autoBackupIfDue() } catch (_: Throwable) {}
                }
            } catch (e: CancellationException) {
                val partial = reply.toString().trim()
                if (partial.isNotBlank() && userId.isNotBlank()) {
                    val assistantId = store.addMessage(sessionId, "assistant", partial)
                    emitDone(requestId, userId, assistantId)
                } else {
                    emitError(requestId, "Respons dihentikan")
                }
                emitState("cancelled", selectedModelId(), 0.0)
            } catch (e: Throwable) {
                emitError(requestId, e.message ?: "Inference gagal")
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
        scope.launch { try { engine.destroy() } catch (_: Throwable) {} }
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
        if (loadedModelId == spec.id && loadedSessionId == sessionId && loadedPersonaHash == personaHash &&
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
        engine.setSystemPrompt(buildSystemPrompt(persona))
        loadedModelId = spec.id
        loadedSessionId = sessionId
        loadedPersonaHash = personaHash
        sessionBootstrapped = false
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
            loadedModelId = null
            loadedSessionId = null
            loadedPersonaHash = null
            sessionBootstrapped = false
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

    private fun dispatchToken(requestId: String, chunk: String) {
        eval("window.__furinaNativeToken && window.__furinaNativeToken(${JSONObject.quote(requestId)}, ${JSONObject.quote(chunk)})")
    }

    private fun emitDone(requestId: String, userId: String, assistantId: String) {
        eval("window.__furinaNativeDone && window.__furinaNativeDone(${JSONObject.quote(requestId)}, ${JSONObject.quote(userId)}, ${JSONObject.quote(assistantId)})")
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
