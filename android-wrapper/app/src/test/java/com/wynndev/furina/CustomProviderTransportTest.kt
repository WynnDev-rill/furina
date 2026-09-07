package com.wynndev.furina

import android.app.Application
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import java.net.ServerSocket
import java.net.InetAddress
import java.io.InputStream
import java.io.IOException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.Executors
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Real HTTP, provider selection, context and SQLite. UI admission is covered on the release APK. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class CustomProviderTransportTest {
    @Test fun probeAndGenerationUseConfiguredAddressAndPersistContextualReply() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        context.deleteDatabase("furina_memory.db")
        val requests = CopyOnWriteArrayList<String>()
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        val executor = Executors.newSingleThreadExecutor()
        executor.execute {
            while (!server.isClosed) {
                val socket = try { server.accept() } catch (_: IOException) { break }
                socket.use {
                    it.soTimeout = 5_000
                    val input = it.getInputStream().buffered()
                    val path = line(input).split(' ').getOrElse(1) { "" }
                    val headers = mutableMapOf<String, String>()
                    while (true) {
                        val header = line(input)
                        if (header.isBlank()) break
                        headers[header.substringBefore(':').lowercase()] = header.substringAfter(':').trim()
                    }
                    val bytes = ByteArray(headers["content-length"]?.toIntOrNull() ?: 0)
                    java.io.DataInputStream(input).readFully(bytes)
                    requests.add(String(bytes, Charsets.UTF_8))
                    val body = """{"choices":[{"message":{"content":"Jawaban uji transport"}}]}""".toByteArray()
                    val code = if (path == "/v1/chat/completions") 200 else 404
                    it.getOutputStream().use { output ->
                        output.write("HTTP/1.1 $code Fixture\r\nContent-Type: application/json\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray())
                        output.write(body)
                    }
                }
            }
        }
        try {
            MemoryStore(context).use { store ->
                val session = store.createSession()
                store.addMemory("Kode proyek adalah zefir")
                val runtime = AiRuntimeController(context)
                runtime.setMode(OnlineAiConfigStore.MODE_ONLINE)
                runtime.configureCustom("http://127.0.0.1:" + server.localPort + "/v1", "qa-model", "")
                val probe = runtime.test("custom")
                assertTrue(probe.message, probe.success)
                val (provider, model) = runtime.resolve(ModelCatalog.models.first())
                val engine = UnifiedAiEngine(store, ContextEngine(context, store), runtime.onlineProviders)
                try {
                    val visible = StringBuilder()
                    engine.generate("request", provider, model, session, "QA_CHAT zefir", "Furina", "Jawab dengan tenang") { visible.append(it) }
                    assertEquals("Jawaban uji transport", visible.toString())
                    assertEquals(2, requests.size)
                    val messages = JSONObject(requests.last()).getJSONArray("messages")
                    assertEquals("system", messages.getJSONObject(0).getString("role"))
                    assertTrue(messages.getJSONObject(0).getString("content").contains("zefir"))
                    assertTrue(messages.getJSONObject(0).getString("content").contains("Furina"))
                    val history = JSONArray(store.loadSessionJson(session))
                    assertEquals(2, history.length())
                    assertEquals("user", history.getJSONObject(0).getString("role"))
                    assertEquals(visible.toString(), history.getJSONObject(1).getString("content"))
                    assertEquals(0, store.recoverInterruptedTurns())
                } finally { engine.unload(); engine.destroy() }
            }
        } finally { server.close(); executor.shutdownNow() }
    }

    private fun line(input: InputStream): String = buildString {
        while (true) {
            val next = input.read()
            if (next < 0 || next == 10) break
            if (next != 13) append(next.toChar())
            check(length <= 8_192)
        }
    }
}
