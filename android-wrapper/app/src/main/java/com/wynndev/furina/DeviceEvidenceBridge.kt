package com.wynndev.furina

import android.provider.Settings
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.Signature
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Native bridge for synthetic engineering evidence only. */
class DeviceEvidenceBridge(
    private val activity: MainActivity,
    private val webView: WebView,
    store: MemoryStore,
    private val modelDownloads: ModelDownloadManager,
    private val withAiIdleForEvidence: suspend (suspend (LocalLlamaProvider) -> Unit) -> Boolean,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val prefs = activity.getSharedPreferences("furina_native", 0)
    private val evidencePrefs = activity.getSharedPreferences("furina_device_evidence", 0)
    private val contextEngine = ContextEngine(activity.applicationContext, store)
    private val jobLock = Any()
    private val transportMutex = Mutex()
    private var activeJob: Job? = null

    /**
     * Fetch the authoritative request through a dedicated install/device credential. This path is
     * intentionally independent from Furina backup/login auth: no Google or Supabase user session
     * is required for engineering evidence.
     */
    @JavascriptInterface
    fun probeEvidenceRequest() {
        scope.launch {
            try {
                val response = transportMutex.withLock {
                    ensureDeviceRegistered()
                    signedDeviceCall("request", null)
                }
                val request = response.optJSONObject("request")
                emitRequest(request?.toString().orEmpty())
            } catch (error: Throwable) {
                emitTransportError("probe", "", error.message ?: "device evidence probe failed")
            }
        }
    }

    /** Upload an already-completed raw benchmark without rerunning inference on transport retry. */
    @JavascriptInterface
    fun submitBehavioralEvidence(reportJson: String) {
        if (reportJson.isBlank() || reportJson.length > MAX_RESULT_CHARS) return
        val requestId = runCatching { JSONObject(reportJson).optString("requestId").trim() }.getOrDefault("")
        if (requestId.isBlank()) return
        scope.launch {
            try {
                transportMutex.withLock {
                    ensureDeviceRegistered()
                    signedDeviceCall("result", reportJson)
                }
                emitSubmitted(requestId)
            } catch (error: Throwable) {
                emitTransportError("submit", requestId, error.message ?: "device evidence upload failed")
            }
        }
    }

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
                    // Evidence is lower priority than chat. FurinaBridge owns the single shared
                    // LocalLlamaProvider and AI mutex so an already-loaded GGUF can be reused
                    // instead of being unloaded/reloaded solely for benchmark capture.
                    val ran = withAiIdleForEvidence { sharedProvider ->
                        report = DeviceBehavioralBenchmark(
                            contextEngine = contextEngine,
                            provider = sharedProvider,
                            modelDownloads = modelDownloads,
                            selectedModelId = ::selectedModelId,
                            onProgress = ::emitProgress,
                        ).run(rawRequest)
                    }
                    if (!ran) {
                        emitError(requestId, "ai_busy")
                        return@launch
                    }
                    emitDone(requestId, report ?: error("Benchmark selesai tanpa report"))
                } catch (cancelled: CancellationException) {
                    emitError(requestId, "cancelled")
                    throw cancelled
                } catch (error: Throwable) {
                    emitError(requestId, error.message ?: "device benchmark failed")
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
        .put("loginRequired", false)
        .put("credential", "AndroidKeyStore RSA device key")
        .put("benchmarkRuntime", "shared-local-provider-v2")
        .toString()

    fun destroy() {
        synchronized(jobLock) { activeJob }?.cancel()
        scope.cancel()
    }

    private suspend fun ensureDeviceRegistered() {
        val appCommit = appCommit()
        val previouslyRegistered = evidencePrefs.getString(PREF_REGISTERED_COMMIT, null)
        val enrollmentToken = BuildConfig.EVIDENCE_ENROLLMENT_TOKEN.trim().lowercase()

        // Existing AndroidKeyStore identity survives normal APK updates. Main builds carry a fresh
        // one-time enrollment token so the server can refresh the exact-build binding without any
        // user login. PR/test builds with no token may still use an identity enrolled by main.
        if (previouslyRegistered == appCommit) {
            ensureKeyPair()
            return
        }
        if (enrollmentToken.isBlank() && !previouslyRegistered.isNullOrBlank()) {
            ensureKeyPair()
            return
        }
        require(ENROLLMENT_TOKEN.matches(enrollmentToken)) {
            "Build APK belum memiliki token enrollment evidence"
        }

        val body = JSONObject()
            .put("action", "register")
            .put("deviceId", deviceId())
            .put("targetCommit", appCommit)
            .put("enrollmentToken", enrollmentToken)
            .put("publicKeySpki", publicKeyBase64())
        val response = postJson(body)
        require(response.optBoolean("ok")) { response.optString("error", "device registration failed") }
        evidencePrefs.edit().putString(PREF_REGISTERED_COMMIT, appCommit).apply()
    }

    private suspend fun signedDeviceCall(action: String, resultRaw: String?): JSONObject {
        require(action == "request" || action == "result") { "unsupported evidence action" }
        val deviceId = deviceId()
        val appCommit = appCommit()
        val challenge = postJson(
            JSONObject()
                .put("action", "device_challenge")
                .put("deviceId", deviceId)
        )
        val challengeId = challenge.optString("challengeId").trim()
        val nonce = challenge.optString("nonce").trim()
        require(HEX_64.matches(challengeId) && HEX_64.matches(nonce)) { "invalid evidence challenge" }

        val payloadHash = if (action == "result") sha256Hex(resultRaw.orEmpty()) else ""
        val canonical = listOf(
            SIGNATURE_DOMAIN,
            action,
            deviceId,
            challengeId,
            nonce,
            appCommit,
            payloadHash,
        ).joinToString("\n")
        val signature = sign(canonical)
        val body = JSONObject()
            .put("action", action)
            .put("deviceId", deviceId)
            .put("challengeId", challengeId)
            .put("nonce", nonce)
            .put("appCommit", appCommit)
            .put("signature", signature)
        if (action == "result") {
            require(!resultRaw.isNullOrBlank() && resultRaw.length <= MAX_RESULT_CHARS) { "invalid evidence result" }
            body.put("resultRaw", resultRaw)
        }
        return postJson(body)
    }

    private suspend fun postJson(body: JSONObject): JSONObject = withContext(Dispatchers.IO) {
        val connection = (URL(EVIDENCE_ENDPOINT).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            doOutput = true
            useCaches = false
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            setRequestProperty("Accept", "application/json")
            setRequestProperty("User-Agent", "FurinaEvidence/1")
        }
        try {
            connection.outputStream.use { stream ->
                stream.write(body.toString().toByteArray(StandardCharsets.UTF_8))
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val text = stream?.bufferedReader(StandardCharsets.UTF_8)?.use { it.readText() }.orEmpty()
            val response = runCatching { if (text.isBlank()) JSONObject() else JSONObject(text) }
                .getOrElse { JSONObject().put("error", text.take(500)) }
            if (code !in 200..299) {
                throw IllegalStateException("evidence_http_$code:${response.optString("error", "request failed")}")
            }
            response
        } finally {
            connection.disconnect()
        }
    }

    private fun deviceId(): String {
        val androidId = Settings.Secure.getString(activity.contentResolver, Settings.Secure.ANDROID_ID)
            ?.trim()
            .orEmpty()
        require(androidId.isNotBlank()) { "Android device identity unavailable" }
        return sha256Hex("${activity.packageName}|$androidId")
    }

    private fun appCommit(): String {
        val commit = BuildConfig.GIT_SHA.trim().lowercase()
        require(COMMIT.matches(commit)) { "Build APK belum memiliki commit provenance" }
        return commit
    }

    private fun ensureKeyPair() {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (keyStore.containsAlias(KEY_ALIAS)) return
        val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_RSA, "AndroidKeyStore")
        generator.initialize(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY,
            )
                .setKeySize(2048)
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1)
                .setUserAuthenticationRequired(false)
                .build()
        )
        generator.generateKeyPair()
    }

    private fun publicKeyBase64(): String {
        ensureKeyPair()
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val encoded = keyStore.getCertificate(KEY_ALIAS)?.publicKey?.encoded
            ?: error("Evidence public key unavailable")
        return Base64.encodeToString(encoded, Base64.NO_WRAP)
    }

    private fun sign(canonical: String): String {
        ensureKeyPair()
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val privateKey = keyStore.getKey(KEY_ALIAS, null) as? PrivateKey
            ?: error("Evidence private key unavailable")
        val signer = Signature.getInstance("SHA256withRSA")
        signer.initSign(privateKey)
        signer.update(canonical.toByteArray(StandardCharsets.UTF_8))
        return Base64.encodeToString(signer.sign(), Base64.NO_WRAP)
    }

    private fun sha256Hex(value: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(StandardCharsets.UTF_8))
        return bytes.joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
    }

    private fun selectedModelId(): String {
        val fallback = ModelCatalog.models.first().id
        return ModelCatalog.byId(prefs.getString("selected_model", fallback))?.id ?: fallback
    }

    private fun emitRequest(requestJson: String) {
        eval(
            "window.__furinaDeviceEvidenceRequest && window.__furinaDeviceEvidenceRequest(" +
                "${JSONObject.quote(requestJson)})"
        )
    }

    private fun emitProgress(requestId: String, completed: Int, total: Int) {
        eval(
            "window.__furinaDeviceEvidenceProgress && window.__furinaDeviceEvidenceProgress(" +
                "${JSONObject.quote(requestId)}, $completed, $total)"
        )
    }

    private fun emitDone(requestId: String, report: JSONObject) {
        eval(
            "window.__furinaDeviceEvidenceDone && window.__furinaDeviceEvidenceDone(" +
                "${JSONObject.quote(requestId)}, ${JSONObject.quote(report.toString())})"
        )
    }

    private fun emitSubmitted(requestId: String) {
        eval(
            "window.__furinaDeviceEvidenceSubmitted && window.__furinaDeviceEvidenceSubmitted(" +
                "${JSONObject.quote(requestId)})"
        )
    }

    private fun emitError(requestId: String, message: String) {
        eval(
            "window.__furinaDeviceEvidenceError && window.__furinaDeviceEvidenceError(" +
                "${JSONObject.quote(requestId)}, ${JSONObject.quote(message.take(500))})"
        )
    }

    private fun emitTransportError(operation: String, requestId: String, message: String) {
        eval(
            "window.__furinaDeviceEvidenceTransportError && window.__furinaDeviceEvidenceTransportError(" +
                "${JSONObject.quote(operation)}, ${JSONObject.quote(requestId)}, ${JSONObject.quote(message.take(500))})"
        )
    }

    private fun eval(script: String) {
        webView.post { if (!webView.isDestroyed) webView.evaluateJavascript(script, null) }
    }

    private companion object {
        const val EVIDENCE_ENDPOINT = "https://fxebamfwewsvtscrbwxk.supabase.co/functions/v1/furina-device-evidence"
        const val SIGNATURE_DOMAIN = "furina-device-evidence-v1"
        const val KEY_ALIAS = "furina_engineering_evidence_v1"
        const val PREF_REGISTERED_COMMIT = "registered_commit"
        const val MAX_REQUEST_CHARS = 96_000
        const val MAX_RESULT_CHARS = 512_000
        const val CONNECT_TIMEOUT_MS = 10_000
        const val READ_TIMEOUT_MS = 30_000
        val COMMIT = Regex("^[0-9a-f]{40}$")
        val HEX_64 = Regex("^[0-9a-f]{64}$")
        val ENROLLMENT_TOKEN = Regex("^[0-9a-f]{64}$")
    }
}
