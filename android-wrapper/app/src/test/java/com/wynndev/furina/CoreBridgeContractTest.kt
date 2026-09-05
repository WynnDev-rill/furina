package com.wynndev.furina

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
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
    private lateinit var server: HttpServer
    private val executor = Executors.newCachedThreadPool()
    @Volatile private var response = "{}"
    @Volatile private var code = 200
    @Volatile private var observedToken = ""
    @Volatile private var observedPath = ""

    @Before fun setup() {
        context = ApplicationProvider.getApplicationContext()
        context.getSharedPreferences("furinahub_termux", 0).edit().putString("hub_token", "fixture-token-for-local-contract-tests").commit()
        server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        server.executor = executor
        server.createContext("/") { exchange ->
            observedToken = exchange.requestHeaders.getFirst("X-FurinaHub-Token").orEmpty()
            observedPath = exchange.requestURI.toString()
            exchange.requestBody.use { it.readBytes() }
            val bytes = response.toByteArray()
            exchange.responseHeaders.add("Content-Type", "application/json")
            exchange.sendResponseHeaders(code, bytes.size.toLong())
            exchange.responseBody.use { it.write(bytes) }
        }
        server.start()
        bridge = TermuxBridgeClient(context, server.address.port)
    }
    @After fun tearDown() { server.stop(0); executor.shutdownNow() }

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
