package com.wynndev.furina

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.os.StatFs
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

class ModelDownloadManager(private val context: Context) {
    companion object {
        private const val DOWNLOAD_HEADROOM_BYTES = 512L * 1024L * 1024L
    }

    private val downloads = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    private val prefs = context.getSharedPreferences("furina_models", Context.MODE_PRIVATE)
    private val modelDir = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models").apply { mkdirs() }

    fun modelFile(spec: ModelSpec): File = File(modelDir, spec.fileName)

    @Synchronized
    fun start(spec: ModelSpec): JSONObject {
        val existingId = prefs.getLong("download:${spec.id}", -1L)
        if (existingId > 0L) {
            val s = status(spec)
            if (s.optString("state") == "downloading" || s.optString("state") == "paused") return s
            downloads.remove(existingId)
        }

        val target = modelFile(spec)
        require(!target.exists() || target.delete()) {
            "File model lama tidak dapat dibersihkan. Coba hapus model lalu ulangi."
        }
        val available = StatFs(modelDir.absolutePath).availableBytes
        require(available >= spec.expectedBytes + DOWNLOAD_HEADROOM_BYTES) {
            "Penyimpanan tidak cukup. Sisakan setidaknya ${formatGiB(spec.expectedBytes + DOWNLOAD_HEADROOM_BYTES)}."
        }
        prefs.edit().remove("verified:${spec.id}").remove("verification_error:${spec.id}").apply()

        val request = DownloadManager.Request(Uri.parse(spec.downloadUrl))
            .setTitle(spec.displayName)
            .setDescription("Mengunduh model AI Furina di latar belakang")
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .addRequestHeader("Accept", "application/octet-stream")
            .addRequestHeader("User-Agent", "FurinaAndroid/4.0")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, "models/${spec.fileName}")

        val id = downloads.enqueue(request)
        prefs.edit().putLong("download:${spec.id}", id).apply()
        return status(spec)
    }

    @Synchronized
    fun cancel(spec: ModelSpec): JSONObject {
        val id = prefs.getLong("download:${spec.id}", -1L)
        if (id > 0L) downloads.remove(id)
        prefs.edit().remove("download:${spec.id}").remove("verified:${spec.id}").apply()
        prefs.edit().remove("verification_error:${spec.id}").apply()
        modelFile(spec).delete()
        return status(spec)
    }

    @Synchronized
    fun delete(spec: ModelSpec): JSONObject {
        val id = prefs.getLong("download:${spec.id}", -1L)
        if (id > 0L) downloads.remove(id)
        prefs.edit().remove("download:${spec.id}").remove("verified:${spec.id}").apply()
        prefs.edit().remove("verification_error:${spec.id}").apply()
        modelFile(spec).delete()
        return status(spec)
    }

    fun status(spec: ModelSpec): JSONObject {
        val file = modelFile(spec)
        val id = prefs.getLong("download:${spec.id}", -1L)
        var state = if (file.exists() && file.length() > 0) "ready" else "not_downloaded"
        var downloaded = if (file.exists()) file.length() else 0L
        var total = if (spec.expectedBytes > 0) spec.expectedBytes else 0L
        var reason = 0

        if (id > 0L) {
            val cursor = downloads.query(DownloadManager.Query().setFilterById(id))
            cursor?.use {
                if (it.moveToFirst()) {
                    val status = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    downloaded = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)).coerceAtLeast(0L)
                    val reportedTotal = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                    if (reportedTotal > 0L) total = reportedTotal
                    reason = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                    state = when (status) {
                        DownloadManager.STATUS_PENDING, DownloadManager.STATUS_RUNNING -> "downloading"
                        DownloadManager.STATUS_PAUSED -> "paused"
                        DownloadManager.STATUS_SUCCESSFUL -> if (file.exists()) "ready" else "missing"
                        DownloadManager.STATUS_FAILED -> "failed"
                        else -> state
                    }
                }
            }
        }

        val sizeMatches = !file.exists() || file.length() == spec.expectedBytes
        val verificationError = prefs.getString("verification_error:${spec.id}", null)
        val transferActive = state == "downloading" || state == "paused"
        val transferFailed = state == "failed"
        if (!transferActive && !transferFailed && file.exists() && !sizeMatches) state = "corrupt"
        if (!transferActive && !transferFailed && verificationError != null) state = "corrupt"
        val verified = sizeMatches && prefs.getString("verified:${spec.id}", null) == spec.sha256
        return JSONObject()
            .put("id", spec.id)
            .put("state", state)
            .put("downloadedBytes", downloaded)
            .put("totalBytes", total)
            .put("progress", if (total > 0L) downloaded.toDouble() / total.toDouble() else 0.0)
            .put("verified", verified)
            .put("reason", reason)
            .put("availableBytes", StatFs(modelDir.absolutePath).availableBytes)
            .put("error", verificationError ?: "")
            .put("path", if (file.exists()) file.absolutePath else "")
    }

    fun verify(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): Boolean {
        val file = modelFile(spec)
        if (!file.exists() || file.length() == 0L) return false
        if (file.length() != spec.expectedBytes) {
            prefs.edit().putString("verification_error:${spec.id}", "Ukuran file model tidak cocok").apply()
            return false
        }
        if (prefs.getString("verified:${spec.id}", null) == spec.sha256) return true

        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(8 * 1024 * 1024)
        var readTotal = 0L
        FileInputStream(file).use { input ->
            while (true) {
                val count = input.read(buffer)
                if (count <= 0) break
                digest.update(buffer, 0, count)
                readTotal += count
                progress?.invoke(readTotal, file.length())
            }
        }
        val actual = digest.digest().joinToString("") { "%02x".format(it) }
        val ok = actual.equals(spec.sha256, ignoreCase = true)
        if (ok) {
            prefs.edit().putString("verified:${spec.id}", spec.sha256).remove("verification_error:${spec.id}").apply()
        } else {
            prefs.edit().putString("verification_error:${spec.id}", "Checksum model tidak cocok").apply()
        }
        return ok
    }

    private fun formatGiB(bytes: Long): String = String.format(java.util.Locale.US, "%.1f GB", bytes / 1024.0 / 1024.0 / 1024.0)
}
