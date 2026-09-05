/*
 * Protocol helpers adapted from EchoFlow ProviderHttpSupport.kt (MIT).
 * Copyright (c) 2026 Aditya Vardhan Sharma.
 * Modified for FurinaHub: org.json, no DNS probing, HTTPS-only external providers,
 * bounded errors; keep Furina's free-model policy and hidden reasoning filter.
 * Full license: assets/licenses/ECHOFLOW-LICENSE.txt.
 */
package com.wynndev.furina

import org.json.JSONArray
import org.json.JSONObject

internal object ProviderProtocol {
    fun parseModelIds(body: String): List<String> {
        val map = runCatching { JSONObject(body) }.getOrNull() ?: return emptyList()
        val items = map.optJSONArray("data") ?: map.optJSONArray("models") ?: return emptyList()
        return (0 until items.length()).mapNotNull { modelId(items.opt(it)) }.distinct()
    }

    fun modelId(item: Any?): String? = when (item) {
        is String -> item.trim().takeIf { it.isNotBlank() }
        is JSONObject -> listOf("id", "name", "model").firstNotNullOfOrNull { key ->
            item.optString(key).trim().takeIf { it.isNotBlank() && it != "null" }
        }
        else -> null
    }

    fun errorMessage(label: String, code: Int, body: String): String {
        val parsed = runCatching {
            val map = JSONObject(body)
            when (val error = map.opt("error")) {
                is String -> error
                is JSONObject -> error.optString("message")
                else -> map.optString("message")
            }.takeIf { it.isNotBlank() }
        }.getOrNull()
        return when (code) {
            401, 403 -> "$label menolak API key atau izin permintaan."
            404 -> "Endpoint atau model $label tidak ditemukan."
            429 -> "$label mencapai batas kuota. Coba lagi nanti."
            else -> parsed?.take(300) ?: "$label mengembalikan HTTP $code."
        }
    }

    fun contentText(value: Any?): String = when (value) {
        is String -> value
        is JSONArray -> buildString {
            for (i in 0 until value.length()) {
                val part = value.optJSONObject(i) ?: continue
                if (part.optString("type") == "text") append(part.optString("text"))
            }
        }
        else -> ""
    }
}
