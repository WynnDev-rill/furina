package com.wynndev.furina

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID
import kotlin.math.ln
import kotlin.math.min

class MemoryStore(private val context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {
    companion object {
        private const val DB_NAME = "furina_memory.db"
        private const val DB_VERSION = 1
    }

    override fun onConfigure(db: SQLiteDatabase) {
        super.onConfigure(db)
        db.setForeignKeyConstraintsEnabled(true)
        db.enableWriteAheadLogging()
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """.trimIndent())
        db.execSQL("""
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """.trimIndent())
        db.execSQL("CREATE INDEX idx_messages_session_time ON messages(session_id, created_at)")
        db.execSQL("CREATE INDEX idx_messages_time ON messages(created_at)")
        db.execSQL("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL DEFAULT 'fact',
                importance INTEGER NOT NULL DEFAULT 5,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """.trimIndent())
        try {
            db.execSQL("CREATE VIRTUAL TABLE message_fts USING fts4(content, message_id, session_id, role, created_at)")
        } catch (_: Throwable) {
            // Raw history remains available even on devices where FTS4 is unavailable.
        }
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    @Synchronized
    fun createSession(title: String = "Percakapan baru"): String {
        val id = UUID.randomUUID().toString()
        val now = System.currentTimeMillis()
        writableDatabase.insertOrThrow("sessions", null, ContentValues().apply {
            put("id", id); put("title", title); put("created_at", now); put("updated_at", now)
        })
        return id
    }

    @Synchronized
    fun ensureSession(id: String): String {
        readableDatabase.rawQuery("SELECT id FROM sessions WHERE id=?", arrayOf(id)).use {
            if (it.moveToFirst()) return id
        }
        val now = System.currentTimeMillis()
        writableDatabase.insert("sessions", null, ContentValues().apply {
            put("id", id); put("title", "Percakapan baru"); put("created_at", now); put("updated_at", now)
        })
        return id
    }

    @Synchronized
    fun addMessage(sessionId: String, role: String, content: String, createdAt: Long = System.currentTimeMillis()): String {
        ensureSession(sessionId)
        val id = UUID.randomUUID().toString()
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.insertOrThrow("messages", null, ContentValues().apply {
                put("id", id); put("session_id", sessionId); put("role", role); put("content", content); put("created_at", createdAt)
            })
            try {
                db.insert("message_fts", null, ContentValues().apply {
                    put("content", content); put("message_id", id); put("session_id", sessionId); put("role", role); put("created_at", createdAt.toString())
                })
            } catch (_: Throwable) {}
            db.execSQL("UPDATE sessions SET updated_at=? WHERE id=?", arrayOf(createdAt, sessionId))
            if (role == "user") {
                db.rawQuery("SELECT title FROM sessions WHERE id=?", arrayOf(sessionId)).use { c ->
                    if (c.moveToFirst() && c.getString(0) == "Percakapan baru") {
                        val title = content.replace(Regex("\\s+"), " ").trim().take(46).ifBlank { "Percakapan baru" }
                        db.execSQL("UPDATE sessions SET title=? WHERE id=?", arrayOf(title, sessionId))
                    }
                }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        if (role == "user") maybeRemember(content)
        return id
    }

    @Synchronized
    fun deleteSession(id: String) {
        writableDatabase.delete("sessions", "id=?", arrayOf(id))
        try { writableDatabase.delete("message_fts", "session_id=?", arrayOf(id)) } catch (_: Throwable) {}
    }

    @Synchronized
    fun sessionsJson(): String {
        val out = JSONArray()
        readableDatabase.rawQuery(
            "SELECT id,title,created_at,updated_at,(SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) FROM sessions s ORDER BY updated_at DESC",
            null,
        ).use { c ->
            while (c.moveToNext()) out.put(JSONObject()
                .put("id", c.getString(0)).put("title", c.getString(1))
                .put("createdAt", c.getLong(2)).put("updatedAt", c.getLong(3)).put("messageCount", c.getInt(4)))
        }
        return out.toString()
    }

    @Synchronized
    fun loadSessionJson(sessionId: String): String {
        val out = JSONArray()
        readableDatabase.rawQuery(
            "SELECT id,role,content,created_at FROM messages WHERE session_id=? ORDER BY created_at ASC",
            arrayOf(sessionId),
        ).use { c ->
            while (c.moveToNext()) out.put(JSONObject()
                .put("id", c.getString(0)).put("role", c.getString(1)).put("content", c.getString(2)).put("createdAt", c.getLong(3)))
        }
        return out.toString()
    }

    @Synchronized
    fun recentContext(sessionId: String, limit: Int = 12): String {
        val rows = mutableListOf<String>()
        readableDatabase.rawQuery(
            "SELECT role,content FROM messages WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            arrayOf(sessionId, limit.toString()),
        ).use { c -> while (c.moveToNext()) rows += "${if (c.getString(0) == "user") "USER" else "FURINA"}: ${c.getString(1)}" }
        return rows.asReversed().joinToString("\n")
    }

    @Synchronized
    fun relevantOldContext(query: String, currentSessionId: String, limit: Int = 8): String {
        val terms = query.lowercase().split(Regex("[^\\p{L}\\p{N}_]+"))
            .filter { it.length >= 3 }.distinct().take(8)
        if (terms.isEmpty()) return ""
        val rows = mutableListOf<String>()
        try {
            val match = terms.joinToString(" OR ") { "${it.replace("'", "")}*" }
            readableDatabase.rawQuery(
                "SELECT role,content,created_at FROM message_fts WHERE message_fts MATCH ? AND session_id<>? ORDER BY CAST(created_at AS INTEGER) DESC LIMIT ?",
                arrayOf(match, currentSessionId, limit.toString()),
            ).use { c ->
                while (c.moveToNext()) rows += "${if (c.getString(0) == "user") "USER" else "FURINA"}: ${c.getString(1)}"
            }
        } catch (_: Throwable) {
            val like = "%${terms.first()}%"
            readableDatabase.rawQuery(
                "SELECT role,content FROM messages WHERE session_id<>? AND lower(content) LIKE ? ORDER BY created_at DESC LIMIT ?",
                arrayOf(currentSessionId, like, limit.toString()),
            ).use { c -> while (c.moveToNext()) rows += "${if (c.getString(0) == "user") "USER" else "FURINA"}: ${c.getString(1)}" }
        }
        return rows.asReversed().joinToString("\n")
    }

    @Synchronized
    fun relevantMemories(query: String, limit: Int = 6): String {
        val terms = query.lowercase().split(Regex("[^\\p{L}\\p{N}]+" )).filter { it.length >= 3 }.toSet()
        val candidates = mutableListOf<Pair<Int, String>>()
        readableDatabase.rawQuery("SELECT content,importance FROM memories ORDER BY updated_at DESC LIMIT 300", null).use { c ->
            while (c.moveToNext()) {
                val content = c.getString(0)
                val overlap = content.lowercase().split(Regex("[^\\p{L}\\p{N}]+" )).count { it in terms }
                candidates += (overlap * 10 + c.getInt(1)) to content
            }
        }
        return candidates.sortedByDescending { it.first }.take(limit).filter { it.first > 0 }.joinToString("\n") { "- ${it.second}" }
    }

    @Synchronized
    fun buildBootstrapContext(query: String, sessionId: String): String {
        val recent = recentContext(sessionId, 12)
        val old = relevantOldContext(query, sessionId, 8)
        val facts = relevantMemories(query, 6)
        return buildString {
            appendLine("Relationship: ${relationshipSummary()}")
            if (facts.isNotBlank()) { appendLine("Known user facts:"); appendLine(facts) }
            if (old.isNotBlank()) { appendLine("Relevant older conversations:"); appendLine(old) }
            if (recent.isNotBlank()) { appendLine("Recent messages in this session:"); appendLine(recent) }
        }.trim()
    }

    @Synchronized
    fun relationshipSummary(): String {
        var userTurns = 0L
        var firstSeen = 0L
        var lastSeen = 0L
        readableDatabase.rawQuery("SELECT COUNT(*),MIN(created_at),MAX(created_at) FROM messages WHERE role='user'", null).use { c ->
            if (c.moveToFirst()) {
                userTurns = c.getLong(0)
                if (!c.isNull(1)) firstSeen = c.getLong(1)
                if (!c.isNull(2)) lastSeen = c.getLong(2)
            }
        }
        val familiarity = if (userTurns <= 0) 0.0 else min(1.0, ln(1.0 + userTurns.toDouble()) / ln(501.0))
        return "user turns=$userTurns, familiarity=${"%.2f".format(familiarity)}, first interaction=$firstSeen, last interaction=$lastSeen"
    }

    @Synchronized
    fun statsJson(): String {
        fun count(table: String): Long = readableDatabase.rawQuery("SELECT COUNT(*) FROM $table", null).use { c -> c.moveToFirst(); c.getLong(0) }
        var firstSeen = 0L
        readableDatabase.rawQuery("SELECT MIN(created_at) FROM messages", null).use { c -> if (c.moveToFirst() && !c.isNull(0)) firstSeen = c.getLong(0) }
        return JSONObject().put("sessions", count("sessions")).put("messages", count("messages"))
            .put("memories", count("memories")).put("firstSeen", firstSeen).put("relationship", relationshipSummary()).toString()
    }

    @Synchronized
    private fun maybeRemember(text: String) {
        val clean = text.replace(Regex("\\s+"), " ").trim()
        if (clean.length !in 15..360) return
        val lower = clean.lowercase()
        val triggers = listOf("aku ", "saya ", "suka ", "tidak suka", "favorit", "tinggal", "kerja", "pekerjaan", "target", "tujuan", "ingin ", "proyek", "project", "panggil aku", "ulang tahun")
        if (triggers.none { lower.contains(it) }) return
        val now = System.currentTimeMillis()
        writableDatabase.insertWithOnConflict("memories", null, ContentValues().apply {
            put("id", UUID.randomUUID().toString()); put("content", clean); put("kind", "user_fact")
            put("importance", 6); put("created_at", now); put("updated_at", now)
        }, SQLiteDatabase.CONFLICT_IGNORE)
    }

    @Synchronized
    fun checkpoint() {
        writableDatabase.rawQuery("PRAGMA wal_checkpoint(FULL)", null).use { while (it.moveToNext()) {} }
    }

    fun databaseFile(): File = context.getDatabasePath(DB_NAME)

    @Synchronized
    fun restoreFrom(file: File) {
        close()
        val target = databaseFile()
        target.parentFile?.mkdirs()
        File(target.absolutePath + "-wal").delete()
        File(target.absolutePath + "-shm").delete()
        file.copyTo(target, overwrite = true)
        readableDatabase.rawQuery("PRAGMA integrity_check", null).use { c ->
            require(c.moveToFirst() && c.getString(0).equals("ok", ignoreCase = true)) { "Backup database tidak valid" }
        }
    }
}
