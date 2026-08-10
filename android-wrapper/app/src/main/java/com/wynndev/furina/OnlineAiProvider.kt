package com.wynndev.furina

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

enum class FreeModelStrategy { OPENROUTER_ZERO_PRICE, GROQ_FREE_PLAN, GEMINI_FREE_TIER }

data class OnlineProviderDefinition(
    val id: String,
    val name: String,
    val baseUrl: String,
    val modelsPath: String,
    val strategy: FreeModelStrategy,
    val note: String,
)

data class OnlineModelInfo(
    val id: String,
    val name: String,
    val contextWindow: Int,
    val maxOutputTokens: Int,
    val vision: Boolean = false,
    val tools: Boolean = false,
    val reasoning: Boolean = false,
) {
    fun toJson() = JSONObject()
        .put("id", id)
        .put("name", name)
        .put("contextWindow", contextWindow)
        .put("maxOutputTokens", maxOutputTokens)
        .put("vision", vision)
        .put("tools", tools)
        .put("reasoning", reasoning)

    fun toModel(providerId: String) = AiModelRef(
        providerId = providerId,
        id = id,
        displayName = name,
        contextWindow = contextWindow,
        maxOutputTokens = maxOutputTokens,
        vision = vision,
        tools = tools,
        reasoning = reasoning,
    )

    companion object {
        fun fromJson(obj: JSONObject) = OnlineModelInfo(
            id = obj.getString("id"),
            name = obj.optString("name", obj.getString("id")),
            contextWindow = obj.optInt("contextWindow", 32_768),
            maxOutputTokens = obj.optInt("maxOutputTokens", 1_024),
            vision = obj.optBoolean("vision", false),
            tools = obj.optBoolean("tools", false),
            reasoning = obj.optBoolean("reasoning", false),
        )
    }
}

class OnlineProviderManager(context: Context) {
    companion object {
        private const val PREFS = "furina_online_ai"
        private const val CACHE_TTL_MS = 12L * 60L * 60L * 1000L

        val DEFINITIONS = listOf(
            OnlineProviderDefinition(
                id = "openrouter",
                name = "OpenRouter",
                baseUrl = "https://openrouter.ai/api/v1",
                modelsPath = "/models/user",
                strategy = FreeModelStrategy.OPENROUTER_ZERO_PRICE,
                note = "Model :free dan router gratis OpenRouter. Daftar diperbarui dari API.",
            ),
            OnlineProviderDefinition(
                id = "groq",
                name = "Groq",
                baseUrl = "https://api.groq.com/openai/v1",
                modelsPath = "/models",
                strategy = FreeModelStrategy.GROQ_FREE_PLAN,
                note = "Model chat yang tercantum pada Free Plan Groq. Batas kuota berlaku per model/proyek.",
            ),
            OnlineProviderDefinition(
                id = "gemini",
                name = "Gemini",
                baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai",
                modelsPath = "/models",
                strategy = FreeModelStrategy.GEMINI_FREE_TIER,
                note = "Model Flash/Flash-Lite yang tersedia pada free tier Gemini API.",
            ),
        )
    }

    private val appContext = context.applicationContext
    private val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val vault = ApiKeyVault(appContext)

    fun definition(id: String): OnlineProviderDefinition =
        DEFINITIONS.firstOrNull { it.id == id } ?: error("Provider online tidak dikenal: $id")

    fun mode(): String = prefs.getString("mode", "local").let { if (it == "online") "online" else "local" }
    fun selectedProviderId(): String = prefs.getString("provider", "openrouter")
        ?.takeIf { id -> DEFINITIONS.any { it.id == id } } ?: "openrouter"
    fun autoFallback(): Boolean = prefs.getBoolean("auto_fallback", true)
    fun apiKey(providerId: String): String? = vault.get(providerId)

    fun setMode(mode: String): String {
        prefs.edit().putString("mode", if (mode == "online") "online" else "local").apply()
        return settingsJson().toString()
    }

    fun setProvider(providerId: String): String {
        definition(providerId)
        prefs.edit().putString("provider", providerId).apply()
        return settingsJson().toString()
    }

