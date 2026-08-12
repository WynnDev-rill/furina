package com.wynndev.furina

import android.app.AlertDialog
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.ContextCompat
import androidx.core.content.pm.PackageInfoCompat
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.Locale
import java.util.concurrent.Executors

data class FurinaUpdateInfo(
    val versionCode: Long,
    val versionName: String,
    val minimumVersionCode: Long,
    val mandatory: Boolean,
    val apkUrl: String,
    val sha256: String,
    val packageName: String,
    val signerSha256: String,
    val title: String,
    val notes: List<String>,
)

/** Native APK updater for Furina's direct-distribution builds. */
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
        ContextCompat.registerReceiver(activity, receiver, IntentFilter(DownloadManager.ACTION_DOWNLOAD_COMPLETE), ContextCompat.RECEIVER_NOT_EXPORTED)
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
            val current = currentVersionCode()
            val fetched = runCatching { fetchManifest() }.getOrNull()
            val info = if (fetched != null) {
                cacheValidatedPolicy(fetched)
                fetched
            } else {
                // Only a policy previously fetched and cryptographically/structurally validated
                // may enforce offline. A fresh install with no cached policy remains usable offline.
                cachedMandatoryPolicy(current) ?: return@execute
            }
            if (info.versionCode <= current && current >= info.minimumVersionCode) {
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
            val sha256 = json.getString("sha256").normalizedDigest()
            val packageName = json.getString("packageName").trim()
            val signerSha256 = json.getString("signerSha256").normalizedDigest()
            require(packageName == activity.packageName) { "Unexpected update package" }
            return FurinaUpdateInfo(
                versionCode = versionCode,
                versionName = json.optString("versionName", versionCode.toString()),
                minimumVersionCode = json.optLong("minimumVersionCode", 1L),
                mandatory = json.optBoolean("mandatory", false),
                apkUrl = apkUrl,
                sha256 = sha256,
                packageName = packageName,
                signerSha256 = signerSha256,
                title = json.optString("title", "Pembaruan Furina tersedia"),
                notes = json.optJSONArray("notes").toStringList(),
            )
        } finally {
            connection.disconnect()
        }
    }

    private fun cacheValidatedPolicy(info: FurinaUpdateInfo) {
        preferences.edit().putString(KEY_CACHED_POLICY, JSONObject()
            .put("versionCode", info.versionCode)
            .put("versionName", info.versionName)
            .put("minimumVersionCode", info.minimumVersionCode)
            .put("mandatory", info.mandatory)
            .put("apkUrl", info.apkUrl)
            .put("sha256", info.sha256)
            .put("packageName", info.packageName)
            .put("signerSha256", info.signerSha256)
            .put("title", info.title)
            .put("notes", JSONArray(info.notes))
            .toString()).apply()
    }

    private fun cachedMandatoryPolicy(current: Long): FurinaUpdateInfo? = runCatching {
        val raw = preferences.getString(KEY_CACHED_POLICY, null) ?: return@runCatching null
        val json = JSONObject(raw)
        val info = FurinaUpdateInfo(
            versionCode = json.getLong("versionCode"),
            versionName = json.getString("versionName"),
            minimumVersionCode = json.getLong("minimumVersionCode"),
            mandatory = json.getBoolean("mandatory"),
            apkUrl = json.getString("apkUrl").also { require(it.startsWith(TRUSTED_RELEASE_PREFIX)) },
            sha256 = json.getString("sha256").normalizedDigest(),
            packageName = json.getString("packageName").also { require(it == activity.packageName) },
            signerSha256 = json.getString("signerSha256").normalizedDigest(),
            title = json.optString("title", "Pembaruan Furina diperlukan"),
            notes = json.optJSONArray("notes").toStringList(),
        )
        if ((info.mandatory || current < info.minimumVersionCode) && current < info.versionCode) info else null
    }.getOrNull()

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
            .setPositiveButton("Perbarui") { _, _ -> updateDialogVisible = false; startDownload(info) }
            .apply {
                if (forced) setNegativeButton("Keluar") { _, _ -> updateDialogVisible = false; activity.finishAndRemoveTask() }
                else setNegativeButton("Nanti") { _, _ -> updateDialogVisible = false }
            }.create()
        dialog.setOnCancelListener { updateDialogVisible = false; if (forced) activity.finishAndRemoveTask() }
        dialog.setCancelable(!forced)
        dialog.setCanceledOnTouchOutside(false)
        dialog.show()
    }

    private fun startDownload(info: FurinaUpdateInfo) {
        val fileName = updateFileName(info.versionCode)
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
                    .putString(KEY_TARGET_SHA256, info.sha256)
                    .putString(KEY_TARGET_PACKAGE, info.packageName)
                    .putString(KEY_TARGET_SIGNER_SHA256, info.signerSha256)
                    .putBoolean(KEY_PENDING_INSTALL, false)
                    .apply()
                Toast.makeText(activity, "Pembaruan sedang diunduh", Toast.LENGTH_LONG).show()
            }
            .onFailure { Toast.makeText(activity, "Pembaruan gagal diunduh. Periksa koneksi lalu coba lagi.", Toast.LENGTH_LONG).show() }
    }

    fun tryInstallPending() {
        val target = preferences.getLong(KEY_TARGET_VERSION, -1L)
        if (target > 0L && currentVersionCode() >= target) {
            clearCompletedUpdateState(currentVersionCode())
            return
        }
        if (!preferences.getBoolean(KEY_PENDING_INSTALL, false)) return
        val id = preferences.getLong(KEY_DOWNLOAD_ID, -1L)
        if (id <= 0L || target <= 0L) return

        val query = DownloadManager.Query().setFilterById(id)
        val successful = runCatching {
            downloadManager.query(query).use { cursor -> cursor.moveToFirst() && cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) == DownloadManager.STATUS_SUCCESSFUL }
        }.getOrDefault(false)
        if (!successful) return

        val verified = runCatching { verifyDownloadedApk(target) }.getOrDefault(false)
        if (!verified) {
            runCatching { downloadManager.remove(id) }
            cleanupUpdateFiles(target)
            clearPendingDownloadState()
            Toast.makeText(activity, "Pembaruan ditolak karena file APK tidak cocok dengan rilis Furina.", Toast.LENGTH_LONG).show()
            return
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !activity.packageManager.canRequestPackageInstalls()) {
            runCatching { activity.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${activity.packageName}"))) }
            Toast.makeText(activity, "Izinkan Furina memasang pembaruan, lalu kembali ke aplikasi.", Toast.LENGTH_LONG).show()
            return
        }

        val apkUri = downloadManager.getUriForDownloadedFile(id) ?: return
        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(apkUri, APK_MIME)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        runCatching { activity.startActivity(installIntent) }
            .onFailure { Toast.makeText(activity, "Installer Android tidak dapat dibuka.", Toast.LENGTH_LONG).show() }
    }

    private fun verifyDownloadedApk(targetVersion: Long): Boolean {
        val expectedSha = preferences.getString(KEY_TARGET_SHA256, null)?.normalizedDigest() ?: return false
        val expectedPackage = preferences.getString(KEY_TARGET_PACKAGE, null)?.trim() ?: return false
        val expectedSigner = preferences.getString(KEY_TARGET_SIGNER_SHA256, null)?.normalizedDigest() ?: return false
        if (expectedPackage != activity.packageName) return false
        val apk = File(activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), updateFileName(targetVersion))
        if (!apk.isFile || apk.length() <= 0L || sha256(apk) != expectedSha) return false
        val archive = packageArchiveInfo(apk) ?: return false
        if (archive.packageName != expectedPackage || PackageInfoCompat.getLongVersionCode(archive) != targetVersion) return false
        if (expectedSigner !in signerDigests(archive)) return false
        val installed = packageInfo(activity.packageName) ?: return false
        return expectedSigner in signerDigests(installed)
    }

    private fun packageArchiveInfo(apk: File): PackageInfo? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) activity.packageManager.getPackageArchiveInfo(apk.absolutePath, PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()))
        else { @Suppress("DEPRECATION") activity.packageManager.getPackageArchiveInfo(apk.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES) }

    private fun packageInfo(packageName: String): PackageInfo? = runCatching {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) activity.packageManager.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()))
        else { @Suppress("DEPRECATION") activity.packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES) }
    }.getOrNull()

    private fun signerDigests(info: PackageInfo): Set<String> {
        val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) info.signingInfo?.apkContentsSigners.orEmpty()
        else { @Suppress("DEPRECATION") info.signatures.orEmpty() }
        return signatures.mapTo(linkedSetOf()) { signature -> MessageDigest.getInstance("SHA-256").digest(signature.toByteArray()).joinToString("") { "%02x".format(it) } }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) { val read = input.read(buffer); if (read <= 0) break; digest.update(buffer, 0, read) }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun currentVersionCode(): Long = runCatching { PackageInfoCompat.getLongVersionCode(activity.packageManager.getPackageInfo(activity.packageName, 0)) }.getOrDefault(0L)

    private fun clearCompletedUpdateState(currentVersionCode: Long) {
        val target = preferences.getLong(KEY_TARGET_VERSION, -1L)
        if (target > 0L && currentVersionCode < target) return
        val id = preferences.getLong(KEY_DOWNLOAD_ID, -1L)
        if (id > 0L) runCatching { downloadManager.remove(id) }
        cleanupUpdateFiles(currentVersionCode)
        clearPendingDownloadState()
    }

    private fun cleanupUpdateFiles(upToVersion: Long) {
        val dir = activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: return
        dir.listFiles()?.forEach { file ->
            val match = UPDATE_FILE_REGEX.matchEntire(file.name) ?: return@forEach
            val version = match.groupValues[1].toLongOrNull() ?: return@forEach
            if (version <= upToVersion) runCatching { file.delete() }
        }
    }

    private fun clearPendingDownloadState() {
        preferences.edit()
            .remove(KEY_DOWNLOAD_ID).remove(KEY_TARGET_VERSION).remove(KEY_TARGET_SHA256)
            .remove(KEY_TARGET_PACKAGE).remove(KEY_TARGET_SIGNER_SHA256).remove(KEY_PENDING_INSTALL).apply()
    }

    private fun JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return buildList { for (index in 0 until length()) optString(index).trim().takeIf { it.isNotEmpty() }?.let(::add) }
    }

    private fun String.normalizedDigest(): String {
        val value = lowercase(Locale.US).replace(":", "").trim()
        require(value.matches(Regex("[0-9a-f]{64}"))) { "Invalid SHA-256 digest" }
        return value
    }

    private fun updateFileName(versionCode: Long): String = "Furina-update-$versionCode.apk"

    companion object {
        private const val PREFS = "furina_updates"
        private const val KEY_DOWNLOAD_ID = "download_id"
        private const val KEY_TARGET_VERSION = "target_version"
        private const val KEY_TARGET_SHA256 = "target_sha256"
        private const val KEY_TARGET_PACKAGE = "target_package"
        private const val KEY_TARGET_SIGNER_SHA256 = "target_signer_sha256"
        private const val KEY_PENDING_INSTALL = "pending_install"
        private const val KEY_CACHED_POLICY = "cached_validated_policy"
        private const val APK_MIME = "application/vnd.android.package-archive"
        private val UPDATE_FILE_REGEX = Regex("Furina-update-(\\d+)\\.apk")
        private const val UPDATE_MANIFEST_URL = "https://github.com/WynnDev-rill/furina/releases/latest/download/update.json"
        private const val TRUSTED_RELEASE_PREFIX = "https://github.com/WynnDev-rill/furina/releases/"
    }
}
