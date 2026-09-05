package com.wynndev.furina

import android.content.Context
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

enum class ChatWallpaperKind { PRESET, IMAGE, VIDEO }

data class ChatAppearance(
    val kind: ChatWallpaperKind = ChatWallpaperKind.PRESET,
    val value: String = ChatAppearanceStore.DEFAULT_PRESET,
    val dimAmount: Float = ChatAppearanceStore.DEFAULT_DIM,
    val motionEnabled: Boolean = true,
)

/**
 * Owns chat presentation data only. Imported media is copied into app-private storage so the
 * wallpaper remains available after a reboot without broad storage permissions. It is never sent
 * to Furina Core or included in an AI request.
 */
object ChatAppearanceStore {
    const val DEFAULT_PRESET = "midnight"
    const val DEFAULT_DIM = 0.24f

    val presetIds = setOf("midnight", "ocean", "aurora", "rose")

    private const val PREFS = "furinahub_chat_appearance"
    private const val KEY_KIND = "wallpaper_kind"
    private const val KEY_VALUE = "wallpaper_value"
    private const val KEY_DIM = "wallpaper_dim"
    private const val KEY_MOTION = "wallpaper_motion"
    private const val MEDIA_DIR = "chat_wallpapers"
    private const val MAX_IMAGE_BYTES = 12L * 1024L * 1024L
    private const val MAX_VIDEO_BYTES = 20L * 1024L * 1024L
    private const val MAX_VIDEO_DURATION_MS = 30_000L
    private const val MAX_VIDEO_PIXELS = 1_920L * 1_080L
    private val safeFile = Regex("^wallpaper_[0-9a-f-]{36}\\.(jpg|png|webp|mp4|webm)$")

    fun load(context: Context): ChatAppearance {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val kind = runCatching {
            ChatWallpaperKind.valueOf(prefs.getString(KEY_KIND, ChatWallpaperKind.PRESET.name).orEmpty())
        }.getOrDefault(ChatWallpaperKind.PRESET)
        val savedValue = prefs.getString(KEY_VALUE, DEFAULT_PRESET).orEmpty()
        val value = when (kind) {
            ChatWallpaperKind.PRESET -> savedValue.takeIf { it in presetIds } ?: DEFAULT_PRESET
            else -> savedValue.takeIf { resolveMedia(context, it)?.isFile == true }.orEmpty()
        }
        if (value.isBlank()) return ChatAppearance()
        return ChatAppearance(
            kind = kind,
            value = value,
            dimAmount = prefs.getFloat(KEY_DIM, DEFAULT_DIM).coerceIn(0f, 0.72f),
            motionEnabled = prefs.getBoolean(KEY_MOTION, true),
        )
    }

    fun selectPreset(context: Context, id: String): ChatAppearance {
        require(id in presetIds) { "Preset wallpaper tidak dikenal" }
        val previous = load(context)
        val next = previous.copy(kind = ChatWallpaperKind.PRESET, value = id)
        persist(context, next)
        deleteIfOwned(context, previous)
        return next
    }

    fun setDimAmount(context: Context, amount: Float): ChatAppearance {
        val next = load(context).copy(dimAmount = amount.coerceIn(0f, 0.72f))
        persist(context, next)
        return next
    }

    fun setMotionEnabled(context: Context, enabled: Boolean): ChatAppearance {
        val next = load(context).copy(motionEnabled = enabled)
        persist(context, next)
        return next
    }

    fun reset(context: Context): ChatAppearance {
        val previous = load(context)
        val next = ChatAppearance()
        persist(context, next)
        deleteIfOwned(context, previous)
        return next
    }

