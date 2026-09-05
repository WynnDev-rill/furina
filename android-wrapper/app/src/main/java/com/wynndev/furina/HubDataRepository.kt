package com.wynndev.furina

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** One boundary for data ownership. Remote numeric IDs are never passed to Android SQLite. */
internal class HubDataRepository(context: Context, private val store: MemoryStore, private val bridge: TermuxBridgeClient) {
    private val legacy = context.getSharedPreferences("furinahub_native", Context.MODE_PRIVATE)

    fun persona(): HubPersona {
        store.hubValue("persona")?.let { return HubPersona.parse(JSONObject(it)) }
        val migrated = HubPersona(
            legacy.getString("assistant_name", "Furina").orEmpty(), legacy.getString("user_nickname", "").orEmpty(),
            legacy.getStringSet("traits", emptySet()).orEmpty().toSet(), legacy.getBoolean("partner_mode", false),
            legacy.getBoolean("roleplay_mode", false), legacy.getBoolean("full_local_memory", false),
            legacy.getBoolean("training_suggestions", false), legacy.getBoolean("inner_thoughts", false),
            legacy.getString("custom_instructions", "").orEmpty(),
        )
        savePersona(migrated, false)
        return migrated
    }

    fun savePersona(persona: HubPersona, dirty: Boolean) {
        store.putHubValues(mapOf("persona" to persona.json().toString(), "persona_dirty" to dirty.toString()))
    }

    fun personaPending(): Boolean = store.hubValue("persona_dirty") == "true"

    suspend fun syncPersona(): HubPersona = withContext(Dispatchers.IO) {
        if (personaPending()) {
            val next = persona()
            bridge.post("/api/settings", JSONObject().put("hub", next.json())
                .put("core", JSONObject().put("persona_name", next.name).put("user_nickname", next.nickname)))
            // The controller serializes edits/syncs so a newer local edit cannot be acknowledged here.
            savePersona(next, false)
        }
        persona()
    }

    suspend fun snapshot(source: HubSource, limit: Int = 200): HubSnapshot = withContext(Dispatchers.IO) {
        if (source == HubSource.TERMUX) {
            syncPersona()
            parseRemote(bridge.get("/api/bootstrap"))
        } else {
            var id = store.hubValue("local_session") ?: legacy.getString("local_session", "").orEmpty()
            if (id.isBlank()) id = store.createSession()
            store.ensureSession(id)
            store.putHubValue("local_session", id)
            val history = JSONArray(store.loadSessionJson(id, limit))
            HubSnapshot(source, id, history.toMessages(), JSONArray(store.sessionsJson()).toConversations(),
                persona(), store.messageCountForSession(id) > history.length())
        }
    }

    private fun parseRemote(boot: JSONObject): HubSnapshot {
        require(boot.has("active_conversation_id") && boot.optJSONArray("history") != null) { "Respons bootstrap Core tidak lengkap" }
        val settings = boot.optJSONObject("settings") ?: JSONObject()
        if (boot.has("assistant_name")) settings.put("assistant_name", boot.get("assistant_name"))
        if (boot.has("user_nickname")) settings.put("user_nickname", boot.get("user_nickname"))
        val profile = HubPersona.parse(settings, persona())
        savePersona(profile, false)
        return HubSnapshot(HubSource.TERMUX, boot.get("active_conversation_id").toString(),
            boot.optJSONArray("history").toMessages(), boot.optJSONArray("conversations").toConversations(), profile,
            historyLimited = true, coreVersion = boot.optString("core_version"))
    }

    suspend fun conversation(source: HubSource, action: String, id: String = "", title: String = "", pinned: Boolean = false): HubSnapshot = withContext(Dispatchers.IO) {
        if (source == HubSource.TERMUX) {
            val payload = JSONObject().put("action", action).put("title", title).put("pinned", pinned)
            if (id.isNotBlank()) payload.put("id", id.toLong())
            parseRemote(bridge.post("/api/conversations", payload))
        } else {
            when (action) {
                "create" -> store.putHubValue("local_session", store.createSession())
                "switch" -> { require(JSONArray(store.sessionsJson()).toConversations().any { it.id == id }) { "Percakapan tidak ditemukan" }; store.putHubValue("local_session", id) }
                "delete" -> {
                    store.deleteSession(id)
                    if (store.hubValue("local_session") == id) store.putHubValue("local_session", store.createSession())
                }
                "rename" -> store.renameSession(id, title)
                "pin" -> store.pinSession(id, pinned)
                else -> error("Aksi percakapan tidak dikenal")
            }
            snapshot(source)
        }
    }

    suspend fun memories(source: HubSource): List<HubMemory> = withContext(Dispatchers.IO) {
        if (source == HubSource.TERMUX) bridge.get("/api/memory").optJSONArray("memories").toMemories()
        else JSONArray(store.memoriesJson()).toMemories()
    }

    suspend fun changeMemory(source: HubSource, text: String? = null, id: String? = null) = withContext(Dispatchers.IO) {
        if (text != null) require(text.trim().length in 4..500) { "Memori harus berisi 4–500 karakter" }
        if (source == HubSource.TERMUX) {
            bridge.post("/api/memory", if (id != null) JSONObject().put("action", "delete").put("id", id.toLong())
                else JSONObject().put("action", "add").put("text", text!!.trim()))
        } else {
            if (id != null) store.deleteMemory(id) else store.addMemory(text!!.trim())
        }
    }

