package com.wynndev.furina

import android.app.Application
import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
class ChatAppearanceTest {
    private lateinit var context: Context
    @Before fun setup() {
        context = ApplicationProvider.getApplicationContext()
        ChatAppearanceStore.reset(context)
    }

    @Test fun importCopiesMediaPrivatelyAndSurvivesSourceDeletion() = runBlocking {
        val source = File(context.cacheDir, "fixture.png")
        val bitmap = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888)
        source.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
        val appearance = ChatAppearanceStore.import(context, Uri.fromFile(source), ChatWallpaperKind.IMAGE).getOrThrow()
        source.delete()
        val copy = ChatAppearanceStore.resolveMedia(context, appearance.value)!!
        assertTrue(copy.isFile)
        assertEquals(appearance, ChatAppearanceStore.load(context))
        ChatAppearanceStore.setDimAmount(context, 0.5f)
        ChatAppearanceStore.setMotionEnabled(context, false)
        val loaded = ChatAppearanceStore.load(context)
        assertEquals(0.5f, loaded.dimAmount)
        assertFalse(loaded.motionEnabled)
        ChatAppearanceStore.selectPreset(context, "ocean")
        assertFalse(copy.exists())
        assertEquals(ChatWallpaperKind.PRESET, ChatAppearanceStore.load(context).kind)
    }

    @Test fun failedImportKeepsPreviousAppearanceAndCleansTemporaryFiles() = runBlocking {
        val before = ChatAppearanceStore.selectPreset(context, "rose")
        val source = File(context.cacheDir, "bad.png").apply { writeText("not an image") }
        assertTrue(ChatAppearanceStore.import(context, Uri.fromFile(source), ChatWallpaperKind.IMAGE).isFailure)
        assertEquals(before, ChatAppearanceStore.load(context))
        assertTrue(File(context.filesDir, "chat_wallpapers").listFiles().orEmpty().isEmpty())
        assertNull(ChatAppearanceStore.resolveMedia(context, "../backup.db"))
    }
}
