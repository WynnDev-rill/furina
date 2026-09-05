package com.wynndev.furina

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import java.net.ServerSocket
import java.net.InetAddress
import java.io.InputStream
import java.io.IOException
import java.util.concurrent.Executors
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Loopback HTTP + real JSON/repository/SQLite. No user API calls or Termux device is simulated. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class CoreBridgeContractTest {
    private lateinit var context: Context
    private lateinit var bridge: TermuxBridgeClient
    private lateinit var server: ServerSocket
    private val executor = Executors.newCachedThreadPool()
    @Volatile private var response = "{}"
    @Volatile private var code = 200
    @Volatile private var observedToken = ""
    @Volatile private var observedPath = ""

    @Before fun setup() {
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences("furinahub_termux", 0).edit().putString("hub_token", "fixture-token-for-local-contract-tests").commit()
        server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        executor.execute {
            while (!server.isClosed) {
                val socket = try { server.accept() } catch (_: IOException) { break }
                socket.use {
                    socket.soTimeout = 5_000
                    val input = socket.getInputStream().buffered()
                    observedPath = line(input).split(' ').getOrElse(1) { "" }
                    val headers = mutableMapOf<String, String>()
                    while (true) {
                        val header = line(input)
                        if (header.isEmpty()) break
                        headers[header.substringBefore(':').lowercase()] = header.substringAfter(':').trim()
                    }
                    observedToken = headers["x-furinahub-token"].orEmpty()
                    repeat(headers["content-length"]?.toIntOrNull() ?: 0) { input.read() }
                    val bytes = response.toByteArray(Charsets.UTF_8)
                    socket.getOutputStream().use { output ->
                        output.write("HTTP/1.1 $code Fixture\r\nContent-Type: application/json\r\nContent-Length: ${bytes.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.US_ASCII))
                        output.write(bytes)
                    }
                }
            }
        }
        bridge = TermuxBridgeClient(context, server.localPort)
    }
    @After fun tearDown() { server.close(); executor.shutdownNow() }

    private fun line(input: InputStream): String = buildString {
        while (true) {
            val next = input.read()
            if (next < 0 || next == 10) break
            if (next != 13) append(next.toChar())
            check(length <= 8_192) { "Fixture header too long" }
        }
    }

    @Test fun progressWithEmptyErrorIsSuccessfulAndTokenStaysInHeader() = runBlocking {
        response = """{"done":true,"error":"","partial":"Halo Wynn"}"""
        assertEquals("Halo Wynn", bridge.get("/api/chat/progress/fixture").getString("partial"))
        assertEquals("fixture-token-for-local-contract-tests", observedToken)
        assertFalse(observedPath.contains("token"))
    }

    @Test fun healthRejectsUnrelatedLoopbackService() = runBlocking {
        response = """{"ok":true,"app":"unrelated"}"""
        var rejected = false
        try { bridge.health() } catch (_: IllegalStateException) { rejected = true }
        assertTrue(rejected)
        response = """{"ok":true,"app":"FurinaHub","version":"fixture"}"""
        assertEquals("fixture", bridge.health().getString("version"))
    }

    @Test fun httpAndApplicationErrorsAreBothRejected() = runBlocking {
        response = """{"error":"Tidak diizinkan"}"""
        code = 403
        var rejected = false
        try { bridge.post("/api/conversations", JSONObject()) } catch (e: CoreBridgeException) { rejected = e.status == 403 }
        assertTrue(rejected)
        code = 200
        rejected = false
        try { bridge.get("/api/bootstrap") } catch (_: IllegalStateException) { rejected = true }
        assertTrue(rejected)
    }

    @Test fun remoteBootstrapNeverReplacesTheLocalSessionIdentifier() = runBlocking {
        context.deleteDatabase("furina_memory.db")
        MemoryStore(context).use { store ->
            val repository = HubDataRepository(context, store, bridge)
            val local = repository.snapshot(HubSource.ANDROID)
            response = """{"active_conversation_id":42,"assistant_name":"Nara","history":[{"id":9,"role":"user","content":"Halo Core"}],"conversations":[{"id":42,"title":"Core"}],"core_version":"fixture"}"""
            val remote = repository.snapshot(HubSource.TERMUX)
            assertEquals("42", remote.id)
            assertEquals("Halo Core", remote.messages.single().content)
            assertEquals(local.id, repository.snapshot(HubSource.ANDROID).id)
            assertEquals(0, store.messageCountForSession(local.id))
        }
    }
}
