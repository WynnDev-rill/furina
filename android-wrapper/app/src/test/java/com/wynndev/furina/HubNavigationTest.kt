package com.wynndev.furina

import android.app.Application
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import androidx.compose.ui.test.hasText
import java.net.ServerSocket
import java.net.InetAddress
import java.io.InputStream
import java.io.IOException
import java.util.concurrent.Executors
import java.util.concurrent.CopyOnWriteArrayList
import org.junit.Assert.*
import org.json.JSONObject
import androidx.work.Configuration
import androidx.work.WorkManager
import androidx.lifecycle.ViewModelProvider
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

class HubTestApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        try { WorkManager.getInstance(this) } catch (_: IllegalStateException) { WorkManager.initialize(this, Configuration.Builder().build()) }
    }
}

/** Real Compose screens/controller/repository, with no GGUF download or billable API requests. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = HubTestApplication::class)
@LooperMode(LooperMode.Mode.PAUSED)
class HubNavigationTest {
    @get:Rule val ui = createAndroidComposeRule<NativeHubActivity>()

    @Test fun customProviderSendTraversesControllerContextTransportAndHistory() {
        val requests = CopyOnWriteArrayList<String>()
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        val executor = Executors.newSingleThreadExecutor()
        fun line(input: InputStream): String = buildString {
            while (true) {
                val next = input.read()
                if (next < 0 || next == 10) break
                if (next != 13) append(next.toChar())
                check(length <= 8_192)
            }
        }
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
        val controller = ViewModelProvider(ui.activity)[HubViewModel::class.java].controller
        try {
            ui.waitUntil(15_000) { !controller.state.value.busy }
            ui.runOnIdle { controller.setAndroidAiMode("online") }
            ui.waitUntil(15_000) { !controller.state.value.busy }
            ui.runOnIdle { controller.configureCustomProvider("http://127.0.0.1:" + server.localPort + "/v1", "qa-model", "") }
            ui.waitUntil(15_000) { !controller.state.value.busy }
            assertTrue(controller.state.value.error, controller.state.value.modelReady)
            ui.runOnIdle { controller.addMemory("Kode proyek adalah zefir") }
            ui.waitUntil(15_000) { !controller.state.value.busy }
            ui.onNodeWithText("Kirim pesan…").performTextInput("QA_CHAT zefir")
            ui.onNodeWithContentDescription("Kirim").performClick()
            ui.waitUntil(15_000) { !controller.state.value.busy }
            assertNull(controller.state.value.chatError, controller.state.value.chatError)
            assertEquals(2, requests.size)
            assertEquals("Jawaban uji transport", controller.state.value.messages.last().content)
            assertEquals("user", controller.state.value.messages.first().role)
            val messages = JSONObject(requests.last()).getJSONArray("messages")
            assertEquals("system", messages.getJSONObject(0).getString("role"))
            assertTrue(messages.getJSONObject(0).getString("content").contains("zefir"))
            assertTrue(messages.getJSONObject(0).getString("content").contains("Furina"))
        } finally { server.close(); executor.shutdownNow() }
    }

    @Test fun launchAndNavigateAcrossAllMainScreens() {
        ui.onNodeWithContentDescription("Riwayat percakapan").assertIsDisplayed()
        ui.onNodeWithContentDescription("Setelan").performClick()
        ui.onNode(hasText("Persona") and hasText("Nama, kepribadian, dan cara berinteraksi")).performClick()
        ui.onNodeWithText("Nama companion").assertIsDisplayed()
        ui.onNodeWithContentDescription("Kembali").performClick()
        ui.onNode(hasText("Memori") and hasText("Hal penting yang diingat")).performClick()
        ui.onNodeWithText("Cari memori…").assertIsDisplayed()
        ui.onNodeWithContentDescription("Kembali").performClick()
        ui.onNodeWithText("Tampilan chat").assertIsDisplayed()
        ui.onNodeWithText("Data & aplikasi").performScrollTo().assertIsDisplayed()
    }

    @Test fun unconfiguredSendPreservesDraftAcrossNavigation() {
        ui.waitUntil(15_000) { !ViewModelProvider(ui.activity)[HubViewModel::class.java].controller.state.value.busy }
        ui.onNodeWithText("Kirim pesan…").performTextInput("Pesan yang belum terkirim")
        ui.onNodeWithContentDescription("Kirim").performClick()
        ui.onNodeWithContentDescription("Setelan").performClick()
        ui.onNodeWithContentDescription("Kembali").performClick()
        ui.onNodeWithText("Pesan yang belum terkirim").assertTextContains("Pesan yang belum terkirim")
    }
}