    suspend fun draft(source: HubSource, id: String): String = withContext(Dispatchers.IO) { store.hubValue("draft:${source.name}:$id").orEmpty() }
    suspend fun saveDraft(source: HubSource, id: String, value: String) = withContext(Dispatchers.IO) {
        if (id.isNotBlank()) store.putHubValue("draft:${source.name}:$id", value.take(12_000))
    }

    suspend fun branchBefore(id: String, message: String): HubSnapshot = withContext(Dispatchers.IO) {
        store.putHubValue("local_session", store.branchBefore(id, message))
        snapshot(HubSource.ANDROID)
    }

    suspend fun exportConversation(source: HubSource, id: String): String = withContext(Dispatchers.IO) {
        val rows = if (source == HubSource.ANDROID) JSONArray(store.loadSessionJson(id)).toMessages()
        else snapshot(source).also { require(it.id == id) { "Percakapan Core telah berubah" } }.messages
        buildString {
            appendLine("# FurinaHub — ${persona().name}")
            if (source == HubSource.TERMUX) appendLine("Ekspor jendela riwayat yang tersedia dari Core; bukan seluruh arsip.")
            rows.forEach { appendLine("\n## ${if (it.role == "user") "Pengguna" else persona().name}\n\n${it.content}") }
        }
    }
}

internal data class HubSnapshot(val source: HubSource, val id: String, val messages: List<HubMessage>, val conversations: List<HubConversation>,
    val persona: HubPersona, val historyLimited: Boolean, val coreVersion: String = "")

internal data class HubPersona(
    val name: String = "Furina", val nickname: String = "", val traits: Set<String> = emptySet(),
    val partner: Boolean = false, val roleplay: Boolean = false, val fullMemory: Boolean = false,
    val training: Boolean = false, val innerThoughts: Boolean = false, val instructions: String = "",
) {
    fun json(): JSONObject = JSONObject().put("assistant_name", name).put("user_nickname", nickname)
        .put("personality_traits", JSONArray(traits.toList())).put("partner_mode", partner).put("roleplay_mode", roleplay)
        .put("full_local_memory", fullMemory).put("training_suggestions", training).put("inner_thoughts", innerThoughts)
        .put("custom_instructions", instructions)

    fun applyTo(state: HubUiState): HubUiState = state.copy(assistantName = name, userNickname = nickname, selectedTraits = traits,
        partnerMode = partner, roleplayMode = roleplay, fullLocalMemory = fullMemory, trainingSuggestions = training,
        innerThoughts = innerThoughts, customInstructions = instructions)

    companion object {
        fun parse(data: JSONObject, fallback: HubPersona = HubPersona()): HubPersona = HubPersona(
            data.optString("assistant_name", fallback.name).trim().take(48).ifBlank { "Furina" },
            data.optString("user_nickname", fallback.nickname).trim().take(48),
            data.optJSONArray("personality_traits")?.let { a -> (0 until a.length()).map { a.optString(it) }.filter { id -> FurinaTraits.any { it.id == id } }.toSet() } ?: fallback.traits,
            data.optBoolean("partner_mode", fallback.partner), data.optBoolean("roleplay_mode", fallback.roleplay),
            data.optBoolean("full_local_memory", fallback.fullMemory), data.optBoolean("training_suggestions", fallback.training),
            data.optBoolean("inner_thoughts", fallback.innerThoughts), data.optString("custom_instructions", fallback.instructions).take(2_000),
        )
    }
}

internal fun JSONArray?.toMessages(): List<HubMessage> = this?.let { a -> (0 until a.length()).mapNotNull { i ->
    val row = a.optJSONObject(i) ?: return@mapNotNull null
    val role = row.optString("role")
    if (role !in setOf("user", "assistant")) return@mapNotNull null
    HubMessage(row.opt("id")?.takeUnless { it == JSONObject.NULL }?.toString() ?: "message-$i", role,
        row.optString("content", row.optString("text")))
}.distinctBy { it.id } } ?: emptyList()

internal fun JSONArray?.toConversations(): List<HubConversation> = this?.let { a -> (0 until a.length()).mapNotNull { i ->
    val row = a.optJSONObject(i) ?: return@mapNotNull null
    val id = row.opt("id")?.takeUnless { it == JSONObject.NULL }?.toString() ?: return@mapNotNull null
    HubConversation(id, row.optString("title").ifBlank { "Percakapan baru" }, row.optInt("messageCount", row.optInt("message_count")), row.optBoolean("pinned"))
}.distinctBy { it.id } } ?: emptyList()

internal fun JSONArray?.toMemories(): List<HubMemory> = this?.let { a -> (0 until a.length()).mapNotNull { i ->
    val row = a.optJSONObject(i) ?: return@mapNotNull null
    val id = row.opt("id")?.takeUnless { it == JSONObject.NULL }?.toString() ?: return@mapNotNull null
    HubMemory(id, row.optString("text", row.optString("content")), row.optString("kind", "memory"))
}.distinctBy { it.id } } ?: emptyList()
