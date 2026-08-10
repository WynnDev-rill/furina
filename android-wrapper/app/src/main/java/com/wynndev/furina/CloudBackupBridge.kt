package com.wynndev.furina

import android.content.Intent
import android.net.Uri
import android.util.Base64
import android.webkit.JavascriptInterface
import android.webkit.WebView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Cipher
import javax.crypto.CipherInputStream
import javax.crypto.CipherOutputStream
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

class CloudBackupBridge(
    private val activity: MainActivity,
    private val webView: WebView,
    private val store: MemoryStore,
    private val backupManager: BackupManager,
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
                val encrypted = createEncryptedBackup()
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
        synchronized(output) { output.write(bytes) }
    }

    @JavascriptInterface
    fun finishRestore(requestId: String) {
        val output = restoreBuffers.remove(requestId) ?: return
        scope.launch {
            try {
                val encrypted = synchronized(output) { output.toByteArray() }
                output.close()
                restoreEncryptedBackup(encrypted)
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

    private fun createEncryptedBackup(): ByteArray {
        store.checkpoint()
        val dbFile: File = store.databaseFile()
        require(dbFile.isFile) { "Database Furina belum tersedia" }
        val dbSize = dbFile.length()
        require(dbSize <= MAX_BACKUP_BYTES) { "Backup melebihi batas 50 MB" }

        val key = decodeKey(backupManager.getOrCreateRecoveryKey())
        val iv = ByteArray(12).also { SecureRandom().nextBytes(it) }
        val initialCapacity = (dbSize + 64L).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
        val raw = ByteArrayOutputStream(initialCapacity)
        raw.write(MAGIC)
        raw.write(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
        CipherOutputStream(raw, cipher).use { encrypted ->
            FileInputStream(dbFile).use { input ->
                copyStream(input, encrypted)
            }
        }
        return raw.toByteArray()
    }

    private fun restoreEncryptedBackup(encryptedBytes: ByteArray) {
        require(encryptedBytes.isNotEmpty()) { "Backup cloud kosong" }
        require(encryptedBytes.size.toLong() <= MAX_BACKUP_BYTES + 1024L * 1024L) { "Backup cloud terlalu besar" }
        val key = decodeKey(backupManager.getOrCreateRecoveryKey())
        val temp = File(activity.cacheDir, "furina-cloud-restore-${System.currentTimeMillis()}.db")
        try {
            ByteArrayInputStream(encryptedBytes).use { rawIn ->
                val header = ByteArray(MAGIC.size)
                require(rawIn.read(header) == header.size && header.contentEquals(MAGIC)) { "Bukan backup Furina yang didukung" }
                val iv = ByteArray(12)
                require(rawIn.read(iv) == iv.size) { "Backup rusak" }
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
                CipherInputStream(rawIn, cipher).use { decrypted ->
                    FileOutputStream(temp).use { output -> copyStream(decrypted, output) }
                }
            }
            FileInputStream(temp).use { input ->
                val sqliteHeader = ByteArray(16)
                require(input.read(sqliteHeader) == 16 && String(sqliteHeader, Charsets.US_ASCII).startsWith("SQLite format 3")) {
                    "Recovery key salah atau backup tidak valid"
                }
            }
            store.restoreFrom(temp)
        } finally {
            temp.delete()
        }
    }

    private fun copyStream(input: java.io.InputStream, output: java.io.OutputStream) {
        val buffer = ByteArray(1024 * 1024)
        while (true) {
            val count = input.read(buffer)
            if (count <= 0) break
            output.write(buffer, 0, count)
        }
    }

    private fun decodeKey(value: String): ByteArray {
        val bytes = Base64.decode(value.trim(), Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
        require(bytes.size == 32) { "Recovery key tidak valid" }
        return bytes
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
        private val MAGIC = "FURINA1".toByteArray(Charsets.US_ASCII)
        private const val JS_CHUNK_CHARS = 196_608
        private const val MAX_BACKUP_BYTES = 50L * 1024L * 1024L
    }
}
