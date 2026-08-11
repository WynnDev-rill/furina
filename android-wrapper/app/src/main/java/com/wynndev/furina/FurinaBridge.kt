package com.wynndev.furina

import android.net.Uri
import android.webkit.JavascriptInterface
import android.webkit.WebView
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.joinAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
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
    private val contextEngine = ContextEngine(activity.applicationContext, store)
    private val localProvider = LocalLlamaProvider(activity.applicationContext, modelDownloads, ::emitState)
    private val aiRuntime = AiRuntimeController(activity.applicationContext)
    private val providers: Map<String, AiProvider> = buildMap {
        put(localProvider.id, localProvider)
        putAll(aiRuntime.onlineProviders)
    }
    private val aiEngine = UnifiedAiEngine(store, contextEngine, providers)

    /** Native llama.cpp lifecycle is single-owner even when WebView actions arrive quickly. */
    private val aiOperationMutex = Mutex()
    private val jobLock = Any()
    private val pendingMutations = AtomicInteger(0)
    private var generationJob: Job? = null
    private var prepareJob: Job? = null
    private val verificationJobs = mutableMapOf<String, Job>()
    private val verificationProgress = mutableMapOf<String, Double>()

    @JavascriptInterface
    fun nativeInfo(): String {
        val runtime = aiRuntime.modeSummaryJson()
        return JSONObject()
            .put("available", true)
            .put("version", "4.3")
            .put("selectedModelId", selectedModelId())
            .put("runtime", if (runtime.optString("mode") == OnlineAiConfigStore.MODE_ONLINE) "Online API" else "llama.cpp Android native")
            .put("aiEngine", "unified-provider-v3")
            .put("provider", runtime.optString("provider"))
            .put("providerName", runtime.optString("providerName"))
            .put("aiMode", runtime.optString("mode"))
            .put("onlineReady", runtime.optBoolean("onlineReady"))
            .put("autoFallback", runtime.optBoolean("autoFallback"))
            .put("contextStrategy", "layered identity + role-safe retrieval + idle consolidation")
            .put("offline", runtime.optString("mode") != OnlineAiConfigStore.MODE_ONLINE)
            .toString()
    }

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
        launchAiMutation("model-delete") {
            synchronized(verificationJobs) {
                verificationJobs.remove(modelId)?.cancel()
                verificationProgress.remove(modelId)
            }
            aiEngine.unload()
            modelDownloads.delete(spec)
            emitState("model_deleted", modelId, 0.0)
        }
    }

    @JavascriptInterface
    fun selectModel(modelId: String): String {
        require(ModelCatalog.byId(modelId) != null) { "Model tidak dikenal" }
        prefs.edit().putString("selected_model", modelId).apply()
        return modelId
    }

    @JavascriptInterface
    fun onlineAiSettings(): String = aiRuntime.settingsJson()

    @JavascriptInterface
    fun setAiMode(mode: String) {
        aiRuntime.setMode(mode)
        launchAiMutation("mode-switch") { aiEngine.unload() }
        emitOnlineAi("settings", aiRuntime.config.selectedProvider(), true, "Mode AI diperbarui")
    }

    @JavascriptInterface
    fun setOnlineProvider(providerId: String) {
        aiRuntime.setProvider(providerId)
        launchAiMutation("provider-switch") { aiEngine.unload() }
        emitOnlineAi("settings", providerId, true, "Provider dipilih")
    }

    @JavascriptInterface
    fun setOnlineModel(providerId: String, modelId: String) {
        aiRuntime.setModel(providerId, modelId)
        emitOnlineAi("settings", providerId, true, "Model utama diperbarui")
    }

    @JavascriptInterface
    fun setOnlineAutoFallback(enabled: Boolean) {
        aiRuntime.setAutoFallback(enabled)
        emitOnlineAi("settings", aiRuntime.config.selectedProvider(), true, if (enabled) "Fallback otomatis aktif" else "Fallback otomatis nonaktif")
    }

    @JavascriptInterface
    fun saveOnlineApiKey(providerId: String, apiKey: String) {
        try {
            aiRuntime.saveKey(providerId, apiKey)
            emitOnlineAi("saved", providerId, true, "API key disimpan aman di Android Keystore")
            testOnlineProvider(providerId)
        } catch (e: Throwable) {
            emitOnlineAi("saved", providerId, false, e.message ?: "API key gagal disimpan")
        }
    }

    @JavascriptInterface
    fun deleteOnlineApiKey(providerId: String) {
        aiRuntime.removeKey(providerId)
        emitOnlineAi("deleted", providerId, true, "API key dihapus")
    }

    @JavascriptInterface
    fun testOnlineProvider(providerId: String) {
        scope.launch {
            emitOnlineAi("testing", providerId, true, "Menguji API key dan katalog model gratis…")
            val result = aiRuntime.test(providerId)
            emitOnlineAi("tested", providerId, result.success, result.message)
        }
    }

    @JavascriptInterface
    fun refreshOnlineModels(providerId: String) {
        scope.launch {
            emitOnlineAi("refreshing", providerId, true, "Memperbarui model gratis…")
            val result = aiRuntime.refresh(providerId)
            emitOnlineAi("refreshed", providerId, result.success, result.message)
        }
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
        // Immediate removal keeps UI responsive. Repeat after cancellation so a generation
        // that was already unwinding cannot resurrect the deleted session with its final write.
        store.deleteSession(sessionId)
        launchAiMutation("session-delete") {
            aiEngine.unload()
            store.deleteSession(sessionId)
        }
    }

    @JavascriptInterface
    fun clearSession(sessionId: String) {
        store.clearSession(sessionId)
        launchAiMutation("session-clear") {
            aiEngine.unload()
            store.clearSession(sessionId)
        }
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
    fun prepareModel(sessionId: String, characterName: String, persona: String) {
        if (sessionId.isBlank() || aiRuntime.config.mode() == OnlineAiConfigStore.MODE_ONLINE) return
        if (pendingMutations.get() > 0) return

        synchronized(jobLock) {
            if (generationJob?.isActive == true || prepareJob?.isActive == true) return
            lateinit var job: Job
            job = scope.launch {
                try {
                    aiOperationMutex.withLock {
                        val localModel = ModelCatalog.byId(selectedModelId()) ?: return@withLock
                        if (modelDownloads.status(localModel).optString("state") != "ready") return@withLock
                        val (providerId, model) = aiRuntime.resolve(localModel)
                        aiEngine.prepare(providerId, model, sessionId, characterName, persona)
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    emitState("error", selectedModelId(), 0.0)
                    emitError("model-prepare", friendlyEngineError(e))
                }
            }
            prepareJob = job
            job.invokeOnCompletion {
                synchronized(jobLock) {
                    if (prepareJob === job) prepareJob = null
                }
            }
        }
    }

    @JavascriptInterface
    fun generate(requestId: String, sessionId: String, userText: String, characterName: String, persona: String) {
        val clean = userText.trim()
        if (clean.isEmpty()) return
        if (pendingMutations.get() > 0) {
            emitError(requestId, "Mesin AI sedang mengganti atau membersihkan konteks")
            return
        }

        synchronized(jobLock) {
            if (generationJob?.isActive == true) {
                emitError(requestId, "Furina masih menyelesaikan jawaban sebelumnya")
                return
            }
            lateinit var job: Job
            job = scope.launch {
                try {
                    aiOperationMutex.withLock {
                        val localModel = ModelCatalog.byId(selectedModelId()) ?: error("Model AI lokal tidak dikenal")
                        if (aiRuntime.config.mode() != OnlineAiConfigStore.MODE_ONLINE) {
                            val modelState = modelDownloads.status(localModel).optString("state")
                            if (modelState != "ready") error("Unduh ${localModel.displayName} terlebih dahulu")
                        }
                        val (providerId, model) = aiRuntime.resolve(localModel)
                        emitState("thinking", model.id, 0.0)
                        val pending = StringBuilder()
                        var lastDispatch = android.os.SystemClock.elapsedRealtime()
                        val result = aiEngine.generate(
                            requestId, providerId, model, sessionId, clean, characterName, persona,
                        ) { token ->
                            pending.append(token)
                            val now = android.os.SystemClock.elapsedRealtime()
                            if (pending.length >= STREAM_DISPATCH_MIN_CHARS || now - lastDispatch >= STREAM_DISPATCH_MAX_DELAY_MS) {
                                dispatchToken(requestId, pending.toString())
                                pending.clear()
                                lastDispatch = now
                            }
                        }
                        if (pending.isNotEmpty()) dispatchToken(requestId, pending.toString())
                        emitDone(requestId, result.userId, result.assistantId, result.metrics)
                        emitState("ready", model.id, 1.0)
                    }
                    withContext(Dispatchers.IO) {
                        try { backupManager.autoBackupIfDue() } catch (_: Throwable) {}
                    }
                } catch (e: CancellationException) {
                    emitError(requestId, "Respons dihentikan")
                    emitState("cancelled", selectedModelId(), 0.0)
                } catch (e: Throwable) {
                    emitState("error", selectedModelId(), 0.0)
                    emitError(requestId, friendlyEngineError(e))
                }
            }
            generationJob = job
            job.invokeOnCompletion {
                synchronized(jobLock) {
                    // Completion of an old cancelled job must never clear a newer job.
                    if (generationJob === job) generationJob = null
                }
            }
        }
    }

    @JavascriptInterface
    fun stopGeneration() {
        // The completion callback owns clearing the reference. Clearing immediately creates a
        // window where a second generation can enter while native llama.cpp is still unwinding.
        synchronized(jobLock) { generationJob }?.cancel()
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
        launchAiMutation("restore") {
            aiEngine.unload()
            withContext(Dispatchers.IO) { backupManager.restoreFrom(uri) }
            emitBackup(true, "Restore selesai. Memori dan kontinuitas Furina sudah dipulihkan.")
            eval("window.__furinaNativeRestored && window.__furinaNativeRestored()")
        }
    }

    /** Used by cloud restore so database replacement cannot overlap native generation. */
    suspend fun withAiPaused(block: suspend () -> Unit) {
        runExclusiveMutation {
            aiEngine.unload()
            block()
        }
    }

    /**
     * Engineering evidence never preempts ordinary chat. It enters the same native AI mutex and
     * receives the exact LocalLlamaProvider already owned by FurinaBridge. Reusing that provider
     * keeps mapped GGUF weights warm when available; evidence itself resets scenario/chat KV state.
     */
    suspend fun withAiIdleForEvidence(block: suspend (LocalLlamaProvider) -> Unit): Boolean = aiOperationMutex.withLock {
        val busy = synchronized(jobLock) {
            generationJob?.isActive == true || prepareJob?.isActive == true
        }
        if (busy || pendingMutations.get() > 0) return@withLock false
        block(localProvider)
        true
    }

    fun notifyNativeReady() {
        eval("window.__furinaNativeReady && window.__furinaNativeReady()")
    }

    fun destroy() {
        synchronized(jobLock) {
            generationJob?.cancel()
            prepareJob?.cancel()
        }
        aiEngine.destroy()
        scope.cancel()
        store.close()
    }

    private fun launchAiMutation(requestId: String, block: suspend () -> Unit) {
        scope.launch {
            try {
                runExclusiveMutation(block)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                emitError(requestId, friendlyEngineError(e))
            }
        }
    }

    private suspend fun runExclusiveMutation(block: suspend () -> Unit) {
        pendingMutations.incrementAndGet()
        try {
            val jobs = synchronized(jobLock) {
                listOfNotNull(generationJob, prepareJob).also { active -> active.forEach { it.cancel() } }
            }
            jobs.joinAll()
            aiOperationMutex.withLock { block() }
        } finally {
            pendingMutations.decrementAndGet()
        }
    }

    private fun selectedModelId(): String {
        val fallback = ModelCatalog.models.first().id
        val stored = prefs.getString("selected_model", fallback)
        val selected = ModelCatalog.byId(stored)?.id ?: fallback
        if (stored != selected) prefs.edit().putString("selected_model", selected).apply()
        return selected
    }

    private fun beginVerification(spec: ModelSpec) {
        synchronized(verificationJobs) {
            if (verificationJobs[spec.id]?.isActive == true) return
            verificationProgress[spec.id] = 0.0
            verificationJobs[spec.id] = scope.launch(Dispatchers.IO) {
                try {
                    val ok = modelDownloads.verifySerialized(spec) { done, total ->
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

    private fun friendlyEngineError(error: Throwable): String {
        val raw = error.message.orEmpty()
        val type = error::class.java.simpleName
        return when {
            error is OnlineProviderException -> raw.ifBlank { "Provider online gagal" }
            error is kotlinx.coroutines.TimeoutCancellationException -> "Mesin AI terlalu lama disiapkan. Tutup aplikasi lain lalu coba lagi."
            raw.contains("API key", ignoreCase = true) || raw.contains("model gratis", ignoreCase = true) || raw.contains("kuota", ignoreCase = true) -> raw
            raw.contains("RAM aman", ignoreCase = true) -> raw
            raw.startsWith("llama.cpp:", ignoreCase = true) -> "Mesin AI gagal memuat model. $raw"
            raw.contains("memory", ignoreCase = true) || raw.contains("allocate", ignoreCase = true) ->
                "RAM tidak cukup untuk model ini. Tutup aplikasi lain atau gunakan model 4B."
            type.contains("UnsupportedArchitecture", ignoreCase = true) || raw.contains("architecture", ignoreCase = true) ->
                "Runtime native gagal memuat model. Build ini akan mencoba mode kompatibilitas; jika tetap gagal, kirim detail diagnostik dari Pengaturan."
            raw.isNotBlank() -> "Mesin AI gagal: $raw"
            else -> "Mesin AI gagal ($type). Muat ulang model atau lihat diagnostik di Pengaturan."
        }
    }

    private fun dispatchToken(requestId: String, chunk: String) {
        eval("window.__furinaNativeToken && window.__furinaNativeToken(${JSONObject.quote(requestId)}, ${JSONObject.quote(chunk)})")
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

    private fun emitOnlineAi(event: String, providerId: String, success: Boolean, message: String) {
        eval("window.__furinaOnlineAi && window.__furinaOnlineAi(${JSONObject.quote(event)}, ${JSONObject.quote(providerId)}, $success, ${JSONObject.quote(message)})")
    }

    private fun emitBackup(success: Boolean, message: String) {
        eval("window.__furinaNativeBackup && window.__furinaNativeBackup($success, ${JSONObject.quote(message)})")
    }

    private fun eval(script: String) {
        webView.post { if (!webView.isDestroyed) webView.evaluateJavascript(script, null) }
    }

    private companion object {
        const val STREAM_DISPATCH_MIN_CHARS = 48
        const val STREAM_DISPATCH_MAX_DELAY_MS = 72L
    }
}
