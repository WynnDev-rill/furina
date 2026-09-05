package com.wynndev.furina

import android.content.Context
import android.net.Uri
import android.util.Base64
import androidx.documentfile.provider.DocumentFile
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.security.SecureRandom
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import javax.crypto.Cipher
import javax.crypto.CipherInputStream
import javax.crypto.CipherOutputStream
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec
import org.json.JSONObject

class BackupManager(
    private val context: Context,
    private val store: MemoryStore,
) {
    companion object {
        private val MAGIC_V1 = "FURINA1".toByteArray(Charsets.US_ASCII)
        private val MAGIC_V2 = "FURINA2".toByteArray(Charsets.US_ASCII)
        private const val KEEP_BACKUPS = 10
        private const val AUTO_INTERVAL_MS = 6L * 60L * 60L * 1000L
        private const val DB_ENTRY = "furina_memory.db"
        private const val COMPANION_ENTRY = "companion_intelligence.json"
        private const val COMPANION_PREFS = "furina_companion_intelligence_v2"
        private const val MAX_COMPANION_BYTES = 2 * 1024 * 1024
        private const val MIN_ENCRYPTED_BACKUP_BYTES = 64L
        private const val MAX_RESTORE_BYTES = 256L * 1024 * 1024
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

    /** Status is safe for WebView consumption; the encryption secret never crosses this API. */
    fun infoJson(): String = JSONObject()
        .put("folderSelected", hasBackupFolder())
        .put("folderUri", prefs.getString("tree_uri", ""))
        .put("recoveryKeyAvailable", true)
        .put("lastBackup", prefs.getLong("last_backup", 0L))
        .put("format", "FURINA2")
        .toString()

    fun backupNow(): String {
        val tree = prefs.getString("tree_uri", null)?.let(Uri::parse)
            ?: throw IllegalStateException("Pilih folder backup terlebih dahulu")
        val root = DocumentFile.fromTreeUri(context, tree)
            ?: throw IllegalStateException("Folder backup tidak dapat dibuka")
        require(root.canWrite()) { "Folder backup tidak dapat ditulis" }

        val now = System.currentTimeMillis()
        val fileName = "Furina-${now}.furina"
        val tempName = "Furina-${now}.partial"
        val temp = root.createFile("application/octet-stream", tempName)
            ?: throw IllegalStateException("Gagal membuat file backup sementara")

        try {
            context.contentResolver.openOutputStream(temp.uri, "w")?.use(::writeEncryptedSnapshot)
                ?: throw IllegalStateException("File backup sementara tidak dapat ditulis")
            require(temp.length() >= MIN_ENCRYPTED_BACKUP_BYTES) { "Backup tidak lengkap" }
            promoteBackup(root, temp, fileName)
            prefs.edit().putLong("last_backup", now).apply()
            prune(root)
            return fileName
        } catch (error: Throwable) {
            runCatching { temp.delete() }
            throw error
        }
    }

    /** Rename when supported; otherwise copy to a final name and remove both sides on failure. */
    private fun promoteBackup(root: DocumentFile, temp: DocumentFile, finalName: String) {
        if (temp.renameTo(finalName)) return

        val finalDoc = root.createFile("application/octet-stream", finalName)
            ?: throw IllegalStateException("Gagal mempromosikan file backup")
        try {
            val input = context.contentResolver.openInputStream(temp.uri)
                ?: throw IllegalStateException("Backup sementara tidak dapat dibaca")
            val output = context.contentResolver.openOutputStream(finalDoc.uri, "w")
                ?: throw IllegalStateException("Backup final tidak dapat ditulis")
            input.use { source -> output.use { target -> source.copyTo(target, 1024 * 1024) } }
            require(finalDoc.length() >= MIN_ENCRYPTED_BACKUP_BYTES) { "Backup final tidak lengkap" }
            require(temp.delete()) { "Backup sementara tidak dapat dibersihkan" }
        } catch (error: Throwable) {
            runCatching { finalDoc.delete() }
            throw error
        }
    }

    fun autoBackupIfDue(): String? {
        if (!hasBackupFolder()) return null
        val last = prefs.getLong("last_backup", 0L)
        if (System.currentTimeMillis() - last < AUTO_INTERVAL_MS) return null
        return backupNow()
    }

    fun restoreFrom(uri: Uri) {
        val input = context.contentResolver.openInputStream(uri) ?: error("Berkas backup tidak dapat dibaca")
        input.use(::restoreEncryptedSnapshot)
    }

    /** A failed restore must never replace the key for the user's existing backups. */
    fun restoreFrom(uri: Uri, recoveryKey: String) {
        val previous = getOrCreateRecoveryKey()
        try { setRecoveryKey(recoveryKey); restoreFrom(uri) }
        catch (error: Exception) { setRecoveryKey(previous); throw error }
    }

    /** Shared by local-folder and cloud backup so both preserve the same companion state. */
    fun createEncryptedSnapshotBytes(maxBytes: Long = Long.MAX_VALUE): ByteArray {
        val dbSize = store.databaseFile().length().coerceAtLeast(0L)
        require(maxBytes > 0) { "Batas ukuran backup tidak valid" }
        val initialCapacity = minOf(dbSize + 256 * 1024L, maxBytes, 4L * 1024 * 1024).toInt()
        val out = ByteArrayOutputStream(initialCapacity)
        val limited = object : OutputStream() {
            override fun write(value: Int) {
                require(out.size().toLong() + 1 <= maxBytes) { "Backup melebihi batas ukuran" }
                out.write(value)
            }
            override fun write(bytes: ByteArray, offset: Int, count: Int) {
                require(out.size().toLong() + count <= maxBytes) { "Backup melebihi batas ukuran" }
                out.write(bytes, offset, count)
            }
        }
        writeEncryptedSnapshot(limited)
        val bytes = out.toByteArray()
        require(bytes.size.toLong() <= maxBytes) { "Backup melebihi batas ukuran" }
        return bytes
    }

    fun restoreEncryptedSnapshotBytes(bytes: ByteArray) {
        require(bytes.isNotEmpty()) { "Backup kosong" }
        ByteArrayInputStream(bytes).use(::restoreEncryptedSnapshot)
    }

    private fun writeEncryptedSnapshot(rawOut: OutputStream) {
        val dbFile = File.createTempFile("furina-backup-snapshot-", ".db", context.cacheDir)
        try {
        store.writeSnapshot(dbFile)

        val key = decodeKey(getOrCreateRecoveryKey())
        val iv = ByteArray(12).also { SecureRandom().nextBytes(it) }
        rawOut.write(MAGIC_V2)
        rawOut.write(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))

        CipherOutputStream(rawOut, cipher).use { encrypted ->
            ZipOutputStream(encrypted.buffered()).use { zip ->
                zip.putNextEntry(ZipEntry(DB_ENTRY))
                dbFile.inputStream().use { it.copyTo(zip, 1024 * 1024) }
                zip.closeEntry()

                zip.putNextEntry(ZipEntry(COMPANION_ENTRY))
                zip.write(companionSnapshot().toString().toByteArray(Charsets.UTF_8))
                zip.closeEntry()
            }
        }
        } finally { dbFile.delete() }
    }

    private fun restoreEncryptedSnapshot(rawIn: InputStream) {
        val header = ByteArray(MAGIC_V2.size)
        java.io.DataInputStream(rawIn).readFully(header)
        when {
            header.contentEquals(MAGIC_V2) -> restoreV2(rawIn)
            header.contentEquals(MAGIC_V1) -> restoreV1(rawIn)
            else -> throw IllegalArgumentException("Bukan backup Furina yang didukung")
        }
    }

    /** Current portable format: encrypted ZIP containing DB plus learned companion state. */
    private fun restoreV2(rawIn: InputStream) {
        val key = decodeKey(getOrCreateRecoveryKey())
        val iv = ByteArray(12)
        java.io.DataInputStream(rawIn).readFully(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))

        val tempDb = File(context.cacheDir, "furina-restore-${System.currentTimeMillis()}.db")
        val authenticatedZip = File.createTempFile("furina-authenticated-", ".zip", context.cacheDir)
        var companion: JSONObject? = null
        try {
            // Consume the encrypted stream through its authentication tag before trusting ZIP entries.
            CipherInputStream(rawIn, cipher).use { decrypted ->
                authenticatedZip.outputStream().use { copyBounded(decrypted, it, MAX_RESTORE_BYTES) }
            }
            authenticatedZip.inputStream().use { input ->
                ZipInputStream(input.buffered()).use { zip ->
                    val seen = mutableSetOf<String>()
                    while (true) {
                        val entry = zip.nextEntry ?: break
                        require(seen.add(entry.name)) { "Entri backup duplikat" }
                        when (entry.name) {
                            DB_ENTRY -> tempDb.outputStream().use { copyBounded(zip, it, MAX_RESTORE_BYTES) }
                            COMPANION_ENTRY -> {
                                val buffer = ByteArrayOutputStream()
                                val chunk = ByteArray(32 * 1024)
                                while (true) {
                                    val count = zip.read(chunk)
                                    if (count <= 0) break
                                    require(buffer.size() + count <= MAX_COMPANION_BYTES) { "State companion backup terlalu besar" }
                                    buffer.write(chunk, 0, count)
                                }
                                companion = JSONObject(buffer.toString(Charsets.UTF_8.name()))
                            }
                        }
                        zip.closeEntry()
                    }
                }
            }
            validateDatabase(tempDb)
            store.restoreFrom(tempDb)
            restoreCompanionSnapshot(companion ?: JSONObject())
        } finally {
            tempDb.delete()
            authenticatedZip.delete()
        }
    }

    /** Backward compatibility for existing FURINA1 encrypted raw-SQLite backups. */
    private fun restoreV1(rawIn: InputStream) {
        val key = decodeKey(getOrCreateRecoveryKey())
        val iv = ByteArray(12)
        java.io.DataInputStream(rawIn).readFully(iv)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
        val temp = File(context.cacheDir, "furina-legacy-restore-${System.currentTimeMillis()}.db")
        try {
            CipherInputStream(rawIn, cipher).use { decrypted ->
                temp.outputStream().use { copyBounded(decrypted, it, MAX_RESTORE_BYTES) }
            }
            validateDatabase(temp)
            store.restoreFrom(temp)
            context.getSharedPreferences(COMPANION_PREFS, Context.MODE_PRIVATE).edit().clear().apply()
        } finally {
            temp.delete()
        }
    }

    private fun validateDatabase(file: File) {
        require(file.isFile && file.length() >= 16L) { "Recovery key salah atau backup tidak valid" }
        file.inputStream().use { input ->
            val sqliteHeader = ByteArray(16)
            require(input.read(sqliteHeader) == 16 && String(sqliteHeader, Charsets.US_ASCII).startsWith("SQLite format 3")) {
                "Recovery key salah atau backup tidak valid"
            }
        }
        android.database.sqlite.SQLiteDatabase.openDatabase(file.path, null, android.database.sqlite.SQLiteDatabase.OPEN_READONLY).use { db ->
            require(db.version in 1..5) { "Versi database backup belum didukung" }
            db.rawQuery("PRAGMA integrity_check", null).use { c ->
                val result = if (c.moveToFirst()) c.getString(0) else "hasil pemeriksaan kosong"
                require(result.equals("ok", ignoreCase = true)) { "Database backup tidak valid: ${result.take(200)}" }
            }
            for (table in listOf("sessions", "messages", "memories")) {
                db.rawQuery("SELECT name FROM sqlite_master WHERE type='table' AND name=?", arrayOf(table)).use { c ->
                    require(c.moveToFirst()) { "Struktur database backup tidak sesuai" }
                }
            }
        }
    }

    private fun copyBounded(input: InputStream, output: OutputStream, maxBytes: Long) {
        val buffer = ByteArray(64 * 1024)
        var total = 0L
        while (true) {
            val count = input.read(buffer)
            if (count < 0) return
            total += count
            require(total <= maxBytes) { "Backup melebihi batas pemulihan 256 MB" }
            output.write(buffer, 0, count)
        }
    }

    private fun companionSnapshot(): JSONObject {
        val source = context.getSharedPreferences(COMPANION_PREFS, Context.MODE_PRIVATE)
        return JSONObject()
            .put("state", source.getString("state", ""))
            .put("experiences", source.getString("experiences", "[]"))
            .put("reflections", source.getString("reflections", "[]"))
            .put("memory_meta", source.getString("memory_meta", "{}"))
    }

    private fun restoreCompanionSnapshot(snapshot: JSONObject) {
        val editor = context.getSharedPreferences(COMPANION_PREFS, Context.MODE_PRIVATE).edit().clear()
        listOf("state", "experiences", "reflections", "memory_meta").forEach { key ->
            val value = snapshot.optString(key, "")
            if (value.isNotBlank()) editor.putString(key, value)
        }
        editor.apply()
    }

    private fun prune(root: DocumentFile) {
        root.listFiles().filter { it.isFile && it.name?.startsWith("Furina-") == true && it.name?.endsWith(".furina") == true }
            .sortedByDescending { it.lastModified() }
            .drop(KEEP_BACKUPS)
            .forEach { it.delete() }
        // Failed/abandoned temporary files are never considered valid backups.
        root.listFiles().filter { it.isFile && it.name?.startsWith("Furina-") == true && it.name?.endsWith(".partial") == true }
            .forEach { it.delete() }
    }

    private fun decodeKey(value: String): ByteArray {
        val bytes = Base64.decode(value, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
        require(bytes.size == 32) { "Recovery key tidak valid" }
        return bytes
    }
}
