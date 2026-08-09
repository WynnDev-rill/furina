package com.wynndev.furina

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import androidx.core.app.NotificationCompat
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import kotlinx.coroutines.CancellationException
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

internal object ModelDownloadKeys {
    const val PREFS = "furina_models"
    const val CHANNEL_ID = "furina_model_downloads"
    const val KEY_MODEL_ID = "model_id"
    const val KEY_MODEL_NAME = "model_name"
    const val KEY_URL = "url"
    const val KEY_FILE_NAME = "file_name"
    const val KEY_EXPECTED_BYTES = "expected_bytes"
}

class ModelDownloadWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    private val prefs = appContext.getSharedPreferences(ModelDownloadKeys.PREFS, Context.MODE_PRIVATE)
    private val notificationManager = appContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    override suspend fun doWork(): Result {
        val modelId = inputData.getString(ModelDownloadKeys.KEY_MODEL_ID) ?: return Result.failure()
        val modelName = inputData.getString(ModelDownloadKeys.KEY_MODEL_NAME) ?: modelId
        val downloadUrl = inputData.getString(ModelDownloadKeys.KEY_URL) ?: return Result.failure()
        val fileName = inputData.getString(ModelDownloadKeys.KEY_FILE_NAME) ?: return Result.failure()
        val expectedBytes = inputData.getLong(ModelDownloadKeys.KEY_EXPECTED_BYTES, 0L)
        if (expectedBytes <= 0L) return Result.failure()

        val modelDir = File(applicationContext.getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS), "models").apply { mkdirs() }
        val finalFile = File(modelDir, fileName)
        val partialFile = File(modelDir, "$fileName.part")
        val notificationId = 7100 + (modelId.hashCode() and 0x3ff)

        return try {
            setState(modelId, "downloading", partialFile.length(), expectedBytes, "")
            setForeground(createForegroundInfo(modelId, modelName, partialFile.length(), expectedBytes, notificationId))
            downloadResumable(modelId, modelName, downloadUrl, partialFile, expectedBytes, notificationId)

            if (partialFile.length() != expectedBytes) {
                throw IOException("Ukuran unduhan ${partialFile.length()} tidak sesuai $expectedBytes byte")
            }
            if (finalFile.exists() && !finalFile.delete()) throw IOException("File model lama tidak dapat diganti")
            if (!partialFile.renameTo(finalFile)) throw IOException("File model selesai tetapi tidak dapat dipindahkan")

            prefs.edit()
                .putString("state:$modelId", "ready")
                .putLong("downloaded:$modelId", expectedBytes)
                .remove("error:$modelId")
                .remove("verified:$modelId")
                .remove("verification_error:$modelId")
                .apply()
            notificationManager.notify(notificationId, completionNotification(modelName))
            Result.success()
        } catch (cancelled: CancellationException) {
            if (!prefs.getBoolean("cancelled:$modelId", false)) {
                setState(modelId, "paused", partialFile.length(), expectedBytes, "Unduhan dijeda dan akan dilanjutkan otomatis")
            }
            throw cancelled
        } catch (error: IOException) {
            if (prefs.getBoolean("cancelled:$modelId", false)) return Result.failure()
            setState(modelId, "paused", partialFile.length(), expectedBytes, error.message ?: "Menunggu jaringan")
            Result.retry()
        } catch (error: Throwable) {
            if (prefs.getBoolean("cancelled:$modelId", false)) return Result.failure()
            setState(modelId, "failed", partialFile.length(), expectedBytes, error.message ?: "Unduhan gagal")
            Result.failure()
        }
    }

    private fun downloadResumable(
        modelId: String,
        modelName: String,
        downloadUrl: String,
        target: File,
        expectedBytes: Long,
        notificationId: Int,
    ) {
        var existing = target.length().coerceAtMost(expectedBytes)
        if (target.length() > expectedBytes) {
            target.delete()
            existing = 0L
        }
        // A previous worker may have written the last byte before Android stopped it.
        // Promote that complete .part in doWork instead of issuing Range at EOF (416).
        if (existing == expectedBytes) return

        val connection = (URL(downloadUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 30_000
            readTimeout = 60_000
            instanceFollowRedirects = true
            setRequestProperty("Accept", "application/octet-stream")
            setRequestProperty("User-Agent", "FurinaAndroid/4.1")
            if (existing > 0L) setRequestProperty("Range", "bytes=$existing-")
        }

        try {
            connection.connect()
            val response = connection.responseCode
            if (response !in 200..299) throw IOException("Server model merespons HTTP $response")
            val append = existing > 0L && response == HttpURLConnection.HTTP_PARTIAL
            if (!append) existing = 0L

            connection.inputStream.use { input ->
                FileOutputStream(target, append).use { output ->
                    val buffer = ByteArray(1024 * 1024)
                    var downloaded = existing
                    var lastUpdate = 0L
                    while (true) {
                        if (isStopped) throw CancellationException("Worker dihentikan")
                        val count = input.read(buffer)
                        if (count < 0) break
                        output.write(buffer, 0, count)
                        downloaded += count
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastUpdate >= 750L) {
                            setState(modelId, "downloading", downloaded, expectedBytes, "")
                            notificationManager.notify(notificationId, progressNotification(modelId, modelName, downloaded, expectedBytes))
                            lastUpdate = now
                        }
                    }
                    output.flush()
                }
            }
        } finally {
            connection.disconnect()
        }
    }

    private fun setState(modelId: String, state: String, downloaded: Long, total: Long, error: String) {
        prefs.edit()
            .putString("state:$modelId", state)
            .putLong("downloaded:$modelId", downloaded)
            .putLong("total:$modelId", total)
            .putString("error:$modelId", error)
            .apply()
    }

    private fun createForegroundInfo(modelId: String, name: String, downloaded: Long, total: Long, id: Int): ForegroundInfo {
        createChannel()
        return ForegroundInfo(id, progressNotification(modelId, name, downloaded, total), ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }

    private fun progressNotification(modelId: String, name: String, downloaded: Long, total: Long): android.app.Notification {
        createChannel()
        val percent = ((downloaded * 100L) / total.coerceAtLeast(1L)).toInt().coerceIn(0, 100)
        val openApp = PendingIntent.getActivity(
            applicationContext,
            modelId.hashCode(),
            Intent(applicationContext, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val cancel = PendingIntent.getBroadcast(
            applicationContext,
            modelId.hashCode(),
            Intent(applicationContext, ModelDownloadCancelReceiver::class.java)
                .setAction(ModelDownloadCancelReceiver.ACTION_CANCEL)
                .putExtra(ModelDownloadCancelReceiver.EXTRA_MODEL_ID, modelId),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(applicationContext, ModelDownloadKeys.CHANNEL_ID)
            .setSmallIcon(R.drawable.furina_icon)
            .setContentTitle("Mengunduh $name")
            .setContentText("$percent% · aman ditinggal di latar belakang")
            .setProgress(100, percent, false)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setContentIntent(openApp)
            .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Batalkan", cancel)
            .build()
    }

    private fun completionNotification(name: String): android.app.Notification = NotificationCompat.Builder(applicationContext, ModelDownloadKeys.CHANNEL_ID)
        .setSmallIcon(R.drawable.furina_icon)
        .setContentTitle("Model Furina siap")
        .setContentText("$name selesai diunduh dan siap diverifikasi")
        .setAutoCancel(true)
        .build()

    private fun createChannel() {
        notificationManager.createNotificationChannel(
            NotificationChannel(ModelDownloadKeys.CHANNEL_ID, "Unduhan model AI", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Progres unduhan model lokal Furina"
            },
        )
    }
}
