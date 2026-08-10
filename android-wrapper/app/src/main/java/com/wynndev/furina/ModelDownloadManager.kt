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
        private const val MIGRATION_HEADROOM_BYTES = 256L * 1024L * 1024L
        private const val COPY_BUFFER_BYTES = 8 * 1024 * 1024
    }

    private val workManager = WorkManager.getInstance(context.applicationContext)
    private val prefs = context.getSharedPreferences(ModelDownloadKeys.PREFS, Context.MODE_PRIVATE)

    // WorkManager downloads to app-specific external storage because it has ample space and
    // supports resumable background transfer. llama.cpp itself runs from internal no-backup
    // storage: Android's private filesystem has predictable mmap semantics and avoids emulated
    // external-storage/FUSE behavior during multi-gigabyte native model mapping.
    private val downloadModelDir = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models").apply { mkdirs() }
    private val runtimeModelDir = File(context.noBackupFilesDir, "models").apply { mkdirs() }
    private val verificationLocks = ConcurrentHashMap<String, Mutex>()

    init {
        cleanupRetiredModels()
    }

    private fun runtimeModelFile(spec: ModelSpec): File = File(runtimeModelDir, spec.fileName)
    private fun downloadModelFile(spec: ModelSpec): File = File(downloadModelDir, spec.fileName)

    /** Prefer the mmap-safe internal runtime copy once it has been migrated. */
    fun modelFile(spec: ModelSpec): File {
        val runtime = runtimeModelFile(spec)
        return if (runtime.exists()) runtime else downloadModelFile(spec)
    }

    private fun partialFile(spec: ModelSpec): File = File(downloadModelDir, "${spec.fileName}.part")
    private fun uniqueWork(spec: ModelSpec) = "furina-model-${spec.id}"

    @Synchronized
    fun start(spec: ModelSpec): JSONObject {
        migrateLegacyDownload(spec)
        val current = status(spec)
        if (current.optString("state") == "downloading") return current

        val runtimeTarget = runtimeModelFile(spec)
        val downloadTarget = downloadModelFile(spec)
        require(!runtimeTarget.exists() || runtimeTarget.delete()) {
            "File model runtime lama tidak dapat dibersihkan. Coba hapus model lalu ulangi."
        }
        require(!downloadTarget.exists() || downloadTarget.delete()) {
            "File model lama tidak dapat dibersihkan. Coba hapus model lalu ulangi."
        }

        val available = StatFs(downloadModelDir.absolutePath).availableBytes
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
        runtimeModelFile(spec).delete()
        downloadModelFile(spec).delete()
        partialFile(spec).delete()
        return status(spec)
    }

    @Synchronized
    fun delete(spec: ModelSpec): JSONObject = cancel(spec)

    fun status(spec: ModelSpec): JSONObject {
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
        val verified = sizeMatches && prefs.getString("verified:${spec.id}", null) == spec.sha256
        return JSONObject()
            .put("id", spec.id)
            .put("state", state)
            .put("downloadedBytes", downloaded)
            .put("totalBytes", total)
            .put("progress", if (total > 0L) downloaded.toDouble() / total.toDouble() else 0.0)
            .put("verified", verified)
            .put("runtimePrivate", runtimeModelFile(spec).exists())
            .put("reason", reason)
            .put("availableBytes", StatFs(downloadModelDir.absolutePath).availableBytes)
            .put("error", verificationError ?: prefs.getString("error:${spec.id}", "") ?: "")
            .put("path", if (file.exists()) file.absolutePath else "")
    }

    /**
     * Copy a verified model from emulated app-specific storage into internal no-backup
     * storage before llama.cpp mmaps it. The source is removed only after a complete,
     * checksum-verified, fsynced internal copy has been atomically promoted.
     */
    fun ensureRuntimeModel(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): File {
        val runtime = runtimeModelFile(spec)
        if (runtime.exists()) {
            require(runtime.length() == spec.expectedBytes) { "Ukuran model runtime tidak cocok" }
            return runtime
        }

        val source = downloadModelFile(spec)
        require(source.exists() && source.isFile && source.canRead()) {
            "File model terverifikasi tidak ditemukan"
        }
        require(source.length() == spec.expectedBytes) { "Ukuran model sumber tidak cocok" }
        require(prefs.getString("verified:${spec.id}", null) == spec.sha256) {
            "Model harus diverifikasi sebelum dipindahkan ke runtime internal"
        }

        val available = StatFs(runtimeModelDir.absolutePath).availableBytes
        require(available >= spec.expectedBytes + MIGRATION_HEADROOM_BYTES) {
            "Penyimpanan internal tidak cukup untuk menyiapkan model lokal. Sisakan setidaknya ${formatGiB(spec.expectedBytes + MIGRATION_HEADROOM_BYTES)}."
        }

        val temp = File(runtimeModelDir, "${spec.fileName}.migrating")
        temp.delete()
        val digest = MessageDigest.getInstance("SHA-256")
        var copied = 0L
        try {
            FileInputStream(source).use { input ->
                FileOutputStream(temp).use { output ->
                    val buffer = ByteArray(COPY_BUFFER_BYTES)
                    while (true) {
                        val count = input.read(buffer)
                        if (count <= 0) break
                        output.write(buffer, 0, count)
                        digest.update(buffer, 0, count)
                        copied += count
                        progress?.invoke(copied, spec.expectedBytes)
                    }
                    output.flush()
                    output.fd.sync()
                }
            }

            if (temp.length() != spec.expectedBytes) {
                throw IOException("Salinan model internal tidak lengkap (${temp.length()} byte)")
            }
            val actual = digest.digest().joinToString("") { "%02x".format(it) }
            if (!actual.equals(spec.sha256, ignoreCase = true)) {
                throw IOException("Checksum salinan model internal tidak cocok")
            }
            if (runtime.exists() && !runtime.delete()) throw IOException("Model runtime lama tidak dapat diganti")
            if (!temp.renameTo(runtime)) throw IOException("Model internal selesai disalin tetapi tidak dapat dipromosikan")
            // A failed delete only leaves a harmless duplicate. modelFile() still prefers runtime.
            source.delete()
            prefs.edit()
                .putString("state:${spec.id}", "ready")
                .putString("verified:${spec.id}", spec.sha256)
                .remove("verification_error:${spec.id}")
                .apply()
            return runtime
        } catch (error: Throwable) {
            temp.delete()
            throw error
        }
    }

    private fun migrateLegacyDownload(spec: ModelSpec) {
        val legacyId = prefs.getLong("download:${spec.id}", -1L)
        if (legacyId <= 0L) return
        runCatching {
            val service = context.getSystemService(Context.DOWNLOAD_SERVICE) as android.app.DownloadManager
            service.remove(legacyId)
        }
        prefs.edit().remove("download:${spec.id}").apply()
        val legacyTarget = downloadModelFile(spec)
        if (legacyTarget.exists() && legacyTarget.length() in 1 until spec.expectedBytes) {
            legacyTarget.renameTo(partialFile(spec))
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
            File(downloadModelDir, fileName).delete()
            File(downloadModelDir, "$fileName.part").delete()
            File(runtimeModelDir, fileName).delete()
            File(runtimeModelDir, "$fileName.migrating").delete()
            prefs.edit()
                .remove("cancelled:$id").remove("verified:$id").remove("verification_error:$id")
                .remove("error:$id").remove("state:$id").remove("downloaded:$id")
                .remove("total:$id").remove("worker:$id").remove("download:$id")
                .apply()
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
            prefs.edit().putString("verified:${spec.id}", spec.sha256).remove("verification_error:${spec.id}").apply()
        } else {
            prefs.edit().putString("verification_error:${spec.id}", "Checksum model tidak cocok").apply()
        }
        return ok
    }

    /**
     * Verification can be requested by both the settings status poller and the inference
     * loader. Serializing per model prevents two full multi-gigabyte scans from competing
     * for I/O and page cache immediately before native load.
     */
    suspend fun verifySerialized(spec: ModelSpec, progress: ((Long, Long) -> Unit)? = null): Boolean {
        val lock = verificationLocks.getOrPut(spec.id) { Mutex() }
        return lock.withLock { verify(spec, progress) }
    }

    private fun formatGiB(bytes: Long): String = String.format(java.util.Locale.US, "%.1f GB", bytes / 1024.0 / 1024.0 / 1024.0)
}
