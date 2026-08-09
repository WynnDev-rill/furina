package com.wynndev.furina

import android.content.Context
import android.net.Uri
import android.util.Base64
import androidx.documentfile.provider.DocumentFile
import org.json.JSONObject
import java.io.File
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.CipherInputStream
import javax.crypto.CipherOutputStream
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

class BackupManager(
    private val context: Context,
    private val store: MemoryStore,
) {
    companion object {
        private val MAGIC = "FURINA1".toByteArray(Charsets.US_ASCII)
        private const val KEEP_BACKUPS = 10
        private const val AUTO_INTERVAL_MS = 6L * 60L * 60L * 1000L
    }

    private val prefs = context.getSharedPreferences("furina_backup", Context.MODE_PRIVATE)

    fun setBackupFolder(uri: Uri) {
        prefs.edit().putString("tree_uri", uri.toString()).apply()
    }

    fun hasBackupFolder(): Boolean = !prefs.getString("tree_uri", null).isNullOrBlank()

    fun getOrCreateRecoveryKey(): String {
        prefs.getString("recovery_key", null)?.let { return it }
        val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val value = Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
        prefs.edit().putString("recovery_key", value).apply()
        return value
    }

    fun setRecoveryKey(value: String) {
        val trimmed = value.trim()
        val bytes = Base64.decode(trimmed, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
        require(bytes.size == 32) { "Recovery key harus 32-byte Base64URL" }
        prefs.edit().putString("recovery_key", trimmed).apply()
    }

    fun infoJson(): String = JSONObject()
        .put("folderSelected", hasBackupFolder())
        .put("folderUri", prefs.getString("tree_uri", ""))
        .put("recoveryKey", getOrCreateRecoveryKey())
        .put("lastBackup", prefs.getLong("last_backup", 0L))
        .toString()

    fun backupNow(): String {
        val tree = prefs.getString("tree_uri", null)?.let(Uri::parse)
            ?: throw IllegalStateException("Pilih folder backup terlebih dahulu")
        val root = DocumentFile.fromTreeUri(context, tree)
            ?: throw IllegalStateException("Folder backup tidak dapat dibuka")
        require(root.canWrite()) { "Folder backup tidak dapat ditulis" }

        store.checkpoint()
        val dbFile = store.databaseFile()
        require(dbFile.exists()) { "Database Furina belum tersedia" }

        val now = System.currentTimeMillis()
        val fileName = "Furina-${now}.furina"
        val doc = root.createFile("application/octet-stream", fileName)
            ?: throw IllegalStateException("Gagal membuat file backup")

        val key = decodeKey(getOrCreateRecoveryKey())
        val iv = ByteArray(12).also { SecureRandom().nextBytes(it) }
        context.contentResolver.openOutputStream(doc.uri, "w")!!.use { rawOut ->
            rawOut.write(MAGIC)
            rawOut.write(iv)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
            CipherOutputStream(rawOut, cipher).use { encrypted -> dbFile.inputStream().use { it.copyTo(encrypted, 1024 * 1024) } }
        }

        prefs.edit().putLong("last_backup", now).apply()
        prune(root)
        return fileName
    }

    fun autoBackupIfDue(): String? {
        if (!hasBackupFolder()) return null
        val last = prefs.getLong("last_backup", 0L)
        if (System.currentTimeMillis() - last < AUTO_INTERVAL_MS) return null
        return backupNow()
    }

    fun restoreFrom(uri: Uri) {
        val key = decodeKey(getOrCreateRecoveryKey())
        val temp = File(context.cacheDir, "furina-restore-${System.currentTimeMillis()}.db")
        context.contentResolver.openInputStream(uri)!!.use { rawIn ->
            val header = ByteArray(MAGIC.size)
            require(rawIn.read(header) == header.size && header.contentEquals(MAGIC)) { "Bukan backup Furina yang didukung" }
            val iv = ByteArray(12)
            require(rawIn.read(iv) == iv.size) { "Backup rusak" }
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
            CipherInputStream(rawIn, cipher).use { decrypted -> temp.outputStream().use { decrypted.copyTo(it, 1024 * 1024) } }
        }
        temp.inputStream().use { input ->
            val sqliteHeader = ByteArray(16)
            require(input.read(sqliteHeader) == 16 && String(sqliteHeader, Charsets.US_ASCII).startsWith("SQLite format 3")) {
                "Recovery key salah atau backup tidak valid"
            }
        }
        store.restoreFrom(temp)
        temp.delete()
    }

    private fun prune(root: DocumentFile) {
        root.listFiles().filter { it.isFile && it.name?.startsWith("Furina-") == true && it.name?.endsWith(".furina") == true }
            .sortedByDescending { it.lastModified() }
            .drop(KEEP_BACKUPS)
            .forEach { it.delete() }
    }

    private fun decodeKey(value: String): ByteArray {
        val bytes = Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
        require(bytes.size == 32) { "Recovery key tidak valid" }
        return bytes
    }
}