    fun setModel(providerId: String, modelId: String): String {
        definition(providerId)
        require(cachedModels(providerId).any { it.id == modelId }) { "Model gratis tidak tersedia pada cache provider" }
        prefs.edit().putString("model_$providerId", modelId).apply()
        return settingsJson().toString()
    }

    fun setAutoFallback(enabled: Boolean): String {
        prefs.edit().putBoolean("auto_fallback", enabled).apply()
        return settingsJson().toString()
    }

    fun removeKey(providerId: String): String {
        definition(providerId)
        vault.remove(providerId)
        return settingsJson().toString()
    }

    fun settingsJson(): JSONObject {
        val providers = JSONArray()
        DEFINITIONS.forEach { def ->
            val models = cachedModels(def.id)
            val modelJson = JSONArray().apply { models.forEach { put(it.toJson()) } }
            providers.put(JSONObject()
                .put("id", def.id)
                .put("name", def.name)
                .put("note", def.note)
                .put("configured", vault.has(def.id))
                .put("selectedModelId", selectedModelId(def.id, models))
                .put("models", modelJson)
                .put("lastRefresh", prefs.getLong("models_ts_${def.id}", 0L)))
        }
        return JSONObject()
            .put("mode", mode())
            .put("providerId", selectedProviderId())
            .put("autoFallback", autoFallback())
            .put("providers", providers)
    }

    suspend fun testAndSave(providerId: String, rawKey: String): JSONObject {
        val def = definition(providerId)
        val key = rawKey.trim()
        require(key.length >= 8) { "API key terlalu pendek" }
        val models = OpenAiHttp.listFreeModels(def, key)
        if (models.isEmpty()) throw AiProviderException(def.id, null, 404, false, message = "API key valid, tetapi tidak ada model gratis yang cocok saat ini")
        vault.put(providerId, key)
        saveModels(providerId, models)
        val selected = selectedModelId(providerId, models).takeIf { id -> models.any { it.id == id } } ?: models.first().id
        prefs.edit().putString("model_$providerId", selected).apply()

        val selectedModel = models.first { it.id == selected }
        return try {
            OpenAiHttp.probe(def, key, selectedModel)
            JSONObject()
                .put("success", true)
                .put("keyValid", true)
                .put("generationReady", true)
                .put("message", "API key aktif. ${models.size} model gratis/free-tier ditemukan.")
                .put("settings", settingsJson())
        } catch (e: AiProviderException) {
            if (e.statusCode == 401) {
                vault.remove(providerId)
                throw e
            }
            JSONObject()
                .put("success", true)
                .put("keyValid", true)
                .put("generationReady", false)
                .put("message", "API key valid, tetapi tes generasi gagal: ${e.message}. Fallback otomatis tetap akan mencoba model gratis lain.")
                .put("settings", settingsJson())
        }
    }

    suspend fun refresh(providerId: String): JSONObject {
        val def = definition(providerId)
        val key = apiKey(providerId) ?: throw AiProviderException(def.id, null, 401, false, message = "Masukkan API key ${def.name} terlebih dahulu")
        val models = OpenAiHttp.listFreeModels(def, key)
        if (models.isEmpty()) throw AiProviderException(def.id, null, 404, false, message = "Tidak ada model gratis/free-tier yang ditemukan")
        saveModels(providerId, models)
        if (selectedModelId(providerId, models).isBlank()) prefs.edit().putString("model_$providerId", models.first().id).apply()
        return JSONObject()
            .put("success", true)
            .put("message", "Daftar model diperbarui: ${models.size} model tersedia.")
            .put("settings", settingsJson())
    }

    suspend fun route(): AiRoute {
        val providerId = selectedProviderId()
        val def = definition(providerId)
        if (!vault.has(providerId)) throw AiProviderException(providerId, null, 401, false, message = "API key ${def.name} belum dipasang")
        var models = cachedModels(providerId)
        val stale = System.currentTimeMillis() - prefs.getLong("models_ts_$providerId", 0L) > CACHE_TTL_MS
        if (models.isEmpty() || stale) {
            try {
                models = OpenAiHttp.listFreeModels(def, apiKey(providerId)!!)
                if (models.isNotEmpty()) saveModels(providerId, models)
            } catch (e: Throwable) {
                if (models.isEmpty()) throw e
            }
        }
        if (models.isEmpty()) throw AiProviderException(providerId, null, 404, false, message = "Daftar model gratis kosong. Tekan Perbarui model di Pengaturan.")

        val selectedId = selectedModelId(providerId, models)
        val ordered = buildList {
            models.firstOrNull { it.id == selectedId }?.let { add(it) }
            models.filterNot { it.id == selectedId }.forEach { add(it) }
        }.distinctBy { it.id }
        return AiRoute(
            providerId = providerId,
            models = ordered.map { it.toModel(providerId) },
            automaticFallback = autoFallback(),
        )
    }

