package com.wynndev.furina

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import java.io.File
import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
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
class BackupAndGenerationTest {
    private lateinit var context: Context
    private lateinit var store: MemoryStore
    @Before fun setup() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase("furina_memory.db")
        store = MemoryStore(context)
    }
    @After fun tearDown() { store.close() }

    @Test fun encryptedBackupRestoresPersonaHistoryAndInvalidatesRetrieval() {
        val id = store.createSession()
        store.addMessage(id, "user", "Percakapan tersimpan")
        store.putHubValue("persona", HubPersona(name = "Nara").json().toString())
        store.addMemory("Kode proyek zefir")
        val backup = BackupManager(context, store)
        val bytes = backup.createEncryptedSnapshotBytes()
        assertFalse(String(bytes, Charsets.ISO_8859_1).contains("Percakapan tersimpan"))
        store.clearSession(id)
        store.clearMemories()
        store.putHubValue("persona", HubPersona(name = "Sementara").json().toString())
        assertEquals("", store.relevantMemories("zefir"))
        backup.restoreEncryptedSnapshotBytes(bytes)
        assertEquals(1, store.messageCountForSession(id))
        assertTrue(store.hubValue("persona")!!.contains("Nara"))
        assertTrue(store.relevantMemories("zefir").contains("zefir"))
    }

    @Test fun tamperingAndWrongRecoveryKeyLeaveCurrentDataAndKeyIntact() {
        val id = store.createSession()
        store.addMessage(id, "user", "Data penting")
        val backup = BackupManager(context, store)
        val key = backup.getOrCreateRecoveryKey()
        val bytes = backup.createEncryptedSnapshotBytes()
        bytes[bytes.lastIndex] = (bytes.last().toInt() xor 1).toByte()
        assertThrows(Exception::class.java) { backup.restoreEncryptedSnapshotBytes(bytes) }
        assertEquals(1, store.messageCountForSession(id))
        val file = File(context.cacheDir, "backup-test.furina")
        file.writeBytes(backup.createEncryptedSnapshotBytes())
        val wrongKey = android.util.Base64.encodeToString(ByteArray(32) { 9 }, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP or android.util.Base64.NO_PADDING)
        assertThrows(Exception::class.java) { backup.restoreFrom(Uri.fromFile(file), wrongKey) }
        assertEquals(key, backup.getOrCreateRecoveryKey())
        assertEquals(1, store.messageCountForSession(id))
    }

    @Test fun cancellationPersistsExactlyTheVisibleReplyPrefix() = verifyInterruptedGeneration(CancellationException("Stop"))
    @Test fun providerFailurePersistsExactlyTheVisibleReplyPrefix() = verifyInterruptedGeneration(IOException("Putus"))

    private fun verifyInterruptedGeneration(error: Exception) = runBlocking {
        val id = store.createSession()
        val fake = object : AiProvider {
            override val id = "fixture"
            override val capabilities = AiProviderCapabilities(true, true)
            override suspend fun prepare(model: AiModelRef, context: AiContext) = Unit
            override fun stream(request: AiGenerationRequest): Flow<String> = flow { emit("Halo "); emit("Wynn"); throw error }
            override suspend fun unload() = Unit
            override fun isWarm(model: AiModelRef, context: AiContext) = false
        }
        val engine = UnifiedAiEngine(store, ContextEngine(context, store), mapOf(fake.id to fake))
        val visible = StringBuilder()
        try {
            engine.generate("fixture", fake.id, AiModelRef(fake.id, "model", "Fixture"), id, "Halo", "Nara", "Jawab natural") { visible.append(it) }
            fail("Generation should be interrupted")
        } catch (e: Exception) { assertEquals(error, e) }
        finally { engine.destroy() }
        val rows = JSONArray(store.loadSessionJson(id))
        assertEquals(2, rows.length())
        assertEquals(visible.toString(), rows.getJSONObject(1).getString("content"))
        assertEquals("assistant", rows.getJSONObject(1).getString("role"))
    }
}
