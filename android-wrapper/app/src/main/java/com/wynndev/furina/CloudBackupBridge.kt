package com.wynndev.furina

import android.content.Intent
import android.net.Uri
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import java.io.ByteArrayOutputStream
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONObject

class CloudBackupBridge(
    private val activity: MainActivity,
    private val webView: WebView,
    private val backupManager: BackupManager,
    private val withAiPaused: suspend (suspend () -> Unit) -> Unit,
) {
    private val scope = kotlinx.coroutines.CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val restoreBuffers = ConcurrentHashMap<String, ByteArrayOutputStream>()

    @JavascriptInterface
    fun openExternal(rawUrl: String) {
        val uri = runCatching { Uri.parse(rawUrl) }.getOrNull() ?: return
        if (!isTrustedOAuthUrl(uri)) return
        activity.runOnUiThread {
            runCatching { activity.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
        }
    }

    @JavascriptInterface
    fun prepareBackup(requestId: String) {
        if (requestId.isBlank()) return
        scope.launch {
            try {
                // Same FURINA2 snapshot as local backup: DB + learned relationship/reflection
                // state. API keys remain outside portable backup by design.
                val encrypted = backupManager.createEncryptedSnapshotBytes(MAX_BACKUP_BYTES)
                val encoded = Base64.encodeToString(encrypted, Base64.NO_WRAP)
                val fileName = "Furina-cloud-${System.currentTimeMillis()}.furina"
                eval(
                    "window.__furinaCloudBackupStart && window.__furinaCloudBackupStart(" +
                        "${JSONObject.quote(requestId)}, ${JSONObject.quote(fileName)}, ${encrypted.size})"
                )
                var offset = 0
                while (offset < encoded.length) {
                    val end = (offset + JS_CHUNK_CHARS).coerceAtMost(encoded.length)
                    val chunk = encoded.substring(offset, end)
                    val done = end >= encoded.length
                    eval(
                        "window.__furinaCloudBackupChunk && window.__furinaCloudBackupChunk(" +
                            "${JSONObject.quote(requestId)}, ${JSONObject.quote(chunk)}, $done)"
                    )
                    offset = end
                }
            } catch (e: Throwable) {
                emitError(requestId, e.message ?: "Backup cloud gagal disiapkan")
            }
        }
    }

    @JavascriptInterface
    fun beginRestore(requestId: String) {
        if (requestId.isBlank()) return
        restoreBuffers.remove(requestId)?.close()
        restoreBuffers[requestId] = ByteArrayOutputStream()
    }

    @JavascriptInterface
    fun appendRestoreChunk(requestId: String, base64Chunk: String) {
        val output = restoreBuffers[requestId] ?: return
        val bytes = Base64.decode(base64Chunk, Base64.NO_WRAP)
        synchronized(output) {
            require(output.size().toLong() + bytes.size <= MAX_BACKUP_BYTES + 1024L * 1024L) { "Backup cloud terlalu besar" }
            output.write(bytes)
        }
    }

    @JavascriptInterface
    fun finishRestore(requestId: String) {
        val output = restoreBuffers.remove(requestId) ?: return
        scope.launch {
            try {
                val encrypted = synchronized(output) { output.toByteArray() }
                output.close()
                withAiPaused {
                    backupManager.restoreEncryptedSnapshotBytes(encrypted)
                }
                emitRestore(requestId, true, "Backup cloud berhasil dipulihkan")
                eval("window.__furinaNativeRestored && window.__furinaNativeRestored()")
            } catch (e: Throwable) {
                runCatching { output.close() }
                emitRestore(requestId, false, e.message ?: "Restore cloud gagal")
            }
        }
    }

    fun destroy() {
        restoreBuffers.values.forEach { runCatching { it.close() } }
        restoreBuffers.clear()
        scope.cancel()
    }

    private fun isTrustedOAuthUrl(uri: Uri): Boolean =
        uri.scheme.equals("https", ignoreCase = true) &&
            uri.host.equals(SUPABASE_HOST, ignoreCase = true) &&
            uri.path?.startsWith("/auth/v1/authorize") == true

    private fun emitError(requestId: String, message: String) {
        eval(
            "window.__furinaCloudBackupError && window.__furinaCloudBackupError(" +
                "${JSONObject.quote(requestId)}, ${JSONObject.quote(message)})"
        )
    }

    private fun emitRestore(requestId: String, success: Boolean, message: String) {
        eval(
            "window.__furinaCloudRestoreDone && window.__furinaCloudRestoreDone(" +
                "${JSONObject.quote(requestId)}, $success, ${JSONObject.quote(message)})"
        )
    }

    private fun eval(script: String) {
        webView.post { if (!webView.isDestroyed) webView.evaluateJavascript(script, null) }
    }

    private companion object {
        private const val SUPABASE_HOST = "fxebamfwewsvtscrbwxk.supabase.co"
        private const val JS_CHUNK_CHARS = 196_608
        private const val MAX_BACKUP_BYTES = 50L * 1024L * 1024L
    }
}
