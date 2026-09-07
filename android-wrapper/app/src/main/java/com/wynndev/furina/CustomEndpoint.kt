package com.wynndev.furina

import java.net.URI

/** Transport policy is shared by configuration, probes, and chat requests. */
internal object CustomEndpoint {
    fun normalize(raw: String): String {
        val uri = try { URI(raw.trim()) } catch (_: Exception) { error("Alamat endpoint tidak valid") }
        val host = uri.host?.lowercase().orEmpty()
        require(host.isNotBlank() && uri.rawUserInfo == null && uri.rawQuery == null && uri.rawFragment == null) {
            "Gunakan alamat server tanpa kredensial, query, atau fragmen"
        }
        require(uri.scheme == "https" || (uri.scheme == "http" && host in setOf("127.0.0.1", "localhost"))) {
            "Gunakan HTTPS. HTTP hanya tersedia untuk server di perangkat ini."
        }
        require(uri.port == -1 || uri.port in 1..65535) { "Port endpoint tidak valid" }
        return uri.toASCIIString().trimEnd('/')
    }
}
