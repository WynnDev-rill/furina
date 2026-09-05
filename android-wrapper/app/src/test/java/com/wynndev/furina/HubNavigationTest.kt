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

    @Test fun launchAndNavigateAcrossAllMainScreens() {
        ui.onNodeWithContentDescription("Riwayat percakapan").assertIsDisplayed()
        ui.onNodeWithContentDescription("Setelan").performClick()
        ui.onNodeWithText("Persona").performClick()
        ui.onNodeWithText("Nama companion").assertIsDisplayed()
        ui.onNodeWithContentDescription("Kembali").performClick()
        ui.onNodeWithText("Memori").performClick()
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