    suspend fun import(context: Context, uri: Uri, kind: ChatWallpaperKind): Result<ChatAppearance> = withContext(Dispatchers.IO) {
        runCatching {
            require(kind == ChatWallpaperKind.IMAGE || kind == ChatWallpaperKind.VIDEO) {
                "Jenis wallpaper tidak didukung"
            }
            val mime = context.contentResolver.getType(uri).orEmpty().lowercase()
            val maxBytes = if (kind == ChatWallpaperKind.IMAGE) MAX_IMAGE_BYTES else MAX_VIDEO_BYTES
            if (kind == ChatWallpaperKind.IMAGE && mime.isNotBlank()) {
                require(mime.startsWith("image/")) { "Pilih berkas gambar yang valid" }
            }
            if (kind == ChatWallpaperKind.VIDEO) {
                require(mime == "video/mp4" || mime == "video/webm" || mime.isBlank()) {
                    "Video harus berformat MP4 atau WebM"
                }
            }

            context.contentResolver.openAssetFileDescriptor(uri, "r")?.use { descriptor ->
                if (descriptor.length > maxBytes) {
                    throw IllegalArgumentException(sizeMessage(kind))
                }
            }

            val directory = File(context.filesDir, MEDIA_DIR).canonicalFile
            if (!directory.exists() && !directory.mkdirs()) throw IOException("Folder wallpaper tidak dapat dibuat")
            require(directory.isDirectory) { "Folder wallpaper tidak valid" }

            val extension = extensionFor(kind, mime)
            val fileName = "wallpaper_${UUID.randomUUID()}.$extension"
            require(safeFile.matches(fileName)) { "Nama wallpaper tidak valid" }
            val temporary = File(directory, ".$fileName.part").canonicalFile
            val destination = File(directory, fileName).canonicalFile
            require(temporary.parentFile == directory && destination.parentFile == directory) { "Lokasi wallpaper tidak aman" }

            try {
                var copied = 0L
                context.contentResolver.openInputStream(uri)?.use { input ->
                    FileOutputStream(temporary).use { output ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            copied += count
                            if (copied > maxBytes) throw IllegalArgumentException(sizeMessage(kind))
                            output.write(buffer, 0, count)
                        }
                        output.fd.sync()
                    }
                } ?: throw IOException("Berkas tidak dapat dibaca")

                require(copied > 0L) { "Berkas wallpaper kosong" }
                when (kind) {
                    ChatWallpaperKind.IMAGE -> validateImage(temporary)
                    ChatWallpaperKind.VIDEO -> validateVideo(temporary)
                    ChatWallpaperKind.PRESET -> Unit
                }
                if (!temporary.renameTo(destination)) throw IOException("Wallpaper tidak dapat disimpan")
            } catch (error: Throwable) {
                temporary.delete()
                destination.delete()
                throw error
            }

            val previous = load(context)
            val next = previous.copy(
                kind = kind,
                value = fileName,
                dimAmount = if (kind == ChatWallpaperKind.VIDEO) maxOf(previous.dimAmount, 0.32f) else previous.dimAmount,
            )
            persist(context, next)
            deleteIfOwned(context, previous)
            next
        }
    }

    fun resolveMedia(context: Context, fileName: String): File? {
        if (!safeFile.matches(fileName)) return null
        return try {
            val directory = File(context.filesDir, MEDIA_DIR).canonicalFile
            val file = File(directory, fileName).canonicalFile
            file.takeIf { it.parentFile == directory }
        } catch (_: IOException) {
            null
        } catch (_: SecurityException) {
            null
        }
    }

    private fun persist(context: Context, appearance: ChatAppearance) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_KIND, appearance.kind.name)
            .putString(KEY_VALUE, appearance.value)
            .putFloat(KEY_DIM, appearance.dimAmount)
            .putBoolean(KEY_MOTION, appearance.motionEnabled)
            .apply()
    }

    private fun validateImage(file: File) {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, options)
        require(options.outWidth > 0 && options.outHeight > 0) { "Gambar tidak dapat dibaca" }
        require(options.outWidth <= 12_000 && options.outHeight <= 12_000) { "Resolusi gambar terlalu besar" }
    }

    private fun validateVideo(file: File) {
        val retriever = MediaMetadataRetriever()
        try {
            retriever.setDataSource(file.absolutePath)
            val duration = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
            val width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toLongOrNull() ?: 0L
            val height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toLongOrNull() ?: 0L
            require(duration in 1L..MAX_VIDEO_DURATION_MS) { "Durasi video maksimal 30 detik" }
            require(width > 0 && height > 0) { "Video tidak dapat dibaca" }
            require(width * height <= MAX_VIDEO_PIXELS) { "Resolusi video maksimal 1080p" }
        } finally {
            retriever.release()
        }
    }

    private fun extensionFor(kind: ChatWallpaperKind, mime: String): String = when (kind) {
        ChatWallpaperKind.IMAGE -> when (mime) {
            "image/png" -> "png"
            "image/webp" -> "webp"
            else -> "jpg"
        }
        ChatWallpaperKind.VIDEO -> if (mime == "video/webm") "webm" else "mp4"
        ChatWallpaperKind.PRESET -> error("Preset tidak memiliki berkas")
    }

    private fun sizeMessage(kind: ChatWallpaperKind): String = if (kind == ChatWallpaperKind.IMAGE) {
        "Ukuran gambar maksimal 12 MB"
    } else {
        "Ukuran video maksimal 20 MB"
    }

    private fun deleteIfOwned(context: Context, appearance: ChatAppearance) {
        if (appearance.kind == ChatWallpaperKind.IMAGE || appearance.kind == ChatWallpaperKind.VIDEO) {
            resolveMedia(context, appearance.value)?.delete()
        }
    }
}
