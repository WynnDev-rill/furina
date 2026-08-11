package com.wynndev.furina

import android.os.SystemClock
import java.time.Instant
import kotlinx.coroutines.flow.collect
import org.json.JSONArray
import org.json.JSONObject

/**
 * Runs the repository behavioral input manifest against the real local model without touching
 * user conversations, learned memory, relationship state, or background maintenance.
 *
 * The benchmark receives only synthetic setup turns. ContextEngine is consulted solely for the
 * canonical identity prompt; every persistence-derived field returned by build() is discarded
 * before the provider sees the request.
 */
class DeviceBehavioralBenchmark(
    private val contextEngine: ContextEngine,
    private val provider: LocalLlamaProvider,
    private val modelDownloads: ModelDownloadManager,
    private val selectedModelId: () -> String,
    private val onProgress: (requestId: String, completed: Int, total: Int) -> Unit = { _, _, _ -> },
) {
    suspend fun run(rawRequest: String): JSONObject {
        val request = JSONObject(rawRequest)
        val requestId = request.requireString("requestId", 120)
        require(REQUEST_ID.matches(requestId)) { "requestId benchmark tidak valid" }
        val targetCommit = request.requireString("targetCommit", 40).lowercase()
        require(COMMIT.matches(targetCommit)) { "target commit benchmark tidak valid" }
        val appCommit = BuildConfig.GIT_SHA.trim().lowercase()
        require(COMMIT.matches(appCommit)) { "Build APK belum memiliki commit provenance" }
        require(targetCommit == appCommit) { "Request benchmark bukan untuk build APK ini" }
        val benchmarkVersion = request.requireString("benchmarkVersion", 80)
        val expiresAt = Instant.parse(request.requireString("expiresAt", 80))
        require(expiresAt.isAfter(Instant.now())) { "Request benchmark sudah kedaluwarsa" }

        val inputs = request.getJSONObject("inputs")
        require(inputs.optInt("schemaVersion") == 1) { "Schema input benchmark tidak didukung" }
        require(inputs.optString("benchmarkVersion") == benchmarkVersion) { "Versi benchmark tidak cocok" }
        val scenarios = inputs.getJSONArray("scenarios")
        require(scenarios.length() in 1..128) { "Jumlah skenario benchmark tidak valid" }

        val spec = ModelCatalog.byId(selectedModelId()) ?: error("Model lokal benchmark tidak dikenal")
        require(modelDownloads.status(spec).optString("state") == "ready") {
            "Model lokal belum tersedia untuk benchmark"
        }
        val model = AiModelRef(
            providerId = provider.id,
            id = spec.id,
            displayName = spec.displayName,
            contextWindowTokens = 4_096,
            maxOutputTokens = 1_024,
            offline = true,
        )

        // identityPrompt is independent of synthetic scenario/session data. Build it once instead
        // of repeating persistence-backed ContextEngine work for every scenario.
        val identityPrompt = contextEngine.build(
            sessionId = "device-evidence:$requestId:identity",
            query = "",
            characterName = "Furina",
            customPersona = "",
            contextWindowTokens = model.contextWindowTokens,
        ).identityPrompt

        val scenarioResults = JSONArray()
        val benchmarkStarted = SystemClock.elapsedRealtime()
        val seenIds = mutableSetOf<String>()
        var warmBeforeBenchmark = false
        var capturedWarmState = false
        onProgress(requestId, 0, scenarios.length())
        try {
            for (index in 0 until scenarios.length()) {
                val scenario = scenarios.getJSONObject(index)
                require(!scenario.has("expect")) { "Judge expectation bocor ke input benchmark" }
                val scenarioId = scenario.requireString("scenarioId", 120)
                require(seenIds.add(scenarioId)) { "scenarioId benchmark duplikat" }
                val userText = scenario.requireString("user", 4_000)
                val setup = parseSetup(scenario.optJSONArray("setup") ?: JSONArray())
                val sessionId = "device-evidence:$requestId:$scenarioId"

                val context = AiContext(
                    sessionId = sessionId,
                    identityPrompt = identityPrompt,
                    summary = "",
                    relevantMemories = "",
                    relevantHistory = "",
                    recentHistory = setup.joinToString("\n") { message ->
                        when (message.role) {
                            AiRole.USER -> "USER: ${message.content}"
                            AiRole.ASSISTANT -> "ASSISTANT: ${message.content}"
                            AiRole.SYSTEM -> error("System setup tidak diizinkan dalam benchmark")
                        }
                    },
                    runtimeContext = "",
                )

                val startedAt = SystemClock.elapsedRealtime()
                val warmBeforePrepare = provider.isWarm(model, context)
                if (!capturedWarmState) {
                    warmBeforeBenchmark = warmBeforePrepare
                    capturedWarmState = true
                }

                // Every scenario has a unique sessionId. LocalLlamaProvider therefore crosses the
                // same setSystemPrompt boundary used for normal session switches, which resets
                // native chat/KV state in one pass. The previous throwaway+real double prepare
                // performed the same reset twice and doubled prompt-prefill work.
                provider.prepare(model, context)

                val preparedAt = SystemClock.elapsedRealtime()
                var firstTokenAt = 0L
                var emittedChunks = 0
                val output = StringBuilder()
                provider.stream(
                    AiGenerationRequest(
                        requestId = "$requestId:$scenarioId",
                        sessionId = sessionId,
                        model = model,
                        context = context,
                        userMessage = userText,
                        // Keep the same production safety horizon. Speed comes from eliminating
                        // redundant load/prefill work, not by truncating model answers.
                        predictLength = model.maxOutputTokens,
                    )
                ).collect { chunk ->
                    if (firstTokenAt == 0L) firstTokenAt = SystemClock.elapsedRealtime()
                    emittedChunks += 1
                    output.append(chunk)
                    require(output.length <= MAX_OUTPUT_CHARS) { "Output benchmark melebihi batas evidence" }
                }
                val finishedAt = SystemClock.elapsedRealtime()
                val finalText = output.toString().trim()
                require(finalText.isNotBlank()) { "Model tidak menghasilkan output benchmark" }
                val firstAt = if (firstTokenAt == 0L) finishedAt else firstTokenAt
                val decodeMs = (finishedAt - firstAt).coerceAtLeast(1L)

                scenarioResults.put(
                    JSONObject()
                        .put("scenarioId", scenarioId)
                        .put("output", finalText)
                        .put(
                            "metrics",
                            JSONObject()
                                .put("prepareMs", preparedAt - startedAt)
                                .put("firstTokenMs", firstAt - startedAt)
                                .put("durationMs", finishedAt - startedAt)
                                .put("streamChunkCount", emittedChunks)
                                .put("chunksPerSecond", emittedChunks * 1000.0 / decodeMs)
                                .put("warmBeforePrepare", warmBeforePrepare)
                        )
                )
                onProgress(requestId, index + 1, scenarios.length())
            }
        } finally {
            // Preserve already-mapped GGUF weights when the user's model was warm before capture.
            // Only conversation/KV state is cleared. If the model had to be cold-loaded solely for
            // evidence, retain the old memory behavior and unload it after capture.
            if (warmBeforeBenchmark) {
                if (!provider.resetConversationStateKeepingModel()) provider.unload()
            } else {
                provider.unload()
            }
        }
        val benchmarkFinished = SystemClock.elapsedRealtime()

        return JSONObject()
            .put("schemaVersion", 1)
            .put("requestId", requestId)
            .put("recordedAt", Instant.now().toString())
            .put("commit", appCommit)
            .put("benchmarkVersion", benchmarkVersion)
            .put("actualModelRun", true)
            .put(
                "model",
                JSONObject()
                    .put("provider", provider.id)
                    .put("identifier", spec.id)
                    .put("quantization", quantization(spec))
                    .put("contextSize", model.contextWindowTokens)
            )
            .put("scenarios", scenarioResults)
            .put(
                "runtime",
                JSONObject()
                    .put("scenarioCount", scenarioResults.length())
                    .put("totalDurationMs", benchmarkFinished - benchmarkStarted)
                    .put("reusedWarmModel", warmBeforeBenchmark)
                    .put("scenarioResetStrategy", "single-session-switch")
            )
            .put(
                "privacy",
                JSONObject()
                    .put("syntheticInputsOnly", true)
                    .put("containsSecrets", false)
                    .put("containsPersonalConversation", false)
                    .put("persistedToUserMemory", false)
            )
    }

    private fun parseSetup(raw: JSONArray): List<AiMessage> {
        require(raw.length() <= 32) { "Setup benchmark terlalu panjang" }
        return buildList {
            for (index in 0 until raw.length()) {
                val item = raw.getJSONObject(index)
                val role = when (item.requireString("role", 24).lowercase()) {
                    "user" -> AiRole.USER
                    "assistant" -> AiRole.ASSISTANT
                    else -> error("Role setup benchmark tidak diizinkan")
                }
                val content = item.requireString("content", 4_000)
                add(AiMessage(role = role, content = content))
            }
        }
    }

    private fun JSONObject.requireString(key: String, maxLength: Int): String {
        val value = optString(key).trim()
        require(value.isNotEmpty() && value.length <= maxLength) { "$key benchmark tidak valid" }
        return value
    }

    private fun quantization(spec: ModelSpec): String = when {
        spec.id.contains("q4km", ignoreCase = true) || spec.fileName.contains("Q4_K_M", ignoreCase = true) -> "Q4_K_M"
        else -> "unknown"
    }

    private companion object {
        val REQUEST_ID = Regex("^[A-Za-z0-9._:-]{8,120}$")
        val COMMIT = Regex("^[0-9a-f]{40}$")
        const val MAX_OUTPUT_CHARS = 12_000
    }
}