    private fun selectedModelId(providerId: String, models: List<OnlineModelInfo> = cachedModels(providerId)): String {
        val stored = prefs.getString("model_$providerId", null)
        if (stored != null && models.any { it.id == stored }) return stored
        return models.firstOrNull()?.id.orEmpty()
    }

    private fun saveModels(providerId: String, models: List<OnlineModelInfo>) {
        val arr = JSONArray().apply { models.forEach { put(it.toJson()) } }
        prefs.edit()
            .putString("models_$providerId", arr.toString())
            .putLong("models_ts_$providerId", System.currentTimeMillis())
            .apply()
    }

    private fun cachedModels(providerId: String): List<OnlineModelInfo> {
        val raw = prefs.getString("models_$providerId", null) ?: return emptyList()
        return runCatching {
            val arr = JSONArray(raw)
            buildList { for (i in 0 until arr.length()) add(OnlineModelInfo.fromJson(arr.getJSONObject(i))) }
        }.getOrElse { emptyList() }
    }

    fun adapters(): List<AiProvider> = DEFINITIONS.map { OpenAiCompatibleProvider(it, ::apiKey) }
}

class OpenAiCompatibleProvider(
    private val definition: OnlineProviderDefinition,
    private val keyProvider: (String) -> String?,
) : AiProvider {
    override val id: String = definition.id
    override val capabilities = AiProviderCapabilities(streaming = true, offline = false, vision = true, tools = true, reasoning = true)

    override suspend fun prepare(model: AiModelRef, context: AiContext) {
        if (keyProvider(id).isNullOrBlank()) throw AiProviderException(id, model.id, 401, false, message = "API key ${definition.name} belum dipasang")
    }

    override fun stream(request: AiGenerationRequest): Flow<String> = flow {
        val key = keyProvider(id) ?: throw AiProviderException(id, request.model.id, 401, false, message = "API key ${definition.name} belum dipasang")
        OpenAiHttp.streamChat(definition, key, request) { emit(it) }
    }

    override suspend fun unload() = Unit
    override fun isWarm(model: AiModelRef, context: AiContext): Boolean = true
}

private object OpenAiHttp {
    suspend fun listFreeModels(def: OnlineProviderDefinition, key: String): List<OnlineModelInfo> = withContext(Dispatchers.IO) {
        val obj = requestJson(def, key, "GET", def.modelsPath, null, null)
        val data = obj.optJSONArray("data") ?: obj.optJSONArray("models") ?: JSONArray()
        val parsed = mutableListOf<OnlineModelInfo>()
        for (i in 0 until data.length()) {
            val item = data.optJSONObject(i) ?: continue
            parseModel(def, item)?.let { parsed += it }
        }
        val unique = parsed.distinctBy { it.id }
        when (def.strategy) {
            FreeModelStrategy.OPENROUTER_ZERO_PRICE -> {
                val router = OnlineModelInfo("openrouter/free", "OpenRouter Free Router (otomatis)", 32_768, 1_024)
                listOf(router) + unique.filterNot { it.id == router.id }.sortedByDescending { qualityScore(it.id) }
            }
            else -> unique.sortedByDescending { qualityScore(it.id) }
        }
    }

