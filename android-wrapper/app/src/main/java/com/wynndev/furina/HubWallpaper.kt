package com.wynndev.furina

import android.graphics.ImageDecoder
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Movie
import androidx.compose.material.icons.outlined.Palette
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.key
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext


@Composable
internal fun ChatWallpaper(appearance: ChatAppearance, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val fallback = Brush.verticalGradient(
        colors = listOf(Color(0xFF111827), Color(0xFF17233A), Color(0xFF101116)),
    )
    Box(modifier.background(fallback)) {
        when (appearance.kind) {
            ChatWallpaperKind.PRESET -> PresetWallpaper(appearance.value, Modifier.fillMaxSize())
            ChatWallpaperKind.IMAGE -> {
                val file = remember(appearance.value) { ChatAppearanceStore.resolveMedia(context, appearance.value) }
                val bitmap by produceState<androidx.compose.ui.graphics.ImageBitmap?>(null, file) {
                    value = withContext(Dispatchers.IO) { file?.let(::decodeWallpaperBitmap)?.asImageBitmap() }
                }
                bitmap?.let {
                    Image(
                        bitmap = it,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
            }
            ChatWallpaperKind.VIDEO -> {
                val file = remember(appearance.value) { ChatAppearanceStore.resolveMedia(context, appearance.value) }
                if (file?.isFile == true) VideoWallpaper(file.absolutePath, appearance.motionEnabled, Modifier.fillMaxSize())
            }
        }
        Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = appearance.dimAmount)))
    }
}

@Composable
private fun PresetWallpaper(id: String, modifier: Modifier = Modifier) {
    val colors = when (id) {
        "ocean" -> listOf(Color(0xFF102A43), Color(0xFF164E63), Color(0xFF0B1324))
        "aurora" -> listOf(Color(0xFF15243B), Color(0xFF174B50), Color(0xFF332A55))
        "rose" -> listOf(Color(0xFF3D2437), Color(0xFF332A4F), Color(0xFF17131F))
        else -> listOf(Color(0xFF111827), Color(0xFF1C2942), Color(0xFF101116))
    }
    Box(modifier.background(Brush.verticalGradient(colors)))
}

@Composable
private fun VideoWallpaper(path: String, motionEnabled: Boolean, modifier: Modifier = Modifier) {
    val owner = LocalLifecycleOwner.current
    var foreground by remember(owner) { mutableStateOf(owner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) }
    var failed by remember(path) { mutableStateOf(false) }
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, _ -> foreground = owner.lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
    key(path) {
        if (!failed) AndroidView(
            factory = { context -> WallpaperVideoView(context).apply { onFailure = { failed = true } } },
            update = { it.configure(path, motionEnabled, foreground) },
            onRelease = { it.releasePlayer() },
            modifier = modifier,
        )
        else Box(modifier, contentAlignment = Alignment.Center) {
            Text("Video tidak dapat diputar. Pilih video lain di Tampilan chat.", color = Color.White, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun decodeWallpaperBitmap(file: java.io.File): android.graphics.Bitmap? = runCatching {
    ImageDecoder.decodeBitmap(ImageDecoder.createSource(file)) { decoder, info, _ ->
        var sample = 1
        while (info.size.width / sample > 1_440 || info.size.height / sample > 2_560) sample *= 2
        decoder.setTargetSampleSize(sample)
        decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
    }
}.getOrNull()

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun WallpaperSettingsCard(
    state: HubUiState,
    controller: NativeHubController,
    chooseImage: () -> Unit,
    chooseVideo: () -> Unit,
) {
    val appearance = state.chatAppearance
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
            Box(
                Modifier.fillMaxWidth().aspectRatio(16f / 7f).clip(RoundedCornerShape(18.dp)),
                contentAlignment = Alignment.Center,
            ) {
                ChatWallpaper(appearance, Modifier.fillMaxSize())
                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surface.copy(alpha = .86f)) {
                    Text(
                        when (appearance.kind) {
                            ChatWallpaperKind.PRESET -> "Pratinjau wallpaper"
                            ChatWallpaperKind.IMAGE -> "Foto pribadi"
                            ChatWallpaperKind.VIDEO -> if (appearance.motionEnabled) "Video berulang · tanpa suara" else "Gerakan dijeda"
                        },
                        style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                    )
                }
            }

            Text("Preset", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(
                    "midnight" to "Midnight",
                    "ocean" to "Ocean",
                    "aurora" to "Aurora",
                    "rose" to "Rose",
                ).forEach { (id, label) ->
                    FilterChip(
                        selected = appearance.kind == ChatWallpaperKind.PRESET && appearance.value == id,
                        onClick = { controller.selectWallpaperPreset(id) },
                        label = { Text(label) },
                    )
                }
            }

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                OutlinedButton(onClick = chooseImage, enabled = !state.wallpaperBusy, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Outlined.PhotoLibrary, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("Pilih foto")
                }
                OutlinedButton(onClick = chooseVideo, enabled = !state.wallpaperBusy, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Outlined.Movie, null, Modifier.size(18.dp))
                    Spacer(Modifier.width(7.dp))
                    Text("Pilih video")
                }
            }

            if (state.wallpaperBusy) {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text("Memeriksa dan menyimpan wallpaper…", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Text("Foto maks. 12 MB. Video MP4/WebM maks. 20 MB, 30 detik, dan 1080p.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            Column {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Kegelapan latar", fontWeight = FontWeight.Medium)
                        Text("${(appearance.dimAmount * 100).toInt()}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Icon(Icons.Outlined.Palette, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Slider(
                    value = appearance.dimAmount,
                    onValueChange = controller::setWallpaperDim,
                    valueRange = 0f..0.72f,
                )
            }

            SettingSwitch(
                title = "Gerakan latar",
                description = "Video dijeda otomatis saat aplikasi tidak terlihat.",
                checked = appearance.motionEnabled,
                onChecked = controller::setWallpaperMotion,
            )

            if (appearance.kind != ChatWallpaperKind.PRESET || appearance.value != ChatAppearanceStore.DEFAULT_PRESET) {
                TextButton(onClick = controller::resetChatWallpaper, modifier = Modifier.align(Alignment.End)) {
                    Text("Kembalikan ke bawaan")
                }
            }
        }
    }
}

