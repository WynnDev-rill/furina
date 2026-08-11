package com.wynndev.furina

import android.webkit.JavascriptInterface
import android.webkit.WebView
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONObject

/** Invisible WebView bridge for synthetic engineering evidence only. */
class DeviceEvidenceBridge(
    private val activity: MainActivity,
    private val webView: WebView,
    store: MemoryStore,
    modelDownloads: ModelDownloadManager,
    private val withAiPaused: suspend (suspend () -> Unit) -> Unit,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val prefs = activity.getSharedPreferences("furina_native", 0)
    private val localProvider = LocalLlamaProvider(activity.applicationContext, modelDownloads) { _, _, _ -> }
    private val benchmark = DeviceBehavioralBenchmark(
        contextEngine = ContextEngine(activity.applicationContext, store),
        provider = localProvider,
        modelDownloads = modelDownloads,
        selectedModelId = ::selectedModelId,
    )
    private val jobLock = Any()
    private var activeJob: Job? = null

    @JavascriptInterface
    fun runBehavioralBenchmark(rawRequest: String) {
        if (rawRequest.isBlank() || rawRequest.length > MAX_REQUEST_CHARS) return
        val requestId = runCatching { JSONObject(rawRequest).optString("requestId").trim() }.getOrDefault("")
        if (requestId.isBlank()) return

        synchronized(jobLock) {
            if (activeJob?.isActive == true) return
            lateinit var job: Job
            job = scope.launch {
                try {
                    var report: JSONObject? = null
                    // Reuse FurinaBridge's mutation boundary so ordinary chat/model preparation
                    // cannot overlap the benchmark. Web waits for a user-idle window first.
                    withAiPaused { report = benchmark.run(rawRequest) }
                    emitDone(requestId, report ?: error("Benchmark selesai tanpa report"))
                } catch (cancelled: CancellationException) {
                    emitError(requestId, "cancelled")
                    throw cancelled
                } catch (error: Throwable) {
                    emitError(requestId, error.message ?: "device benchmark failed")
                } finally {
                    try { localProvider.unload() } catch (_: Throwable) {}
                }
            }
            activeJob = job
            job.invokeOnCompletion {
                synchronized(jobLock) {
                    if (activeJob === job) activeJob = null
                }
            }
        }
    }

    @JavascriptInterface
    fun cancelBehavioralBenchmark() {
        synchronized(jobLock) { activeJob }?.cancel()
    }

    @JavascriptInterface
    fun evidenceInfo(): String = JSONObject()
        .put("available", true)
        .put("gitSha", BuildConfig.GIT_SHA)
        .put("syntheticOnly", true)
        .put("persistentWrites", false)
        .toString()

    fun destroy() {
        synchronized(jobLock) { activeJob }?.cancel()
        scope.cancel()
    }

    private fun selectedModelId(): String {
        val fallback = ModelCatalog.models.first().id
        return ModelCatalog.byId(prefs.getString("selected_model", fallback))?.id ?: fallback
    }

    private fun emitDone(requestId: String, report: JSONObject) {
        eval(
            "window.__furinaDeviceEvidenceDone && window.__furinaDeviceEvidenceDone(" +
                "${JSONObject.quote(requestId)}, ${JSONObject.quote(report.toString())})"
        )
    }

    private fun emitError(requestId: String, message: String) {
        eval(
            "window.__furinaDeviceEvidenceError && window.__furinaDeviceEvidenceError(" +
                "${JSONObject.quote(requestId)}, ${JSONObject.quote(message.take(500))})"
        )
    }

    private fun eval(script: String) {
        webView.post { if (!webView.isDestroyed) webView.evaluateJavascript(script, null) }
    }

    private companion object {
        const val MAX_REQUEST_CHARS = 96_000
    }
}
