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

data class CompanionEmotionalState(
    val mood: String = "poised",
    val warmth: Int = 48,
    val trust: Int = 30,
    val irritation: Int = 8,
    val playfulness: Int = 52,
    val vulnerability: Int = 14,
    val protectiveness: Int = 35,
    val lastInputHash: Int = 0,
    val lastObservedAt: Long = 0L,
)

class MemoryStore(private val context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {
    companion object {
        private const val DB_NAME = "furina_memory.db"
        private const val DB_VERSION = 5
        private val CORE_MEMORY_KINDS = setOf(
            "profile_name",
            "profile_location",
            "profile_work",
            "profile_birthday",
            "profile_goal",
        )
    }

    private data class MemoryCandidate(
        val content: String,
        val kind: String,
        val importance: Int,
        val singleton: Boolean = false,
    )

    private var retrievalIndex: MemoryRetrievalIndex? = null

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
        createSettingsTable(db)
        createSummaryTable(db)
        db.execSQL("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) createSettingsTable(db)
        if (oldVersion < 3) createSummaryTable(db)
        if (oldVersion < 4) compactLegacyAutoMemories(db)
        if (oldVersion < 5) db.execSQL("ALTER TABLE sessions ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
    }

    private fun createSettingsTable(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL)")
    }

    private fun createSummaryTable(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                through_created_at INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """.trimIndent())
    }

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
    fun addMessage(sessionId: String, role: String, content: String, createdAt: Long = System.currentTimeMillis(), rememberFacts: Boolean = true): String {
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
            db.execSQL("UPDATE sessions SET updated_at=? WHERE id=?", arrayOf<Any>(createdAt, sessionId))
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
        if (role == "user" && rememberFacts) maybeRemember(content)
        return id
    }

    @Synchronized
    fun deleteSession(id: String) {
        writableDatabase.delete("sessions", "id=?", arrayOf(id))
        try { writableDatabase.delete("message_fts", "session_id=?", arrayOf(id)) } catch (_: Throwable) {}
    }

    @Synchronized
    fun clearSession(id: String) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.delete("messages", "session_id=?", arrayOf(id))
            db.delete("session_summaries", "session_id=?", arrayOf(id))
            try { db.delete("message_fts", "session_id=?", arrayOf(id)) } catch (_: Throwable) {}
            db.execSQL("UPDATE sessions SET title='Percakapan baru', updated_at=? WHERE id=?", arrayOf<Any>(System.currentTimeMillis(), id))
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    @Synchronized
    fun sessionsJson(): String {
        val out = JSONArray()
        readableDatabase.rawQuery(
            "SELECT id,title,created_at,updated_at,(SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id),pinned FROM sessions s ORDER BY pinned DESC,updated_at DESC",
            null,
        ).use { c ->
            while (c.moveToNext()) out.put(JSONObject()
                .put("id", c.getString(0)).put("title", c.getString(1))
                .put("createdAt", c.getLong(2)).put("updatedAt", c.getLong(3)).put("messageCount", c.getInt(4)).put("pinned", c.getInt(5) != 0))
        }
        return out.toString()
    }

    @Synchronized
    fun loadSessionJson(sessionId: String, limit: Int = Int.MAX_VALUE): String {
        val out = JSONArray()
        readableDatabase.rawQuery(
            "SELECT id,role,content,created_at FROM (SELECT rowid AS sequence,id,role,content,created_at FROM messages WHERE session_id=? ORDER BY created_at DESC,rowid DESC LIMIT ?) ORDER BY created_at ASC,sequence ASC",
            arrayOf(sessionId, limit.coerceAtLeast(1).toString()),
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
    fun lastUserMessage(sessionId: String): String {
        readableDatabase.rawQuery(
            "SELECT content FROM messages WHERE session_id=? AND role='user' ORDER BY created_at DESC LIMIT 1",
            arrayOf(sessionId),
        ).use { c -> return if (c.moveToFirst()) c.getString(0) else "" }
    }

    @Synchronized
    fun sessionSummary(sessionId: String): String {
        readableDatabase.rawQuery(
            "SELECT summary FROM session_summaries WHERE session_id=?",
            arrayOf(sessionId),
        ).use { c -> return if (c.moveToFirst()) c.getString(0) else "" }
    }

    /**
     * Offline deterministic compaction. It deliberately makes no second model call,
     * so memory maintenance remains reliable even on slow or unavailable providers.
     */
    @Synchronized
    fun updateSessionSummary(sessionId: String, keepRecent: Int = 10) {
        val total = readableDatabase.rawQuery(
            "SELECT COUNT(*) FROM messages WHERE session_id=?",
            arrayOf(sessionId),
        ).use { c -> c.moveToFirst(); c.getInt(0) }
        if (total <= keepRecent) return

        val compactable = total - keepRecent
        val rows = mutableListOf<Triple<String, String, Long>>()
        readableDatabase.rawQuery(
            "SELECT role,content,created_at FROM messages WHERE session_id=? ORDER BY created_at ASC LIMIT ?",
            arrayOf(sessionId, compactable.toString()),
        ).use { c ->
            while (c.moveToNext()) rows += Triple(c.getString(0), c.getString(1), c.getLong(2))
        }
        if (rows.isEmpty()) return

        val selected = if (rows.size <= 28) rows else rows.take(6) + rows.takeLast(22)
        val summary = buildString {
            appendLine("Ringkasan percakapan terdahulu:")
            selected.forEach { (role, content, _) ->
                val clean = content.replace(Regex("\\s+"), " ").trim().take(220)
                if (clean.isNotBlank()) appendLine("- ${if (role == "user") "Pengguna" else "Furina"}: $clean")
            }
        }.trim().take(5_600)
        val now = System.currentTimeMillis()
        writableDatabase.insertWithOnConflict("session_summaries", null, ContentValues().apply {
            put("session_id", sessionId)
            put("summary", summary)
            put("through_created_at", rows.last().third)
            put("message_count", compactable)
            put("updated_at", now)
        }, SQLiteDatabase.CONFLICT_REPLACE)
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
        val index = retrievalIndex ?: MemoryRetrievalIndex(buildList {
            readableDatabase.rawQuery("SELECT id,content,importance,kind,updated_at FROM memories", null).use { c ->
                while (c.moveToNext()) add(IndexedMemory(c.getString(0), c.getString(1), c.getInt(2), c.getLong(4), c.getString(3) in CORE_MEMORY_KINDS || c.getInt(2) >= 9))
            }
        }).also { retrievalIndex = it }
        return index.search(query, limit).joinToString("\n") { "- $it" }
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
            .put("memories", count("memories")).put("summaries", count("session_summaries"))
            .put("firstSeen", firstSeen).put("relationship", relationshipSummary()).toString()
    }

    @Synchronized
    fun memoriesJson(): String {
        val out = JSONArray()
        readableDatabase.rawQuery(
            "SELECT id,content,kind,importance,created_at,updated_at FROM memories ORDER BY importance DESC, updated_at DESC",
            null,
        ).use { c ->
            while (c.moveToNext()) out.put(JSONObject()
                .put("id", c.getString(0)).put("content", c.getString(1)).put("kind", c.getString(2))
                .put("importance", c.getInt(3)).put("createdAt", c.getLong(4)).put("updatedAt", c.getLong(5)))
        }
        return out.toString()
    }

    @Synchronized
    fun addMemory(content: String): String {
        val clean = normalizeText(content)
        require(clean.length in 3..500) { "Memori harus berisi 3–500 karakter" }
        val extracted = extractMemoryCandidates(clean)
        if (extracted.size == 1) return upsertMemory(writableDatabase, extracted.first().copy(importance = maxOf(8, extracted.first().importance)))
        return upsertMemory(writableDatabase, MemoryCandidate(clean, "manual_fact", 8))
    }

    @Synchronized
    fun deleteMemory(id: String) {
        retrievalIndex = null
        writableDatabase.delete("memories", "id=?", arrayOf(id))
    }

    @Synchronized
    fun clearMemories() {
        retrievalIndex = null
        writableDatabase.delete("memories", null, null)
    }

    @Synchronized
    fun appSettingsJson(): String {
        readableDatabase.rawQuery("SELECT value FROM app_settings WHERE key='ui'", null).use { c ->
            if (c.moveToFirst()) return c.getString(0)
        }
        return "{}"
    }

    @Synchronized
    fun saveAppSettingsJson(raw: String) {
        val normalized = JSONObject(raw).toString()
        writableDatabase.insertWithOnConflict("app_settings", null, ContentValues().apply {
            put("key", "ui"); put("value", normalized); put("updated_at", System.currentTimeMillis())
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    /**
     * Evolves a small, deterministic emotional state without a second model call.
     * It lives in app_settings, so it survives sessions, provider changes, and backups.
     */
    @Synchronized
    fun observeUserTurn(text: String) {
        val clean = normalizeText(text).lowercase()
        if (clean.isBlank()) return
        val now = System.currentTimeMillis()
        val previous = companionState()
        if (previous.lastInputHash == clean.hashCode() && now - previous.lastObservedAt < 120_000L) return

        fun String.hasAny(words: List<String>) = words.any { contains(it) }
        val affectionate = clean.hasAny(listOf("terima kasih", "makasih", "sayang", "kangen", "rindu", "bangga sama kamu", "aku suka kamu", "love you"))
        val apologetic = clean.hasAny(listOf("maaf", "sorry", "aku salah"))
        val distressed = clean.hasAny(listOf("sedih", "takut", "cemas", "khawatir", "capek", "lelah", "sakit", "sendirian", "menangis", "menyerah"))
        val insulting = clean.hasAny(listOf("kamu bodoh", "dasar bodoh", "aku benci kamu", "tidak berguna", "menyebalkan sekali", "diam kamu"))
        val playful = clean.hasAny(listOf("wkwk", "haha", "hehe", "bercanda", "lucu", "goda", "cie"))

        var warmth = approach(previous.warmth, 48, 1)
        var trust = if (!insulting && previous.trust < 82) previous.trust + 1 else previous.trust
        var irritation = approach(previous.irritation, 8, 2)
        var playfulness = approach(previous.playfulness, 52, 1)
        var vulnerability = approach(previous.vulnerability, 14, 1)
        var protectiveness = approach(previous.protectiveness, 35, 1)

        if (affectionate) { warmth += 9; trust += 4; vulnerability += 5; irritation -= 5 }
        if (apologetic) { warmth += 3; trust += 2; irritation -= 12 }
        if (distressed) { warmth += 7; protectiveness += 15; playfulness -= 12 }
        if (insulting) { irritation += 24; warmth -= 7; trust -= 8; vulnerability -= 4 }
        if (playful) { playfulness += 15; warmth += 3; irritation -= 3 }

        warmth = warmth.coerceIn(0, 100)
        trust = trust.coerceIn(0, 100)
        irritation = irritation.coerceIn(0, 100)
        playfulness = playfulness.coerceIn(0, 100)
        vulnerability = vulnerability.coerceIn(0, 100)
        protectiveness = protectiveness.coerceIn(0, 100)
        val mood = when {
            distressed -> "protective"
            insulting || irritation >= 55 -> "annoyed"
            affectionate -> "flustered"
            playful || playfulness >= 72 -> "playful"
            warmth >= 70 && trust >= 55 -> "soft"
            else -> "poised"
        }
        saveCompanionState(CompanionEmotionalState(
            mood, warmth, trust, irritation, playfulness, vulnerability, protectiveness,
            clean.hashCode(), now,
        ))
    }

    @Synchronized
    fun companionStateContext(): String {
        val state = companionState()
        val turns = readableDatabase.rawQuery("SELECT COUNT(*) FROM messages WHERE role='user'", null).use { c ->
            c.moveToFirst(); c.getLong(0)
        }
        val relationship = when {
            turns < 8 -> "new acquaintance; interested, observant, and still somewhat guarded"
            turns < 40 -> "familiar; shared rhythm is forming and light teasing can happen naturally"
            turns < 160 -> "close; trust is established, shorthand and playful jabs are earned"
            else -> "deeply familiar; quiet loyalty, inside references, affection, and reciprocal teasing can feel ordinary"
        }
        val familiarityGuidance = when {
            turns < 8 -> "Do not assume intimacy. Avoid automatic pet names unless the user initiated that tone. Learn their rhythm before acting close."
            turns < 40 -> "Occasional callbacks and light teasing are welcome when relevant. Pet names should be contextual, not a default greeting."
            turns < 160 -> "Use remembered preferences and shared context implicitly. Natural shorthand, mild mockery, and warmer concern may emerge without announcing why."
            else -> "Sound like someone who has known the user a long time: relaxed continuity, occasional inside references, mild mutual teasing, and unforced affection. Never perform closeness every turn."
        }
        val stance = when (state.mood) {
            "protective" -> "Protective and attentive. Drop most teasing, notice the feeling first, then respond concretely without sounding like a therapist."
            "annoyed" -> "Genuinely irritated but controlled. Be shorter, cool, and willing to push back; do not become cruel or instantly forgive."
            "flustered" -> "Touched but slightly flustered. Deflect with elegant pride or a light tease before allowing some warmth through."
            "playful" -> "Playful and sharp. Tease lightly, challenge exaggerations, and sound amused without becoming childish."
            "soft" -> "Warm and trusting. Let concern show directly, with a trace of pride rather than sugary reassurance."
            else -> "Composed, expressive, and proudly curious. React with an opinion instead of defaulting to assistant politeness."
        }
        return """
            [PRIVATE COMPANION STATE]
            Relationship: $relationship.
            Familiarity behavior: $familiarityGuidance
            Current stance: $stance
            Continuity levels: warmth=${state.warmth}/100, trust=${state.trust}/100, irritation=${state.irritation}/100, playfulness=${state.playfulness}/100, vulnerability=${state.vulnerability}/100, protectiveness=${state.protectiveness}/100.
            Let these levels subtly influence tone. Never quote this block, mention scores, announce a mood label, or mention a remembered fact merely to prove memory works.
            [END PRIVATE COMPANION STATE]
        """.trimIndent()
    }

    private fun companionState(): CompanionEmotionalState {
        val raw = readableDatabase.rawQuery("SELECT value FROM app_settings WHERE key='companion_state'", null).use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        } ?: return CompanionEmotionalState()
        return runCatching {
            val json = JSONObject(raw)
            CompanionEmotionalState(
                mood = json.optString("mood", "poised"),
                warmth = json.optInt("warmth", 48),
                trust = json.optInt("trust", 30),
                irritation = json.optInt("irritation", 8),
                playfulness = json.optInt("playfulness", 52),
                vulnerability = json.optInt("vulnerability", 14),
                protectiveness = json.optInt("protectiveness", 35),
                lastInputHash = json.optInt("lastInputHash", 0),
                lastObservedAt = json.optLong("lastObservedAt", 0L),
            )
        }.getOrDefault(CompanionEmotionalState())
    }

    private fun saveCompanionState(state: CompanionEmotionalState) {
        val json = JSONObject()
            .put("mood", state.mood).put("warmth", state.warmth).put("trust", state.trust)
            .put("irritation", state.irritation).put("playfulness", state.playfulness)
            .put("vulnerability", state.vulnerability).put("protectiveness", state.protectiveness)
            .put("lastInputHash", state.lastInputHash).put("lastObservedAt", state.lastObservedAt)
        writableDatabase.insertWithOnConflict("app_settings", null, ContentValues().apply {
            put("key", "companion_state"); put("value", json.toString()); put("updated_at", System.currentTimeMillis())
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    private fun approach(value: Int, target: Int, step: Int): Int = when {
        value < target -> (value + step).coerceAtMost(target)
        value > target -> (value - step).coerceAtLeast(target)
        else -> value
    }

    @Synchronized
    private fun maybeRemember(text: String) {
        val clean = normalizeText(text)
        if (clean.length !in 5..600) return
        val candidates = extractMemoryCandidates(clean)
        if (candidates.isEmpty()) return
        candidates.take(4).forEach { upsertMemory(writableDatabase, it) }
    }

    private fun extractMemoryCandidates(text: String): List<MemoryCandidate> {
        val clean = normalizeText(text)
        if (clean.isBlank()) return emptyList()
        val out = mutableListOf<MemoryCandidate>()
        val segments = clean.split(Regex("(?<=[.!?;])\\s+|[;\\n]+"))
            .map(::normalizeText)
            .filter { it.length >= 3 }
            .take(8)

        fun match(segment: String, pattern: String): String? =
            Regex(pattern, RegexOption.IGNORE_CASE).find(segment)
                ?.groupValues?.getOrNull(1)
                ?.let(::cleanMemoryValue)
                ?.takeIf { it.length >= 1 }

        for (segment in segments) {
            val name = match(segment, """\b(?:panggil(?:lah)? aku|panggil saya|namaku(?: adalah)?|nama saya(?: adalah)?|call me)\s+([^,.!?;]{1,60})""")
            if (name != null) {
                out += MemoryCandidate("Panggilan pengguna: $name", "profile_name", 10, singleton = true)
                continue
            }

            val dislike = match(segment, """\b(?:aku|saya)\s+(?:sangat\s+)?(?:tidak suka|tidak menyukai|benci)\s+([^,.!?;]{2,120})""")
            if (dislike != null) {
                out += MemoryCandidate("Pengguna tidak menyukai $dislike", "preference_dislike", 7)
                continue
            }

            val like = match(segment, """\b(?:aku|saya)\s+(?:sangat\s+)?(?:menyukai|suka)\s+([^,.!?;]{2,120})""")
            if (like != null) {
                out += MemoryCandidate("Pengguna menyukai $like", "preference_like", 7)
                continue
            }

            val favorite = match(segment, """\b(?:favoritku|favorit saya)(?: adalah)?\s+([^,.!?;]{2,120})""")
            if (favorite != null) {
                out += MemoryCandidate("Favorit pengguna: $favorite", "preference_favorite", 8)
                continue
            }

            val location = match(segment, """\b(?:aku|saya)\s+(?:tinggal|berdomisili)\s+(?:di\s+)?([^,.!?;]{2,120})""")
            if (location != null) {
                out += MemoryCandidate("Pengguna tinggal di $location", "profile_location", 9, singleton = true)
                continue
            }

            val work = match(segment, """\b(?:aku|saya)\s+(?:bekerja sebagai|kerja sebagai|berprofesi sebagai|adalah seorang)\s+([^,.!?;]{2,120})""")
            if (work != null) {
                out += MemoryCandidate("Pekerjaan pengguna: $work", "profile_work", 9, singleton = true)
                continue
            }

            val birthday = match(segment, """\b(?:ulang tahunku|ulang tahun saya)(?: adalah| tanggal)?\s+([^,.!?;]{2,100})""")
            if (birthday != null) {
                out += MemoryCandidate("Ulang tahun pengguna: $birthday", "profile_birthday", 10, singleton = true)
                continue
            }

            val goal = match(segment, """\b(?:targetku|tujuanku|target saya|tujuan saya)(?: adalah)?\s+([^.!?;]{2,160})""")
            if (goal != null) {
                out += MemoryCandidate("Tujuan pengguna: $goal", "profile_goal", 8, singleton = true)
                continue
            }

            val explicit = match(segment, """\b(?:tolong\s+ingat(?:lah)?|ingat(?:lah)?|simpan(?: ini)?(?: di memori(?:mu)?)?|remember(?: that)?)\s*[:,.-]?\s*(.+)""")
            if (explicit != null && !explicit.equals("itu", ignoreCase = true) && explicit.length >= 3) {
                out += MemoryCandidate("Catatan pengguna: $explicit", "explicit_memory", 9)
            }
        }
        return out.distinctBy { "${it.kind}:${it.content.lowercase()}" }
    }

    private fun normalizeText(value: String): String = value.replace(Regex("\\s+"), " ").trim()

    private fun cleanMemoryValue(value: String): String = normalizeText(value)
        .trim(' ', ',', '.', '!', '?', ';', ':', '-', '—')
        .replace(Regex("(?i)\\s*,?\\s*(?:coba|tolong)?\\s*(?:ingat|simpan)(?:lah)?(?: itu| ini)?(?: di memori(?:mu)?)?\\s*$"), "")
        .trim()
        .take(180)

    private fun upsertMemory(db: SQLiteDatabase, candidate: MemoryCandidate): String {
        retrievalIndex = null
        val content = normalizeText(candidate.content).take(500)
        if (content.length < 3) return ""
        val now = System.currentTimeMillis()

        db.rawQuery("SELECT id,importance FROM memories WHERE content=? LIMIT 1", arrayOf(content)).use { c ->
            if (c.moveToFirst()) {
                val id = c.getString(0)
                val importance = maxOf(c.getInt(1), candidate.importance).coerceAtMost(10)
                db.update("memories", ContentValues().apply {
                    put("kind", candidate.kind)
                    put("importance", importance)
                    put("updated_at", now)
                }, "id=?", arrayOf(id))
                return id
            }
        }

        if (candidate.singleton) {
            db.rawQuery("SELECT id FROM memories WHERE kind=? ORDER BY updated_at DESC LIMIT 1", arrayOf(candidate.kind)).use { c ->
                if (c.moveToFirst()) {
                    val id = c.getString(0)
                    db.delete("memories", "content=? AND id<>?", arrayOf(content, id))
                    db.update("memories", ContentValues().apply {
                        put("content", content)
                        put("importance", candidate.importance.coerceIn(1, 10))
                        put("updated_at", now)
                    }, "id=?", arrayOf(id))
                    return id
                }
            }
        }

        val id = UUID.randomUUID().toString()
        db.insertWithOnConflict("memories", null, ContentValues().apply {
            put("id", id)
            put("content", content)
            put("kind", candidate.kind)
            put("importance", candidate.importance.coerceIn(1, 10))
            put("created_at", now)
            put("updated_at", now)
        }, SQLiteDatabase.CONFLICT_IGNORE)
        db.rawQuery("SELECT id FROM memories WHERE content=? LIMIT 1", arrayOf(content)).use { c ->
            return if (c.moveToFirst()) c.getString(0) else id
        }
    }

    private fun compactLegacyAutoMemories(db: SQLiteDatabase) {
        val legacy = mutableListOf<Pair<String, String>>()
        db.rawQuery(
            "SELECT id,content FROM memories WHERE kind='user_fact' AND importance<=6",
            null,
        ).use { c ->
            while (c.moveToNext()) legacy += c.getString(0) to c.getString(1)
        }
        if (legacy.isEmpty()) return
        db.beginTransaction()
        try {
            legacy.forEach { (id, raw) ->
                val extracted = extractMemoryCandidates(raw)
                db.delete("memories", "id=?", arrayOf(id))
                extracted.take(4).forEach { upsertMemory(db, it) }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    @Synchronized
    fun checkpoint() {
        writableDatabase.rawQuery("PRAGMA wal_checkpoint(FULL)", null).use { while (it.moveToNext()) {} }
    }

    fun databaseFile(): File = context.getDatabasePath(DB_NAME)

    /** SQLite produces a consistent standalone file, including committed WAL pages. */
    @Synchronized
    fun writeSnapshot(target: File) {
        require(!target.exists() || target.length() == 0L) { "Tujuan snapshot sudah berisi data" }
        writableDatabase.execSQL("VACUUM INTO ?", arrayOf(target.absolutePath))
    }

    @Synchronized
    fun restoreFrom(file: File) {
        retrievalIndex = null
        checkpoint()
        val target = databaseFile()
        val safety = File(context.cacheDir, "furina-before-restore-${System.currentTimeMillis()}.db")
        if (target.exists()) writeSnapshot(safety)
        close()
        target.parentFile?.mkdirs()
        File(target.absolutePath + "-wal").delete()
        File(target.absolutePath + "-shm").delete()
        try {
            file.copyTo(target, overwrite = true)
            readableDatabase.rawQuery("PRAGMA integrity_check", null).use { c ->
                require(c.moveToFirst() && c.getString(0).equals("ok", ignoreCase = true)) { "Backup database tidak valid" }
            }
        } catch (e: Throwable) {
            close()
            File(target.absolutePath + "-wal").delete()
            File(target.absolutePath + "-shm").delete()
            if (safety.exists()) safety.copyTo(target, overwrite = true) else target.delete()
            readableDatabase
            throw e
        } finally {
            safety.delete()
        }
    }

    @Synchronized
    fun hubValue(key: String): String? = readableDatabase.rawQuery(
        "SELECT value FROM app_settings WHERE key=?", arrayOf("hub:$key"),
    ).use { if (it.moveToFirst()) it.getString(0) else null }

    @Synchronized
    fun putHubValue(key: String, value: String) {
        writableDatabase.insertWithOnConflict("app_settings", null, ContentValues().apply {
            put("key", "hub:$key"); put("value", value); put("updated_at", System.currentTimeMillis())
        }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    @Synchronized
    fun putHubValues(values: Map<String, String>) {
        val db = writableDatabase
        db.beginTransaction()
        try { values.forEach { (key, value) -> putHubValue(key, value) }; db.setTransactionSuccessful() }
        finally { db.endTransaction() }
    }

    @Synchronized
    fun renameSession(id: String, title: String) {
        val clean = title.replace(Regex("\\s+"), " ").trim().take(72)
        require(clean.isNotBlank()) { "Judul tidak boleh kosong" }
        require(writableDatabase.update("sessions", ContentValues().apply { put("title", clean) }, "id=?", arrayOf(id)) == 1) { "Percakapan tidak ditemukan" }
    }

    @Synchronized
    fun pinSession(id: String, pinned: Boolean) {
        require(writableDatabase.update("sessions", ContentValues().apply { put("pinned", if (pinned) 1 else 0) }, "id=?", arrayOf(id)) == 1) { "Percakapan tidak ditemukan" }
    }

    /** A non-destructive branch: preserve the old conversation and copy only the selected prefix. */
    @Synchronized
    fun branchBefore(sessionId: String, messageId: String): String {
        val messages = JSONArray(loadSessionJson(sessionId))
        val index = (0 until messages.length()).firstOrNull { messages.getJSONObject(it).getString("id") == messageId }
            ?: error("Pesan tidak ditemukan")
        val db = writableDatabase
        db.beginTransaction()
        try {
            val next = createSession("Cabang percakapan")
            for (i in 0 until index) {
                val row = messages.getJSONObject(i)
                addMessage(next, row.getString("role"), row.getString("content"), row.optLong("createdAt"), rememberFacts = false)
            }
            db.setTransactionSuccessful()
            return next
        } finally { db.endTransaction() }
    }
}
