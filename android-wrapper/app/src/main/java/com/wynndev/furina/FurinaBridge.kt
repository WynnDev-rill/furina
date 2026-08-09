package com.wynndev.furina

import android.net.Uri
import android.webkit.JavascriptInterface
import android.webkit.WebView
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
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
    private val contextEngine = ContextEngine(store)
    private val localProvider = LocalLlamaProvider(activity.applicationContext, modelDownloads, ::emitState)
    private val aiEngine = UnifiedAiEngine(store, contextEngine, mapOf(localProvider.id to localProvider))
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
        .put("aiEngine", "unified-provider-v1")
        .put("provider", localProvider.id)
        .put("contextStrategy", "identity + summary + relevant memory + recent history")
        .put("offline", localProvider.capabilities.offline)
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
                aiEngine.unload()
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
        scope.launch { aiEngine.unload() }
    }

    @JavascriptInterface
    fun clearSession(sessionId: String) {
        store.clearSession(sessionId)
        scope.launch { aiEngine.unload() }
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
        if (sessionId.isBlank() || generationJob?.isActive == true || prepareJob?.isActive == true) return
        prepareJob = scope.launch {
            try {
                val model = ModelCatalog.byId(selectedModelId()) ?: return@launch
                if (modelDownloads.status(model).optString("state") != "ready") return@launch
                aiEngine.prepare(model, sessionId, characterName, persona)
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
    fun generate(requestId: String, sessionId: String, userText: String, characterName: String, persona: String) {
        val clean = userText.trim()
        if (clean.isEmpty()) return
        if (generationJob?.isActive == true) {
            emitError(requestId, "Furina masih menyelesaikan jawaban sebelumnya")
            return
        }

        generationJob = scope.launch {
            try {
                val model = ModelCatalog.byId(selectedModelId()) ?: error("Model AI tidak dikenal")
                val modelState = modelDownloads.status(model).optString("state")
                if (modelState != "ready") error("Unduh ${model.displayName} terlebih dahulu")
                emitState("thinking", model.id, 0.0)
                val pending = StringBuilder()
                var lastDispatch = android.os.SystemClock.elapsedRealtime()
                val result = aiEngine.generate(requestId, model, sessionId, clean, characterName, persona) { token ->
                    pending.append(token)
                    val now = android.os.SystemClock.elapsedRealtime()
                    if (pending.length >= 24 || now - lastDispatch >= 45L) {
                        dispatchToken(requestId, pending.toString())
                        pending.clear()
                        lastDispatch = now
                    }
                }
                if (pending.isNotEmpty()) dispatchToken(requestId, pending.toString())
                emitDone(requestId, result.userId, result.assistantId, result.metrics)
                emitState("ready", model.id, 1.0)
                withContext(Dispatchers.IO) {
                    try { backupManager.autoBackupIfDue() } catch (_: Throwable) {}
                }
            } catch (e: CancellationException) {
                emitError(requestId, "Respons dihentikan")
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
                aiEngine.unload()
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
        // The llama runtime is process-wide; Android frees native memory with the process.
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

    private fun friendlyEngineError(error: Throwable): String {
        val raw = error.message.orEmpty()
        val type = error::class.java.simpleName
        return when {
            error is kotlinx.coroutines.TimeoutCancellationException -> "Mesin AI terlalu lama disiapkan. Tutup aplikasi lain lalu coba lagi."
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

    private fun emitBackup(success: Boolean, message: String) {
        eval("window.__furinaNativeBackup && window.__furinaNativeBackup($success, ${JSONObject.quote(message)})")
    }

    private fun eval(script: String) {
        webView.post { if (!webView.isDestroyed) webView.evaluateJavascript(script, null) }
    }
}
