package com.wynndev.furina

import android.content.Context
import org.json.JSONObject

/** Keeps provider selection, secrets and free-model discovery out of the WebView. */
class AiRuntimeController(context: Context) {
    val config = OnlineAiConfigStore(context)
    val keys = SecureApiKeyStore(context)
    val onlineProviders: Map<String, OpenAiCompatibleProvider> = OnlineProviderCatalog.providers.associate { spec ->
        spec.id to OpenAiCompatibleProvider(spec, keys, config)
    }

    fun settingsJson(): String = onlineProvidersJson(config, keys) { id -> onlineProviders[id]?.cachedModels().orEmpty() }

    fun setMode(mode: String) = config.setMode(mode)
    fun setProvider(providerId: String) = config.setSelectedProvider(providerId)
    fun setAutoFallback(enabled: Boolean) = config.setAutoFallback(enabled)

    fun setModel(providerId: String, modelId: String) {
        require(OnlineProviderCatalog.byId(providerId) != null) { "Provider tidak dikenal" }
        val cached = onlineProviders[providerId]?.cachedModels().orEmpty()
        require(cached.isEmpty() || cached.any { it.id == modelId }) { "Model gratis tidak dikenal" }
        config.setSelectedModel(providerId, modelId)
    }

    fun saveKey(providerId: String, apiKey: String) {
        require(OnlineProviderCatalog.byId(providerId) != null) { "Provider tidak dikenal" }
        config.clearValidation(providerId)
        keys.put(providerId, apiKey)
    }

    fun removeKey(providerId: String) {
        config.clearValidation(providerId)
        keys.remove(providerId)
        config.setSelectedModel(providerId, null)
    }

    suspend fun test(providerId: String): ProviderProbeResult {
        val provider = onlineProviders[providerId] ?: return ProviderProbeResult(false, "Provider tidak dikenal")
        val result = provider.testAndRefresh()
        val fingerprint = keys.fingerprint(providerId)
        if (result.success && fingerprint != null) config.markValidated(providerId, fingerprint)
        else config.clearValidation(providerId)
        return result
    }

    suspend fun refresh(providerId: String): ProviderProbeResult {
        val provider = onlineProviders[providerId] ?: return ProviderProbeResult(false, "Provider tidak dikenal")
        if (!keys.has(providerId)) return ProviderProbeResult(false, "API key belum disimpan")
        return try {
            val models = provider.discoverFreeModels(force = true)
            if (models.isEmpty()) ProviderProbeResult(false, "Tidak ada model gratis yang tersedia")
            else ProviderProbeResult(true, "${models.size} model gratis diperbarui", models)
        } catch (e: Throwable) {
            ProviderProbeResult(false, e.message ?: "Gagal memperbarui model")
        }
    }

    suspend fun resolve(localModel: ModelSpec): Pair<String, AiModelRef> {
        if (config.mode() != OnlineAiConfigStore.MODE_ONLINE) {
            return "local-llama" to AiModelRef(
                providerId = "local-llama",
                id = localModel.id,
                displayName = localModel.displayName,
                contextWindowTokens = 4_096,
                maxOutputTokens = 1_024,
                offline = true,
            )
        }

        val providerId = config.selectedProvider()
        val provider = onlineProviders[providerId] ?: error("Provider online tidak dikenal")
        val fingerprint = keys.fingerprint(providerId)
        if (fingerprint == null) error("Masukkan API key ${OnlineProviderCatalog.byId(providerId)?.displayName ?: providerId} terlebih dahulu")
        if (!config.isValidated(providerId, fingerprint)) error("Tes API key ${OnlineProviderCatalog.byId(providerId)?.displayName ?: providerId} terlebih dahulu")
        val models = provider.discoverFreeModels(force = false)
        if (models.isEmpty()) error("Tidak ada model gratis yang tersedia pada provider ini")
        val selectedId = config.selectedModel(providerId)
        val model = models.firstOrNull { it.id == selectedId } ?: models.first()
        if (selectedId != model.id) config.setSelectedModel(providerId, model.id)
        return providerId to model.toAiModelRef(providerId)
    }

    fun modeSummaryJson(): JSONObject {
        val mode = config.mode()
        val providerId = config.selectedProvider()
        val provider = OnlineProviderCatalog.byId(providerId)
        val fingerprint = keys.fingerprint(providerId)
        return JSONObject()
            .put("mode", mode)
            .put("provider", if (mode == OnlineAiConfigStore.MODE_ONLINE) providerId else "local-llama")
            .put("providerName", if (mode == OnlineAiConfigStore.MODE_ONLINE) provider?.displayName ?: providerId else "Lokal")
            .put("onlineReady", mode == OnlineAiConfigStore.MODE_ONLINE && config.isValidated(providerId, fingerprint))
            .put("autoFallback", config.autoFallback())
    }
}
