package com.wynndev.furina

import android.app.AlertDialog
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.content.pm.PackageInfoCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

data class FurinaUpdateInfo(
    val versionCode: Long,
    val versionName: String,
    val minimumVersionCode: Long,
    val mandatory: Boolean,
    val apkUrl: String,
    val title: String,
    val notes: List<String>,
)

/**
 * Native APK updater for Furina's direct-distribution builds.
 *
 * The manifest is published beside each successful stable GitHub Release. The updater never
 * touches user/model data: Android installs the new APK over the existing signed package.
 */
class UpdateManager(private val activity: MainActivity) {
    private val executor = Executors.newSingleThreadExecutor()
    private val preferences = activity.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val downloadManager = activity.getSystemService(DownloadManager::class.java)
    private var registered = false
    private var updateDialogVisible = false

    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != DownloadManager.ACTION_DOWNLOAD_COMPLETE) return
            val completedId = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L)
            if (completedId != preferences.getLong(KEY_DOWNLOAD_ID, -2L)) return
            preferences.edit().putBoolean(KEY_PENDING_INSTALL, true).apply()
            tryInstallPending()
        }
    }

    fun register() {
        if (registered) return
        ContextCompat.registerReceiver(
            activity,
            receiver,
            IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE),
            ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        registered = true
    }

    fun unregister() {
        if (registered) {
            runCatching { activity.unregisterReceiver(receiver) }
            registered = false
        }
        executor.shutdownNow()
    }

    fun checkForUpdate() {
        executor.execute {
            val info = runCatching { fetchManifest() }.getOrNull() ?: return@execute
            val current = currentVersionCode()
            if (info.versionCode <= current) {
                clearCompletedUpdateState(current)
                return@execute
            }
            activity.runOnUiThread { showUpdateDialog(info, current) }
        }
    }

    private fun fetchManifest(): FurinaUpdateInfo {
        val connection = URL("$UPDATE_MANIFEST_URL?t=${System.currentTimeMillis()}").openConnection() as HttpURLConnection
        connection.connectTimeout = 7_000
        connection.readTimeout = 7_000
        connection.instanceFollowRedirects = true
        connection.useCaches = false
        connection.setRequestProperty("Cache-Control", "no-cache, no-store")
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("User-Agent", "FurinaAndroid/${BuildConfig.VERSION_NAME}")
        try {
            if (connection.responseCode !in 200..299) error("Update manifest unavailable")
            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            val apkUrl = json.getString("apkUrl").trim()
            require(apkUrl.startsWith(TRUSTED_RELEASE_PREFIX)) { "Untrusted update URL" }
            val versionCode = json.getLong("versionCode")
            require(versionCode > 0L) { "Invalid update version" }
            return FurinaUpdateInfo(
                versionCode = versionCode,
                versionName = json.optString("versionName", versionCode.toString()),
                minimumVersionCode = json.optLong("minimumVersionCode", 1L),
                mandatory = json.optBoolean("mandatory", true),
                apkUrl = apkUrl,
                title = json.optString("title", "Pembaruan Furina tersedia"),
                notes = json.optJSONArray("notes").toStringList(),
            )
        } finally {
            connection.disconnect()
        }
    }

    private fun showUpdateDialog(info: FurinaUpdateInfo, currentVersionCode: Long) {
        if (activity.isFinishing || activity.isDestroyed || updateDialogVisible) return
        val forced = info.mandatory || currentVersionCode < info.minimumVersionCode
        val message = buildString {
            append("Versi ${info.versionName} tersedia.")
            if (info.notes.isNotEmpty()) {
                append("\n\n")
                info.notes.forEach { append("• ").append(it).append('\n') }
            }
        }.trim()

        updateDialogVisible = true
        val dialog = AlertDialog.Builder(activity)
            .setTitle(info.title)
            .setMessage(message)
            .setPositiveButton("Perbarui") { _, _ ->
                updateDialogVisible = false
                startDownload(info)
            }
            .apply {
                if (forced) {
                    setNegativeButton("Keluar") { _, _ ->
                        updateDialogVisible = false
                        activity.finishAndRemoveTask()
                    }
                } else {
                    setNegativeButton("Nanti") { _, _ -> updateDialogVisible = false }
                }
            }
            .create()

        dialog.setOnCancelListener {
            updateDialogVisible = false
            if (forced) activity.finishAndRemoveTask()
        }
        dialog.setCancelable(!forced)
        dialog.setCanceledOnTouchOutside(false)
        dialog.show()
    }

    private fun startDownload(info: FurinaUpdateInfo) {
        val fileName = "Furina-update-${info.versionCode}.apk"
        val request = DownloadManager.Request(Uri.parse(info.apkUrl))
            .setTitle("Memperbarui Furina")
            .setDescription("Mengunduh Furina ${info.versionName}")
            .setMimeType(APK_MIME)
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(activity, Environment.DIRECTORY_DOWNLOADS, fileName)

        runCatching { downloadManager.enqueue(request) }
            .onSuccess { id ->
                preferences.edit()
                    .putLong(KEY_DOWNLOAD_ID, id)
                    .putLong(KEY_TARGET_VERSION, info.versionCode)
                    .putBoolean(KEY_PENDING_INSTALL, false)
                    .apply()
                Toast.makeText(activity, "Pembaruan sedang diunduh", Toast.LENGTH_LONG).show()
            }
            .onFailure {
                Toast.makeText(activity, "Pembaruan gagal diunduh. Periksa koneksi lalu coba lagi.", Toast.LENGTH_LONG).show()
            }
    }

    fun tryInstallPending() {
        val target = preferences.getLong(KEY_TARGET_VERSION, -1L)
        if (target > 0L && currentVersionCode() >= target) {
            clearCompletedUpdateState(currentVersionCode())
            return
        }
        if (!preferences.getBoolean(KEY_PENDING_INSTALL, false)) return
        val id = preferences.getLong(KEY_DOWNLOAD_ID, -1L)
        if (id <= 0L) return

        val query = DownloadManager.Query().setFilterById(id)
        val successful = runCatching {
            downloadManager.query(query).use { cursor ->
                cursor.moveToFirst() &&
                    cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) == DownloadManager.STATUS_SUCCESSFUL
            }
        }.getOrDefault(false)
        if (!successful) return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !activity.packageManager.canRequestPackageInstalls()) {
            val settingsIntent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${activity.packageName}"),
            )
            runCatching { activity.startActivity(settingsIntent) }
            Toast.makeText(activity, "Izinkan Furina memasang pembaruan, lalu kembali ke aplikasi.", Toast.LENGTH_LONG).show()
            return
        }

        val apkUri = downloadManager.getUriForDownloadedFile(id) ?: return
        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(apkUri, APK_MIME)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        runCatching { activity.startActivity(installIntent) }
            .onFailure {
                Toast.makeText(activity, "Installer Android tidak dapat dibuka.", Toast.LENGTH_LONG).show()
            }
    }

    private fun currentVersionCode(): Long = runCatching {
        PackageInfoCompat.getLongVersionCode(
            activity.packageManager.getPackageInfo(activity.packageName, 0),
        )
    }.getOrDefault(0L)

    private fun clearCompletedUpdateState(currentVersionCode: Long) {
        val target = preferences.getLong(KEY_TARGET_VERSION, -1L)
        if (target <= 0L || currentVersionCode < target) return
        preferences.edit()
            .remove(KEY_DOWNLOAD_ID)
            .remove(KEY_TARGET_VERSION)
            .remove(KEY_PENDING_INSTALL)
            .apply()
    }

    private fun JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return buildList {
            for (index in 0 until length()) {
                optString(index).trim().takeIf { it.isNotEmpty() }?.let(::add)
            }
        }
    }

    companion object {
        private const val PREFS = "furina_updates"
        private const val KEY_DOWNLOAD_ID = "download_id"
        private const val KEY_TARGET_VERSION = "target_version"
        private const val KEY_PENDING_INSTALL = "pending_install"
        private const val APK_MIME = "application/vnd.android.package-archive"
        private const val UPDATE_MANIFEST_URL =
            "https://github.com/WynnDev-rill/furina/releases/latest/download/update.json"
        private const val TRUSTED_RELEASE_PREFIX =
            "https://github.com/WynnDev-rill/furina/releases/"
    }
}
