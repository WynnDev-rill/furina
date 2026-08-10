package com.wynndev.furina

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.channelFlow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStream
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap


data class ProviderProbeResult(
    val success: Boolean,
    val message: String,
    val models: List<OnlineModel> = emptyList(),
)

class OnlineProviderException(
    val status: Int,
    message: String,
    val retryable: Boolean,
) : IllegalStateException(message)

/**
 * OpenRouter, Gemini and Groq expose compatible chat/model endpoints. One adapter keeps
 * Furina's prompt/memory semantics identical across providers and prevents an unhealthy
 * free-model catalogue from turning one response into minutes of sequential retries.
 */
class OpenAiCompatibleProvider(
    private val spec: OnlineProviderSpec,
    private val keyStore: SecureApiKeyStore,
    private val config: OnlineAiConfigStore,
) : AiProvider {
    override val id: String = spec.id
    override val capabilities = AiProviderCapabilities(streaming = true, offline = false)

    @Volatile private var modelCache: List<OnlineModel> = emptyList()
    @Volatile private var modelCacheAt: Long = 0L
    @Volatile private var lastResolvedModel: String? = null
    private val unhealthyUntil = ConcurrentHashMap<String, Long>()

    override fun isWarm(model: AiModelRef, context: AiContext): Boolean = keyStore.has(id)
    override suspend fun prepare(model: AiModelRef, context: AiContext) = Unit
    override suspend fun unload() = Unit
    override fun resolvedModelId(): String? = lastResolvedModel

    fun cachedModels(): List<OnlineModel> = modelCache

    suspend fun testAndRefresh(): ProviderProbeResult = withContext(Dispatchers.IO) {
        val key = keyStore.get(id) ?: return@withContext ProviderProbeResult(false, "API key belum disimpan")
        try {
            if (id == "openrouter") {
                val probe = request("${spec.baseUrl}/key", "GET", key)
                if (probe.code !in 200..299) throw httpError(probe.code, probe.body)
            }
            val models = discoverFreeModels(force = true)
            if (models.isEmpty()) {
                ProviderProbeResult(false, "API key valid, tetapi tidak ada model gratis yang aman dipilih otomatis.")
            } else {
                ProviderProbeResult(true, "API key aktif · ${models.size} model gratis tersedia", models)
            }
        } catch (e: OnlineProviderException) {
            ProviderProbeResult(false, e.message ?: "Provider menolak API key")
        } catch (e: Throwable) {
            ProviderProbeResult(false, e.message ?: "Tidak dapat terhubung ke provider")
        }
    }

    suspend fun discoverFreeModels(force: Boolean = false): List<OnlineModel> = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        if (!force && modelCache.isNotEmpty() && now - modelCacheAt < 10 * 60_000L) return@withContext modelCache
        val key = keyStore.get(id) ?: return@withContext emptyList()
        val response = request("${spec.baseUrl}/models", "GET", key)
        if (response.code !in 200..299) throw httpError(response.code, response.body)
        val parsed = parseModels(response.body)
        modelCache = parsed
        modelCacheAt = now
        val selected = config.selectedModel(id)
        if (selected.isNullOrBlank() || parsed.none { it.id == selected }) {
            config.setSelectedModel(id, parsed.firstOrNull()?.id)
        }
        parsed
    }

    override fun stream(request: AiGenerationRequest): Flow<String> = channelFlow {
        val key = keyStore.get(id) ?: throw IllegalStateException("API key ${spec.displayName} belum disimpan")
        val discovered = try {
            discoverFreeModels(force = false)
        } catch (e: Throwable) {
            if (modelCache.isNotEmpty()) modelCache else throw e
        }
        if (discovered.isEmpty()) throw IllegalStateException("Tidak ada model gratis ${spec.displayName} yang tersedia")

        val preferredId = config.selectedModel(id).takeUnless { it.isNullOrBlank() } ?: request.model.id
        val preferred = discovered.firstOrNull { it.id == preferredId }
        val ordered = buildList {
            if (preferred != null) add(preferred)
            discovered.filterTo(this) { it.id != preferred?.id }
        }
        val now = System.currentTimeMillis()
        val healthy = ordered.filter { (unhealthyUntil[it.id] ?: 0L) <= now }
        val pool = if (healthy.isNotEmpty()) healthy else ordered
        val candidates = if (config.autoFallback()) pool.take(MAX_FALLBACK_CANDIDATES) else ordered.take(1)
        var lastError: Throwable? = null

        for (candidate in candidates) {
            var emitted = false
            try {
                generateCandidate(key, candidate, request) { chunk ->
                    if (chunk.isNotEmpty()) {
                        emitted = true
                        send(chunk)
                    }
                }
                unhealthyUntil.remove(candidate.id)
                lastResolvedModel = candidate.id
                return@channelFlow
            } catch (e: OnlineProviderException) {
                lastError = e
                if (!emitted && e.retryable) {
                    val cooldown = if (e.status == 429) 5 * 60_000L else 90_000L
                    unhealthyUntil[candidate.id] = System.currentTimeMillis() + cooldown
                }
                if (emitted || !config.autoFallback() || !e.retryable) throw e
            }
        }
        throw lastError ?: IllegalStateException("Semua model gratis ${spec.displayName} sedang tidak tersedia")
    }

    private suspend fun generateCandidate(
        key: String,
        model: OnlineModel,
        request: AiGenerationRequest,
        onChunk: suspend (String) -> Unit,
    ) = withContext(Dispatchers.IO) {
        val payload = JSONObject()
            .put("model", model.id)
            .put("stream", true)
            .put("temperature", 0.85)
            .put("max_tokens", request.predictLength.coerceIn(64, model.maxOutputTokens))
            .put("messages", JSONArray().apply {
                put(JSONObject().put("role", "system").put("content", request.context.systemPrompt))
                // Dynamic relationship state is background context, never merged into the
                // current user's role. This preserves the same priority rule as local mode.
                if (request.context.runtimeContext.isNotBlank()) {
                    put(JSONObject().put("role", "system").put("content", request.context.runtimeContext))
                }
                put(JSONObject().put("role", "user").put("content", request.userMessage))
            })
        applyReasoningPolicy(payload, model.id)

        val connection = openConnection("${spec.baseUrl}/chat/completions", "POST", key).apply {
            doOutput = true
            setRequestProperty("Accept", "text/event-stream, application/json")
        }
        connection.outputStream.use { it.write(payload.toString().toByteArray(StandardCharsets.UTF_8)) }
        val code = connection.responseCode
        if (code !in 200..299) {
            val body = readAll(connection.errorStream ?: connection.inputStream)
            connection.disconnect()
            throw httpError(code, body)
        }

        val contentType = connection.contentType?.lowercase(Locale.US).orEmpty()
        val reasoningFilter = HiddenReasoningFilter()
        var emitted = false
        suspend fun emitVisible(raw: String) {
            val visible = reasoningFilter.accept(raw)
            if (visible.isNotEmpty()) {
                emitted = true
                onChunk(visible)
            }
        }
        try {
            if (contentType.contains("text/event-stream")) {
                BufferedReader(InputStreamReader(connection.inputStream, StandardCharsets.UTF_8)).use { reader ->
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (!line.startsWith("data:")) continue
                        val data = line.removePrefix("data:").trim()
                        if (data.isBlank() || data == "[DONE]") continue
                        val chunk = parseStreamChunk(data)
                        if (chunk.isNotEmpty()) emitVisible(chunk)
                    }
                }
            } else {
                val body = readAll(connection.inputStream)
                val text = parseCompletion(body)
                if (text.isNotBlank()) emitVisible(text)
            }
            val tail = reasoningFilter.finish()
            if (tail.isNotEmpty()) {
                emitted = true
                onChunk(tail)
            }
        } finally {
            connection.disconnect()
        }
        if (!emitted) throw OnlineProviderException(502, "${model.displayName} tidak menghasilkan jawaban akhir", true)
    }

    private fun applyReasoningPolicy(payload: JSONObject, modelId: String) {
        when (id) {
            "openrouter" -> payload.put(
                "reasoning",
                JSONObject().put("effort", "none").put("exclude", true),
            )
            "groq" -> {
                val normalized = modelId.lowercase(Locale.US)
                if (normalized.contains("qwen3")) {
                    payload.put("reasoning_effort", "none")
                    payload.put("reasoning_format", "hidden")
                }
            }
        }
    }

    private fun parseModels(raw: String): List<OnlineModel> {
        val root = JSONObject(raw)
        val data = root.optJSONArray("data") ?: JSONArray()
        val out = mutableListOf<OnlineModel>()
        for (i in 0 until data.length()) {
            val item = data.optJSONObject(i) ?: continue
            val modelId = item.optString("id").trim()
            if (modelId.isBlank()) continue
            val free = when (id) {
                "openrouter" -> {
                    val pricing = item.optJSONObject("pricing")
                    val prompt = pricing?.optString("prompt")?.toDoubleOrNull()
                    val completion = pricing?.optString("completion")?.toDoubleOrNull()
                    modelId == "openrouter/free" || modelId.endsWith(":free") ||
                        (prompt == 0.0 && completion == 0.0)
                }
                else -> OnlineProviderCatalog.isKnownFreeTierModel(id, modelId)
            }
            if (!free) continue
            val context = when {
                item.optInt("context_length", 0) > 0 -> item.optInt("context_length")
                item.optInt("context_window", 0) > 0 -> item.optInt("context_window")
                id == "gemini" -> 32_768
                else -> 8_192
            }
            val topProvider = item.optJSONObject("top_provider")
            val maxOutput = when {
                (topProvider?.optInt("max_completion_tokens", 0) ?: 0) > 0 -> topProvider!!.optInt("max_completion_tokens")
                item.optInt("max_completion_tokens", 0) > 0 -> item.optInt("max_completion_tokens")
                else -> 2_048
            }
            out += OnlineModel(
                id = modelId,
                displayName = item.optString("name").ifBlank { modelId },
                contextWindowTokens = context,
                maxOutputTokens = maxOutput,
            )
        }
        if (id == "openrouter" && out.none { it.id == "openrouter/free" }) {
            out.add(0, OnlineModel("openrouter/free", "OpenRouter Free Router", 32_768, 2_048))
        }
        return out.distinctBy { it.id }.sortedWith(
            compareBy<OnlineModel> { if (it.id == "openrouter/free") 0 else 1 }
                .thenByDescending { it.contextWindowTokens }
                .thenBy { it.displayName.lowercase(Locale.US) },
        )
    }

    private fun parseStreamChunk(raw: String): String {
        val root = JSONObject(raw)
        root.optJSONObject("error")?.let {
            throw OnlineProviderException(502, it.optString("message", "Provider menghentikan stream"), true)
        }
        val choice = root.optJSONArray("choices")?.optJSONObject(0) ?: return ""
        val delta = choice.optJSONObject("delta")
        return contentText(delta?.opt("content"))
    }

    private fun parseCompletion(raw: String): String {
        val root = JSONObject(raw)
        root.optJSONObject("error")?.let {
            throw OnlineProviderException(502, it.optString("message", "Provider gagal menghasilkan jawaban"), true)
        }
        val message = root.optJSONArray("choices")?.optJSONObject(0)?.optJSONObject("message") ?: return ""
        return contentText(message.opt("content"))
    }

    private fun contentText(value: Any?): String = when (value) {
        is String -> value
        is JSONArray -> buildString {
            for (i in 0 until value.length()) {
                val part = value.optJSONObject(i) ?: continue
                if (part.optString("type") == "text") append(part.optString("text"))
            }
        }
        else -> ""
    }

    private data class SimpleResponse(val code: Int, val body: String)

    private fun request(url: String, method: String, key: String): SimpleResponse {
        val connection = openConnection(url, method, key)
        return try {
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            SimpleResponse(code, readAll(stream))
        } finally {
            connection.disconnect()
        }
    }

    private fun openConnection(url: String, method: String, key: String): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 120_000
            useCaches = false
            setRequestProperty("Authorization", "Bearer $key")
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("User-Agent", "Furina-Android/4.3")
            if (id == "openrouter") {
                setRequestProperty("HTTP-Referer", "https://furina-pi.vercel.app")
                setRequestProperty("X-Title", "Furina")
            }
        }

    private fun httpError(status: Int, raw: String): OnlineProviderException {
        val message = try {
            val root = JSONObject(raw)
            root.optJSONObject("error")?.optString("message")
                ?.takeIf { it.isNotBlank() }
                ?: root.optString("message").takeIf { it.isNotBlank() }
                ?: "HTTP $status"
        } catch (_: Throwable) {
            raw.take(240).ifBlank { "HTTP $status" }
        }
        val lower = raw.lowercase(Locale.US)
        val retryable = status in setOf(402, 403, 404, 408, 409, 429, 500, 502, 503, 504) ||
            (status == 400 && listOf("context_length", "max_tokens", "token_limit", "model").any { lower.contains(it) })
        val friendly = when (status) {
            401 -> "API key ${spec.displayName} tidak valid atau sudah dicabut"
            402 -> "Kuota/kredit untuk model ini habis"
            403 -> "Model ini tidak diizinkan oleh akun ${spec.displayName}"
            429 -> "Model sedang mencapai batas kuota/rate limit"
            else -> message
        }
        return OnlineProviderException(status, friendly, retryable)
    }

    private fun readAll(stream: InputStream?): String {
        if (stream == null) return ""
        return stream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
    }

    private class HiddenReasoningFilter {
        private enum class Mode { UNDECIDED, HIDDEN, ANSWER }
        private var mode = Mode.UNDECIDED
        private var activeCloseTag = "</think>"
        private val pending = StringBuilder()
        private val pairs = listOf(
            "<think>" to "</think>",
            "<analysis>" to "</analysis>",
            "<reasoning>" to "</reasoning>",
        )

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
                        val exact = pairs.firstOrNull { candidate.startsWith(it.first, ignoreCase = true) }
                        if (exact != null) {
                            pending.delete(0, leading + exact.first.length)
                            activeCloseTag = exact.second
                            mode = Mode.HIDDEN
                            continue
                        }
                        val couldBecomeTag = candidate.isNotEmpty() && pairs.any {
                            it.first.startsWith(candidate, ignoreCase = true)
                        }
                        if (candidate.isEmpty() || couldBecomeTag) break
                        mode = Mode.ANSWER
                        continue
                    }
                    Mode.HIDDEN -> {
                        val raw = pending.toString()
                        val lower = raw.lowercase(Locale.US)
                        val end = lower.indexOf(activeCloseTag.lowercase(Locale.US))
                        if (end >= 0) {
                            pending.delete(0, end + activeCloseTag.length)
                            while (pending.isNotEmpty() && pending.first().isWhitespace()) pending.deleteCharAt(0)
                            mode = Mode.ANSWER
                            continue
                        }
                        if (pending.length > 40) pending.delete(0, pending.length - 40)
                        break
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
            Mode.HIDDEN -> ""
        }.also { pending.clear() }
    }

    private companion object {
        const val MAX_FALLBACK_CANDIDATES = 5
    }
}
