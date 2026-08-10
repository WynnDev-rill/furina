package com.wynndev.furina

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class OnlineProviderSpec(
    val id: String,
    val displayName: String,
    val baseUrl: String,
    val keyHint: String,
    val description: String,
)

data class OnlineModel(
    val id: String,
    val displayName: String,
    val contextWindowTokens: Int,
    val maxOutputTokens: Int = 2_048,
) {
    fun toAiModelRef(providerId: String): AiModelRef = AiModelRef(
        providerId = providerId,
        id = id,
        displayName = displayName,
        contextWindowTokens = contextWindowTokens.coerceAtLeast(2_048),
        maxOutputTokens = maxOutputTokens.coerceIn(256, 16_384),
        offline = false,
    )

    fun toJson(): JSONObject = JSONObject()
        .put("id", id)
        .put("name", displayName)
        .put("contextWindow", contextWindowTokens)
        .put("maxOutputTokens", maxOutputTokens)
}

object OnlineProviderCatalog {
    val providers = listOf(
        OnlineProviderSpec(
            id = "openrouter",
            displayName = "OpenRouter",
            baseUrl = "https://openrouter.ai/api/v1",
            keyHint = "sk-or-v1-…",
            description = "Banyak model dalam satu API. Hanya varian gratis yang dipilih otomatis.",
        ),
        OnlineProviderSpec(
            id = "gemini",
            displayName = "Google Gemini",
            baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai",
            keyHint = "AIza… / auth key",
            description = "Gemini API melalui endpoint OpenAI-compatible. Fallback dibatasi ke model free-tier yang dikenal.",
        ),
        OnlineProviderSpec(
            id = "groq",
            displayName = "Groq",
            baseUrl = "https://api.groq.com/openai/v1",
            keyHint = "gsk_…",
            description = "Inferensi sangat cepat. Fallback dibatasi ke model chat yang tercantum pada Free Plan.",
        ),
    )

    fun byId(id: String?): OnlineProviderSpec? = providers.firstOrNull { it.id == id }

    /** Conservative allow-list for providers whose model endpoint does not expose pricing. */
    fun isKnownFreeTierModel(providerId: String, modelId: String): Boolean {
        val id = modelId.lowercase()
        return when (providerId) {
            "gemini" -> {
                val allowed = listOf(
                    "gemini-3.6-flash",
                    "gemini-3.5-flash",
                    "gemini-3-flash-preview",
                    "gemini-2.5-flash",
                    "gemini-2.5-flash-lite",
                )
                allowed.any { id == it || id.startsWith("$it-") } &&
                    !id.contains("image") && !id.contains("live") && !id.contains("tts")
            }
            "groq" -> id in setOf(
                "groq/compound",
                "groq/compound-mini",
                "llama-3.1-8b-instant",
                "llama-3.3-70b-versatile",
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "qwen/qwen3.6-27b",
            )
            else -> false
        }
    }
}

class OnlineAiConfigStore(context: Context) {
    companion object {
        const val MODE_LOCAL = "local"
        const val MODE_ONLINE = "online"
    }

    private val prefs = context.applicationContext.getSharedPreferences("furina_online_ai", Context.MODE_PRIVATE)

    fun mode(): String = prefs.getString("mode", MODE_LOCAL).let { if (it == MODE_ONLINE) MODE_ONLINE else MODE_LOCAL }
    fun setMode(value: String) = prefs.edit().putString("mode", if (value == MODE_ONLINE) MODE_ONLINE else MODE_LOCAL).apply()

    fun selectedProvider(): String = prefs.getString("provider", "openrouter") ?: "openrouter"
    fun setSelectedProvider(id: String) {
        require(OnlineProviderCatalog.byId(id) != null) { "Provider tidak dikenal" }
        prefs.edit().putString("provider", id).apply()
    }

