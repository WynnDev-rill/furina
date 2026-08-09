package com.wynndev.furina

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

class ModelDownloadManager(private val context: Context) {
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
        }

        val target = modelFile(spec)
        if (target.exists()) target.delete()
        prefs.edit().remove("verified:${spec.id}").apply()

        val request = DownloadManager.Request(Uri.parse(spec.downloadUrl))
            .setTitle(spec.displayName)
            .setDescription("Mengunduh model AI Furina di latar belakang")
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
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
        modelFile(spec).delete()
        return status(spec)
    }

    @Synchronized
    fun delete(spec: ModelSpec): JSONObject {
        val id = prefs.getLong("download:${spec.id}", -1L)
        if (id > 0L) downloads.remove(id)
        prefs.edit().remove("download:${spec.id}").remove("verified:${spec.id}").apply()
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

        val verified = prefs.getString("verified:${spec.id}", null) == spec.sha256
        return JSONObject()
            .put("id", spec.id)
            .put("state", state)
            .put("downloadedBytes", downloaded)
            .put("totalBytes", total)
            .put("progress", if (total > 0L) downloaded.toDouble() / total.toDouble() else 0.0)
            .put("verified", verified)
            .put("reason", reason)
            .put("path", if (file.exists()) file.absolutePath else "")
    }

    fun verify(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): Boolean {
        val file = modelFile(spec)
        if (!file.exists() || file.length() == 0L) return false
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
        if (ok) prefs.edit().putString("verified:${spec.id}", spec.sha256).apply()
        return ok
    }
}
