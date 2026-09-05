package com.wynndev.furina

import android.app.Application
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class HubDataRepositoryTest {
    private lateinit var context: Context
    private lateinit var store: MemoryStore
    private lateinit var repository: HubDataRepository

    @Before fun setup() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase("furina_memory.db")
        context.getSharedPreferences("furinahub_native", 0).edit().clear().commit()
        store = MemoryStore(context)
        repository = HubDataRepository(context, store, TermuxBridgeClient(context))
    }
    @After fun tearDown() { store.close() }

    @Test fun versionFourUpgradePreservesMessagesAndAddsPinning() {
        store.close()
        context.deleteDatabase("furina_memory.db")
        val file = context.getDatabasePath("furina_memory.db")
        file.parentFile!!.mkdirs()
        SQLiteDatabase.openOrCreateDatabase(file, null).use { db ->
            db.execSQL("CREATE TABLE sessions (id TEXT PRIMARY KEY,title TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)")
            db.execSQL("CREATE TABLE messages (id TEXT PRIMARY KEY,session_id TEXT NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at INTEGER NOT NULL)")
            db.execSQL("INSERT INTO sessions VALUES ('legacy','Percakapan lama',1,1)")
            db.execSQL("INSERT INTO messages VALUES ('message','legacy','user','Jangan hilang',1)")
            db.version = 4
        }
        store = MemoryStore(context)
        assertEquals("Jangan hilang", JSONArray(store.loadSessionJson("legacy")).getJSONObject(0).getString("content"))
        store.pinSession("legacy", true)
        assertTrue(JSONArray(store.sessionsJson()).getJSONObject(0).getBoolean("pinned"))
        assertEquals(5, store.readableDatabase.version)
    }

    @Test fun pagingAndBranchesPreserveOriginalMessagesAndOrderForEqualTimestamps() = runBlocking {
        val id = repository.snapshot(HubSource.ANDROID).id
        val ids = (0..204).map { store.addMessage(id, if (it % 2 == 0) "user" else "assistant", "Pesan $it", 10, rememberFacts = false) }
        val page = repository.snapshot(HubSource.ANDROID)
        assertTrue(page.historyLimited)
        assertEquals(200, page.messages.size)
        assertEquals("Pesan 5", page.messages.first().content)
        assertEquals("Pesan 204", page.messages.last().content)
        val branch = repository.branchBefore(id, ids[4])
        assertNotEquals(id, branch.id)
        assertEquals(4, branch.messages.size)
        assertEquals(205, store.messageCountForSession(id))
    }

    @Test fun namespacedDraftsAndPersonaSurviveRepositoryRecreation() = runBlocking {
        val id = repository.snapshot(HubSource.ANDROID).id
        repository.saveDraft(HubSource.ANDROID, id, "draft Android")
        repository.saveDraft(HubSource.TERMUX, id, "draft Core")
        val p = HubPersona(name = "Nara", nickname = "Wynn", partner = true)
        repository.savePersona(p, true)
        val reloaded = HubDataRepository(context, store, TermuxBridgeClient(context))
        assertEquals(p, reloaded.persona())
        assertTrue(reloaded.personaPending())
        assertEquals("draft Android", reloaded.draft(HubSource.ANDROID, id))
        assertEquals("draft Core", reloaded.draft(HubSource.TERMUX, id))
    }

    @Test fun renamePinDeleteAndMemoryInvalidationUseTheSameStore() = runBlocking {
        val first = repository.snapshot(HubSource.ANDROID).id
        repository.conversation(HubSource.ANDROID, "rename", first, "  Percakapan   penting ")
        repository.conversation(HubSource.ANDROID, "pin", first, pinned = true)
        val second = repository.conversation(HubSource.ANDROID, "create")
        assertEquals(first, second.conversations.first().id)
        assertEquals("Percakapan penting", second.conversations.first().title)
        val memory = store.addMemory("Kode proyek zefir")
        assertTrue(store.relevantMemories("zefir").contains("zefir"))
        repository.changeMemory(HubSource.ANDROID, id = memory)
        assertFalse(store.relevantMemories("zefir").contains("zefir"))
        val after = repository.conversation(HubSource.ANDROID, "delete", second.id)
        assertNotEquals(second.id, after.id)
        assertTrue(after.conversations.any { it.id == first })
    }

    @Test fun exportingUsesFullArchiveInsteadOfVisiblePage() = runBlocking {
        val id = repository.snapshot(HubSource.ANDROID).id
        (0..201).forEach { store.addMessage(id, "user", "ARSIP_$it", it.toLong(), rememberFacts = false) }
        val text = repository.exportConversation(HubSource.ANDROID, id)
        assertTrue(text.contains("ARSIP_0\n"))
        assertTrue(text.contains("ARSIP_201"))
    }
}