    fun autoFallback(): Boolean = prefs.getBoolean("auto_fallback", true)
    fun setAutoFallback(enabled: Boolean) = prefs.edit().putBoolean("auto_fallback", enabled).apply()

    fun selectedModel(providerId: String): String? = prefs.getString("model:$providerId", null)
    fun setSelectedModel(providerId: String, modelId: String?) {
        val editor = prefs.edit()
        if (modelId.isNullOrBlank()) editor.remove("model:$providerId") else editor.putString("model:$providerId", modelId)
        editor.apply()
    }

    fun markValidated(providerId: String, keyFingerprint: String) {
        prefs.edit().putString("validated_key:$providerId", keyFingerprint).apply()
    }

    fun isValidated(providerId: String, keyFingerprint: String?): Boolean {
        if (keyFingerprint.isNullOrBlank()) return false
        return prefs.getString("validated_key:$providerId", null) == keyFingerprint
    }

    fun clearValidation(providerId: String) {
        prefs.edit().remove("validated_key:$providerId").apply()
    }
}

/**
 * API keys are encrypted with a non-exportable AES key stored in Android Keystore.
 * Only ciphertext and IV are persisted in SharedPreferences; keys are deliberately
 * excluded from Furina's portable backups.
 */
class SecureApiKeyStore(context: Context) {
    companion object {
        private const val KEYSTORE = "AndroidKeyStore"
        private const val ALIAS = "furina_online_api_keys_v1"
        private const val PREFS = "furina_online_api_keys_secure"
    }

    private val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    @Synchronized
    fun put(providerId: String, apiKey: String) {
        val clean = apiKey.trim()
        require(clean.length >= 8) { "API key terlalu pendek" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(clean.toByteArray(Charsets.UTF_8))
        val payload = JSONObject()
            .put("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .put("data", Base64.encodeToString(encrypted, Base64.NO_WRAP))
        prefs.edit().putString(providerId, payload.toString()).apply()
    }

    @Synchronized
    fun get(providerId: String): String? {
        val raw = prefs.getString(providerId, null) ?: return null
        return try {
            val payload = JSONObject(raw)
            val iv = Base64.decode(payload.getString("iv"), Base64.NO_WRAP)
            val encrypted = Base64.decode(payload.getString("data"), Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
            String(cipher.doFinal(encrypted), Charsets.UTF_8)
        } catch (_: Throwable) {
            prefs.edit().remove(providerId).apply()
            null
        }
    }

    fun has(providerId: String): Boolean = get(providerId)?.isNotBlank() == true

    fun fingerprint(providerId: String): String? {
        val value = get(providerId) ?: return null
        val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8))
        return digest.take(12).joinToString("") { "%02x".format(it) }
    }

    fun remove(providerId: String) = prefs.edit().remove(providerId).apply()

    private fun key(): SecretKey {
        val store = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (store.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build(),
        )
        return generator.generateKey()
    }
}

fun onlineProvidersJson(
    config: OnlineAiConfigStore,
    keys: SecureApiKeyStore,
    cachedModels: (String) -> List<OnlineModel>,
): String {
    val providers = JSONArray()
    OnlineProviderCatalog.providers.forEach { spec ->
        val models = JSONArray()
        cachedModels(spec.id).forEach { models.put(it.toJson()) }
        val fingerprint = keys.fingerprint(spec.id)
        providers.put(
            JSONObject()
                .put("id", spec.id)
                .put("name", spec.displayName)
                .put("description", spec.description)
                .put("keyHint", spec.keyHint)
                .put("keyConfigured", fingerprint != null)
                .put("keyValidated", config.isValidated(spec.id, fingerprint))
                .put("selectedModel", config.selectedModel(spec.id) ?: "")
                .put("models", models),
        )
    }
    return JSONObject()
        .put("mode", config.mode())
        .put("selectedProvider", config.selectedProvider())
        .put("autoFallback", config.autoFallback())
        .put("providers", providers)
        .toString()
}