    suspend fun probe(def: OnlineProviderDefinition, key: String, model: OnlineModelInfo) = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("model", model.id)
            .put("stream", false)
            .put("max_tokens", 4)
            .put("messages", JSONArray().put(JSONObject().put("role", "user").put("content", "Reply OK")))
        requestJson(def, key, "POST", "/chat/completions", body, model.id)
        Unit
    }

    // Keep Flow emissions in the collector coroutine. Emitting from withContext(IO)
    // violates Flow context preservation and can crash streaming at runtime.
    suspend fun streamChat(def: OnlineProviderDefinition, key: String, request: AiGenerationRequest, emit: suspend (String) -> Unit) {
        val effectiveUser = if (request.context.runtimeContext.isNotBlank()) {
            "[PRIVATE RUNTIME CONTEXT]\n${request.context.runtimeContext}\n[END PRIVATE RUNTIME CONTEXT]\n${request.userMessage}"
        } else request.userMessage
        val body = JSONObject()
            .put("model", request.model.id)
            .put("stream", true)
            .put("max_tokens", request.predictLength.coerceAtMost(request.model.maxOutputTokens))
            .put("messages", JSONArray()
                .put(JSONObject().put("role", "system").put("content", request.context.systemPrompt))
                .put(JSONObject().put("role", "user").put("content", effectiveUser)))

        val conn = openConnection(def, key, "POST", "/chat/completions")
        conn.doOutput = true
        conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val code = conn.responseCode
        if (code !in 200..299) throw httpError(def, request.model.id, conn, code)
        try {
            BufferedReader(InputStreamReader(conn.inputStream, Charsets.UTF_8)).use { reader ->
                while (true) {
                    val line = reader.readLine() ?: break
                    if (!line.startsWith("data:")) continue
                    val payload = line.removePrefix("data:").trim()
                    if (payload.isBlank() || payload == "[DONE]") continue
                    val event = runCatching { JSONObject(payload) }.getOrNull() ?: continue
                    event.optJSONObject("error")?.let { throw eventError(def, request.model.id, it, conn) }
                    val choice = event.optJSONArray("choices")?.optJSONObject(0) ?: continue
                    val delta = choice.optJSONObject("delta")
                    val content = delta?.opt("content")
                    if (content is String && content.isNotEmpty()) emit(content)
                }
            }
        } catch (e: AiProviderException) {
            throw e
        } catch (e: Throwable) {
            throw AiProviderException(def.id, request.model.id, 503, true, message = "Koneksi streaming ${def.name} terputus", cause = e)
        } finally {
            conn.disconnect()
        }
    }

    private fun parseModel(def: OnlineProviderDefinition, item: JSONObject): OnlineModelInfo? {
        val id = item.optString("id", item.optString("name").removePrefix("models/"))
        if (id.isBlank()) return null
        val lower = id.lowercase(Locale.ROOT)
        val excluded = listOf("embedding", "whisper", "tts", "audio", "image", "guard", "moderation", "orpheus")
        if (excluded.any { lower.contains(it) }) return null

        val allowed = when (def.strategy) {
            FreeModelStrategy.OPENROUTER_ZERO_PRICE -> {
                if (id == "openrouter/free" || id.endsWith(":free")) true
                else {
                    val pricing = item.optJSONObject("pricing")
                    val prompt = pricing?.optString("prompt")?.toDoubleOrNull()
                    val completion = pricing?.optString("completion")?.toDoubleOrNull()
                    val request = pricing?.optString("request")?.toDoubleOrNull()
                    prompt == 0.0 && completion == 0.0 && (request == null || request == 0.0)
                }
            }
            FreeModelStrategy.GROQ_FREE_PLAN -> id in setOf(
                "groq/compound", "groq/compound-mini", "llama-3.1-8b-instant", "llama-3.3-70b-versatile",
                "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b",
            )
            FreeModelStrategy.GEMINI_FREE_TIER ->
                lower.contains("flash") && !lower.contains("live") && !lower.contains("image")
        }
        if (!allowed) return null

        val architecture = item.optJSONObject("architecture")
        val inputModalities = architecture?.optJSONArray("input_modalities")
        val supported = item.optJSONArray("supported_parameters")
        val topProvider = item.optJSONObject("top_provider")
        val context = sequenceOf(
            item.optInt("context_length", 0), item.optInt("context_window", 0), item.optInt("input_token_limit", 0),
            topProvider?.optInt("context_length", 0) ?: 0,
        ).firstOrNull { it > 0 } ?: if (def.id == "gemini") 1_000_000 else 32_768
        val maxOutput = sequenceOf(
            item.optInt("max_completion_tokens", 0), item.optInt("output_token_limit", 0),
            topProvider?.optInt("max_completion_tokens", 0) ?: 0,
        ).firstOrNull { it > 0 } ?: 1_024
        val name = item.optString("name", item.optString("display_name", id)).removePrefix("models/")
        return OnlineModelInfo(
            id = id.removePrefix("models/"),
            name = name.ifBlank { id },
            contextWindow = context.coerceAtLeast(4_096),
            maxOutputTokens = maxOutput.coerceIn(256, 16_384),
            vision = inputModalities?.let { arr -> (0 until arr.length()).any { arr.optString(it) == "image" } } ?: false,
            tools = supported?.let { arr -> (0 until arr.length()).any { arr.optString(it).contains("tool") } } ?: false,
            reasoning = lower.contains("reason") || lower.contains("thinking") || lower.contains("gpt-oss") || lower.contains("qwen"),
        )
    }

    private fun qualityScore(id: String): Int {
        val x = id.lowercase(Locale.ROOT)
        return when {
            x == "openrouter/free" -> 10_000
            x.contains("qwen3.6") -> 9_000
            x.contains("gpt-oss-120b") -> 8_800
            x.contains("70b") || x.contains("nemotron") -> 8_500
            x.contains("gpt-oss-20b") -> 8_000
            x.contains("flash") && !x.contains("lite") -> 7_800
            x.contains("flash-lite") -> 7_500
            x.contains("8b") -> 6_500
            else -> 5_000
        }
    }

    private fun requestJson(
        def: OnlineProviderDefinition,
        key: String,
        method: String,
        path: String,
        body: JSONObject?,
        modelId: String?,
    ): JSONObject {
        val conn = openConnection(def, key, method, path)
        if (body != null) {
            conn.doOutput = true
            conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val raw = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        if (code !in 200..299) {
            val error = httpError(def, modelId, conn, code, raw)
            conn.disconnect()
            throw error
        }
        conn.disconnect()
        return if (raw.isBlank()) JSONObject() else JSONObject(raw)
    }

    private fun openConnection(def: OnlineProviderDefinition, key: String, method: String, path: String): HttpURLConnection {
        return (URL(def.baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 15_000
            readTimeout = 90_000
            setRequestProperty("Authorization", "Bearer $key")
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "application/json, text/event-stream")
            setRequestProperty("User-Agent", "Furina-Android/4.1")
            if (def.id == "openrouter") {
                setRequestProperty("HTTP-Referer", "https://furina-pi.vercel.app")
                setRequestProperty("X-Title", "Furina")
            }
        }
    }

    private fun httpError(def: OnlineProviderDefinition, modelId: String?, conn: HttpURLConnection, code: Int, rawOverride: String? = null): AiProviderException {
        val raw = rawOverride ?: conn.errorStream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        val message = errorMessage(raw).ifBlank { "HTTP $code" }
        val retry = conn.getHeaderField("Retry-After")?.toLongOrNull()
        return AiProviderException(def.id, modelId, code, recoverable(code), retry, "${def.name}: $message")
    }

    private fun eventError(def: OnlineProviderDefinition, modelId: String?, error: JSONObject, conn: HttpURLConnection): AiProviderException {
        val code = when (val rawCode = error.opt("code")) {
            is Number -> rawCode.toInt()
            is String -> rawCode.toIntOrNull() ?: 503
            else -> error.optInt("status", 503)
        }
        val message = error.optString("message", "Provider menghentikan generasi")
        return AiProviderException(def.id, modelId, code, recoverable(code), conn.getHeaderField("Retry-After")?.toLongOrNull(), "${def.name}: $message")
    }

    private fun errorMessage(raw: String): String = runCatching {
        val obj = JSONObject(raw)
        val error = obj.optJSONObject("error")
        error?.optString("message")?.takeIf { it.isNotBlank() }
            ?: error?.optString("status")?.takeIf { it.isNotBlank() }
            ?: obj.optString("message")
    }.getOrDefault(raw.take(400))

    private fun recoverable(code: Int): Boolean = code in setOf(402, 404, 408, 409, 429, 498, 500, 502, 503, 504, 524, 529)
}
