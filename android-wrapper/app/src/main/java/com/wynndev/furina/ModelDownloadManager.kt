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
import java.io.FileOutputStream
import java.io.IOException
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class ModelDownloadManager(private val context: Context) {
    companion object {
        private const val DOWNLOAD_HEADROOM_BYTES = 512L * 1024L * 1024L
        private const val LEGACY_MIGRATION_HEADROOM_BYTES = 256L * 1024L * 1024L
        private const val COPY_BUFFER_BYTES = 8 * 1024 * 1024
    }

    private val workManager = WorkManager.getInstance(context.applicationContext)
    private val prefs = context.getSharedPreferences(ModelDownloadKeys.PREFS, Context.MODE_PRIVATE)

    // New downloads go directly to mmap-safe private no-backup storage. Older builds used
    // app-specific external storage first and then copied the entire GGUF internally; keeping
    // a legacy directory reference lets existing partial/full downloads migrate once.
    private val runtimeModelDir = File(context.noBackupFilesDir, "models").apply { mkdirs() }
    private val legacyDownloadModelDir = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models").apply { mkdirs() }
    private val verificationLocks = ConcurrentHashMap<String, Mutex>()

    init {
        cleanupRetiredModels()
    }

    private fun runtimeModelFile(spec: ModelSpec): File = File(runtimeModelDir, spec.fileName)
    private fun partialFile(spec: ModelSpec): File = File(runtimeModelDir, "${spec.fileName}.part")
    private fun legacyModelFile(spec: ModelSpec): File = File(legacyDownloadModelDir, spec.fileName)
    private fun legacyPartialFile(spec: ModelSpec): File = File(legacyDownloadModelDir, "${spec.fileName}.part")
    private fun uniqueWork(spec: ModelSpec) = "furina-model-${spec.id}"

    fun modelFile(spec: ModelSpec): File = runtimeModelFile(spec)

    private fun verificationTrustMatches(spec: ModelSpec, file: File): Boolean =
        file.exists() &&
            prefs.getString("verified:${spec.id}", null) == spec.sha256 &&
            prefs.getLong("verified_size:${spec.id}", -1L) == file.length() &&
            prefs.getLong("verified_mtime:${spec.id}", -1L) == file.lastModified() &&
            prefs.getString("verified_path:${spec.id}", null) == file.absolutePath

    private fun recordVerificationTrust(spec: ModelSpec, file: File) {
        prefs.edit()
            .putString("verified:${spec.id}", spec.sha256)
            .putLong("verified_size:${spec.id}", file.length())
            .putLong("verified_mtime:${spec.id}", file.lastModified())
            .putString("verified_path:${spec.id}", file.absolutePath)
            .remove("verification_error:${spec.id}")
            .apply()
    }

    fun invalidateVerificationTrust(spec: ModelSpec) {
        prefs.edit()
            .remove("verified:${spec.id}")
            .remove("verified_size:${spec.id}")
            .remove("verified_mtime:${spec.id}")
            .remove("verified_path:${spec.id}")
            .apply()
    }

    @Synchronized
    fun start(spec: ModelSpec): JSONObject {
        migrateLegacyDownload(spec)
        val current = status(spec)
        if (current.optString("state") == "downloading") return current

        val runtimeTarget = runtimeModelFile(spec)
        require(!runtimeTarget.exists() || runtimeTarget.delete()) {
            "File model runtime lama tidak dapat dibersihkan. Coba hapus model lalu ulangi."
        }

        val available = StatFs(runtimeModelDir.absolutePath).availableBytes
        val reusablePartial = partialFile(spec).length().coerceAtMost(spec.expectedBytes)
        require(available + reusablePartial >= spec.expectedBytes + DOWNLOAD_HEADROOM_BYTES) {
            "Penyimpanan tidak cukup. Sisakan setidaknya ${formatGiB(spec.expectedBytes + DOWNLOAD_HEADROOM_BYTES)}."
        }
        invalidateVerificationTrust(spec)
        prefs.edit()
            .remove("cancelled:${spec.id}")
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
        prefs.edit().remove("worker:${spec.id}").remove("download:${spec.id}").apply()
        invalidateVerificationTrust(spec)
        prefs.edit()
            .remove("verification_error:${spec.id}")
            .remove("state:${spec.id}")
            .remove("error:${spec.id}")
            .remove("downloaded:${spec.id}")
            .remove("total:${spec.id}")
            .apply()
        runtimeModelFile(spec).delete()
        partialFile(spec).delete()
        legacyModelFile(spec).delete()
        legacyPartialFile(spec).delete()
        return status(spec)
    }

    @Synchronized
    fun delete(spec: ModelSpec): JSONObject = cancel(spec)

    fun status(spec: ModelSpec): JSONObject {
        migrateLegacyDownload(spec)
        val file = modelFile(spec)
        val partial = partialFile(spec)
        var state = prefs.getString("state:${spec.id}", null)
            ?: if (file.exists() && file.length() > 0) "ready" else if (partial.exists()) "paused" else "not_downloaded"
        if (!file.exists() && state == "ready") {
            state = if (partial.exists()) "paused" else "not_downloaded"
        }
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
        val verified = sizeMatches && verificationTrustMatches(spec, file)
        return JSONObject()
            .put("id", spec.id)
            .put("state", state)
            .put("downloadedBytes", downloaded)
            .put("totalBytes", total)
            .put("progress", if (total > 0L) downloaded.toDouble() / total.toDouble() else 0.0)
            .put("verified", verified)
            .put("runtimePrivate", file.exists())
            .put("reason", reason)
            .put("availableBytes", StatFs(runtimeModelDir.absolutePath).availableBytes)
            .put("error", verificationError ?: prefs.getString("error:${spec.id}", "") ?: "")
            .put("path", if (file.exists()) file.absolutePath else "")
    }

    /** The worker already downloads into the final mmap-safe filesystem; only verify trust. */
    fun ensureRuntimeModel(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): File {
        migrateLegacyDownload(spec)
        val runtime = runtimeModelFile(spec)
        require(runtime.exists() && runtime.isFile && runtime.canRead()) { "File model terverifikasi tidak ditemukan" }
        require(runtime.length() == spec.expectedBytes) { "Ukuran model runtime tidak cocok" }
        if (!verificationTrustMatches(spec, runtime)) {
            require(verify(spec, progress)) { "Model runtime harus diverifikasi ulang sebelum digunakan" }
        }
        return runtime
    }

    /**
     * One-time compatibility migration for downloads created by builds before direct-private
     * storage. New downloads never enter this path and therefore never require a second model copy.
     */
    @Synchronized
    private fun migrateLegacyDownload(spec: ModelSpec) {
        val legacyId = prefs.getLong("download:${spec.id}", -1L)
        if (legacyId > 0L) {
            runCatching {
                val service = context.getSystemService(Context.DOWNLOAD_SERVICE) as android.app.DownloadManager
                service.remove(legacyId)
            }
            prefs.edit().remove("download:${spec.id}").apply()
        }

        val runtime = runtimeModelFile(spec)
        val partial = partialFile(spec)
        val legacyFinal = legacyModelFile(spec)
        val legacyPartial = legacyPartialFile(spec)

        if (!runtime.exists() && legacyFinal.exists()) {
            moveLegacyFile(legacyFinal, runtime)
            invalidateVerificationTrust(spec)
            prefs.edit().putString("state:${spec.id}", "ready").apply()
        }
        if (!runtime.exists() && !partial.exists() && legacyPartial.exists()) {
            moveLegacyFile(legacyPartial, partial)
            prefs.edit()
                .putString("state:${spec.id}", "paused")
                .putLong("downloaded:${spec.id}", partial.length())
                .putLong("total:${spec.id}", spec.expectedBytes)
                .apply()
        }
    }

    private fun moveLegacyFile(source: File, target: File) {
        if (!source.exists()) return
        target.parentFile?.mkdirs()
        if (source.renameTo(target)) return
        val available = StatFs(runtimeModelDir.absolutePath).availableBytes
        require(available >= source.length() + LEGACY_MIGRATION_HEADROOM_BYTES) {
            "Penyimpanan internal tidak cukup untuk memindahkan model lama. Sisakan setidaknya ${formatGiB(source.length() + LEGACY_MIGRATION_HEADROOM_BYTES)}."
        }
        val temp = File(target.parentFile, "${target.name}.legacy-migrating")
        temp.delete()
        try {
            FileInputStream(source).use { input ->
                FileOutputStream(temp).use { output ->
                    input.copyTo(output, COPY_BUFFER_BYTES)
                    output.flush()
                    output.fd.sync()
                }
            }
            if (temp.length() != source.length()) throw IOException("Migrasi model lama tidak lengkap")
            if (target.exists() && !target.delete()) throw IOException("Target model lama tidak dapat diganti")
            if (!temp.renameTo(target)) throw IOException("Model lama tidak dapat dipromosikan")
            source.delete()
        } catch (error: Throwable) {
            temp.delete()
            throw error
        }
    }

    /** Remove only Furina's retired GGUF files so an update cannot leave old models unused. */
    private fun cleanupRetiredModels() {
        val retired = listOf(
            "qwen35-4b-uncensored-q4km" to "Qwen3.5-4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
            "qwen35-9b-uncensored-q4km" to "Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        )
        retired.forEach { (id, fileName) ->
            workManager.cancelUniqueWork("furina-model-$id")
            File(legacyDownloadModelDir, fileName).delete()
            File(legacyDownloadModelDir, "$fileName.part").delete()
            File(runtimeModelDir, fileName).delete()
            File(runtimeModelDir, "$fileName.part").delete()
            File(runtimeModelDir, "$fileName.migrating").delete()
            File(runtimeModelDir, "$fileName.legacy-migrating").delete()
            prefs.edit()
                .remove("cancelled:$id").remove("verified:$id")
                .remove("verified_size:$id").remove("verified_mtime:$id").remove("verified_path:$id")
                .remove("verification_error:$id").remove("error:$id").remove("state:$id")
                .remove("downloaded:$id").remove("total:$id").remove("worker:$id").remove("download:$id")
                .apply()
        }
    }

    fun verify(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): Boolean {
        val file = modelFile(spec)
        if (!file.exists() || file.length() == 0L) return false
        if (file.length() != spec.expectedBytes) {
            invalidateVerificationTrust(spec)
            prefs.edit().putString("verification_error:${spec.id}", "Ukuran file model tidak cocok").apply()
            return false
        }
        if (verificationTrustMatches(spec, file)) return true

        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(COPY_BUFFER_BYTES)
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
            recordVerificationTrust(spec, file)
        } else {
            invalidateVerificationTrust(spec)
            prefs.edit().putString("verification_error:${spec.id}", "Checksum model tidak cocok").apply()
        }
        return ok
    }

    suspend fun verifySerialized(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): Boolean {
        val lock = verificationLocks.getOrPut(spec.id) { Mutex() }
        return lock.withLock { verify(spec, progress) }
    }

    private fun formatGiB(bytes: Long): String = String.format(java.util.Locale.US, "%.1f GB", bytes / 1024.0 / 1024.0 / 1024.0)
}
