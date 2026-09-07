package com.wynndev.furina

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
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
class TurnRecoveryTest {
    private lateinit var context: Context
    private lateinit var store: MemoryStore
    @Before fun setup() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase("furina_memory.db")
        store = MemoryStore(context)
    }
    @After fun close() { store.close() }

    @Test fun processRestartRecoversOnlyCheckpointedReplyAndDoesNotDuplicateIt() {
        val session = store.createSession()
        store.putHubValue("draft:ANDROID:$session", "Pertanyaan")
        store.beginTurn("request", session, "Pertanyaan")
        store.checkpointTurn("request", "Jawaban yang terlihat")
        store.close()
        store = MemoryStore(context)
        assertEquals(1, store.recoverInterruptedTurns())
        assertEquals(0, store.recoverInterruptedTurns())
        val messages = JSONArray(store.loadSessionJson(session))
        assertEquals(2, messages.length())
        assertEquals("Pertanyaan", messages.getJSONObject(0).getString("content"))
        assertEquals("Jawaban yang terlihat", messages.getJSONObject(1).getString("content"))
        assertEquals("", store.hubValue("draft:ANDROID:$session"))
    }

    @Test fun interruptionBeforeOutputRestoresDraftWithoutInventingAnAnswer() {
        val session = store.createSession()
        store.beginTurn("request", session, "Belum terjawab")
        assertEquals(1, store.recoverInterruptedTurns())
        assertEquals("Belum terjawab", store.hubValue("draft:ANDROID:$session"))
        assertEquals(0, store.messageCountForSession(session))
    }

    @Test fun newerDraftAndSubmittedPromptBothSurvive() {
        val session = store.createSession()
        store.beginTurn("request", session, "Pesan pertama")
        store.putHubValue("draft:ANDROID:$session", "Pesan berikutnya")
        store.recoverInterruptedTurns()
        assertEquals("Pesan berikutnya", store.hubValue("draft:ANDROID:$session"))
        assertEquals("Pesan pertama", JSONArray(store.loadSessionJson(session)).getJSONObject(0).getString("content"))
    }

    @Test fun versionFiveUpgradePreservesArchiveAndSupportsJournal() {
        val session = store.createSession("Percakapan lama")
        store.addMessage(session, "user", "Arsip tetap ada", rememberFacts = false)
        store.writableDatabase.execSQL("DROP TABLE pending_turns")
        store.writableDatabase.version = 5
        store.close()
        store = MemoryStore(context)
        store.beginTurn("new", session, "Pertanyaan baru")
        store.finishTurn("new", "Jawaban baru")
        assertEquals(6, store.readableDatabase.version)
        assertEquals(3, store.messageCountForSession(session))
        assertEquals(0, store.recoverInterruptedTurns())
    }
}
