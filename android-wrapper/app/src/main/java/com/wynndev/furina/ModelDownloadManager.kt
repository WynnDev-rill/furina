package com.wynndev.furina

import android.content.Context
import android.os.Environment
import android.os.StatFs
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit

class ModelDownloadManager(private val context: Context) {
    companion object {
        private const val DOWNLOAD_HEADROOM_BYTES = 512L * 1024L * 1024L
    }

    private val workManager = WorkManager.getInstance(context.applicationContext)
    private val prefs = context.getSharedPreferences(ModelDownloadKeys.PREFS, Context.MODE_PRIVATE)
    private val modelDir = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models").apply { mkdirs() }

    fun modelFile(spec: ModelSpec): File = File(modelDir, spec.fileName)
    private fun partialFile(spec: ModelSpec): File = File(modelDir, "${spec.fileName}.part")
    private fun uniqueWork(spec: ModelSpec) = "furina-model-${spec.id}"

    @Synchronized
    fun start(spec: ModelSpec): JSONObject {
        migrateLegacyDownload(spec)
        val current = status(spec)
        if (current.optString("state") == "downloading") return current

        val target = modelFile(spec)
        require(!target.exists() || target.delete()) {
            "File model lama tidak dapat dibersihkan. Coba hapus model lalu ulangi."
        }
        val available = StatFs(modelDir.absolutePath).availableBytes
        val reusablePartial = partialFile(spec).length().coerceAtMost(spec.expectedBytes)
        require(available + reusablePartial >= spec.expectedBytes + DOWNLOAD_HEADROOM_BYTES) {
            "Penyimpanan tidak cukup. Sisakan setidaknya ${formatGiB(spec.expectedBytes + DOWNLOAD_HEADROOM_BYTES)}."
        }
        prefs.edit()
            .remove("cancelled:${spec.id}")
            .remove("verified:${spec.id}")
            .remove("verification_error:${spec.id}")
            .remove("error:${spec.id}")
            .putString("state:${spec.id}", "downloading")
            .putLong("downloaded:${spec.id}", partialFile(spec).length())
            .putLong("total:${spec.id}", spec.expectedBytes)
            .apply()

        val request = OneTimeWorkRequestBuilder<ModelDownloadWorker>()
            .setInputData(workDataOf(
                ModelDownloadKeys.KEY_MODEL_ID to spec.id,
                ModelDownloadKeys.KEY_MODEL_NAME to spec.displayName,
                ModelDownloadKeys.KEY_URL to spec.downloadUrl,
                ModelDownloadKeys.KEY_FILE_NAME to spec.fileName,
                ModelDownloadKeys.KEY_EXPECTED_BYTES to spec.expectedBytes,
            ))
            .setConstraints(Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .setRequiresStorageNotLow(true)
                .build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .addTag(uniqueWork(spec))
            .build()
        workManager.enqueueUniqueWork(uniqueWork(spec), ExistingWorkPolicy.REPLACE, request)
        prefs.edit().putString("worker:${spec.id}", request.id.toString()).apply()
        return status(spec)
    }

    @Synchronized
    fun cancel(spec: ModelSpec): JSONObject {
        prefs.edit().putBoolean("cancelled:${spec.id}", true).apply()
        workManager.cancelUniqueWork(uniqueWork(spec))
        prefs.getString("worker:${spec.id}", null)?.let { runCatching { workManager.cancelWorkById(UUID.fromString(it)) } }
        prefs.edit().remove("worker:${spec.id}").remove("download:${spec.id}").remove("verified:${spec.id}").apply()
        prefs.edit()
            .remove("verification_error:${spec.id}")
            .remove("state:${spec.id}")
            .remove("error:${spec.id}")
            .remove("downloaded:${spec.id}")
            .remove("total:${spec.id}")
            .apply()
        modelFile(spec).delete()
        partialFile(spec).delete()
        return status(spec)
    }

    @Synchronized
    fun delete(spec: ModelSpec): JSONObject {
        return cancel(spec)
    }

    fun status(spec: ModelSpec): JSONObject {
        val file = modelFile(spec)
        val partial = partialFile(spec)
        var state = prefs.getString("state:${spec.id}", null)
            ?: if (file.exists() && file.length() > 0) "ready" else if (partial.exists()) "paused" else "not_downloaded"
        val downloaded = when {
            file.exists() -> file.length()
            partial.exists() -> partial.length()
            else -> prefs.getLong("downloaded:${spec.id}", 0L)
        }
        val total = prefs.getLong("total:${spec.id}", spec.expectedBytes).coerceAtLeast(spec.expectedBytes)
        val reason = 0

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
            .put("error", verificationError ?: prefs.getString("error:${spec.id}", "") ?: "")
            .put("path", if (file.exists()) file.absolutePath else "")
    }

    private fun migrateLegacyDownload(spec: ModelSpec) {
        val legacyId = prefs.getLong("download:${spec.id}", -1L)
        if (legacyId <= 0L) return
        runCatching {
            val service = context.getSystemService(Context.DOWNLOAD_SERVICE) as android.app.DownloadManager
            service.remove(legacyId)
        }
        prefs.edit().remove("download:${spec.id}").apply()
        val legacyTarget = modelFile(spec)
        if (legacyTarget.exists() && legacyTarget.length() in 1 until spec.expectedBytes) {
            legacyTarget.renameTo(partialFile(spec))
        }
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
