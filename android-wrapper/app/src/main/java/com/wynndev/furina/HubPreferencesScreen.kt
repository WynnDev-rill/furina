package com.wynndev.furina

import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.Palette
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.Terminal
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.key
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

import androidx.compose.material.icons.outlined.ChevronRight


@OptIn(ExperimentalLayoutApi::class)
@Composable internal fun PreferencesScreen(state: HubUiState, controller: NativeHubController, onConnect: () -> Unit, onDownload: (String) -> Unit, modifier: Modifier = Modifier) {
    var providerDialog by remember { mutableStateOf<ProviderState?>(null) }
    var deleteModel by remember { mutableStateOf<AndroidModelState?>(null) }
    val imagePicker = androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let { controller.importChatWallpaper(it, ChatWallpaperKind.IMAGE) } }
    val videoPicker = androidx.activity.compose.rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri -> uri?.let { controller.importChatWallpaper(it, ChatWallpaperKind.VIDEO) } }
    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        when(state.destination) {
            HubDestination.SETTINGS -> {
                SettingsLink("Persona", "Nama, kepribadian, dan cara berinteraksi", Icons.Outlined.Person) { controller.setDestination(HubDestination.PERSONA) }
                SettingsLink("Memori", "Hal penting yang diingat", Icons.Outlined.Psychology) { controller.setDestination(HubDestination.MEMORY) }
                HorizontalDivider()
                SettingsLink("Model", if(state.modelReady) "Siap digunakan" else "Pilih model untuk mulai chat", Icons.Outlined.Memory) { controller.setDestination(HubDestination.MODELS) }
                SettingsLink("Tampilan chat", "Tema, foto, dan video", Icons.Outlined.Palette) { controller.setDestination(HubDestination.APPEARANCE) }
                SettingsLink("Termux", if(state.connected) "Terhubung" else "Hubungkan Furina Core", Icons.Outlined.Terminal) { controller.setDestination(HubDestination.TERMUX) }
                SettingsLink("Data & aplikasi", "Backup, ekspor, dan pembaruan", Icons.Outlined.History) { controller.setDestination(HubDestination.DATA) }
            }
            HubDestination.MODELS -> {
                Text("Jalankan di perangkat atau gunakan provider online.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(state.androidAiMode == OnlineAiConfigStore.MODE_LOCAL, { controller.setAndroidAiMode(OnlineAiConfigStore.MODE_LOCAL) }, label = { Text("Di perangkat") }, enabled = !state.busy)
                    FilterChip(state.androidAiMode == OnlineAiConfigStore.MODE_ONLINE, { controller.setAndroidAiMode(OnlineAiConfigStore.MODE_ONLINE) }, label = { Text("Online") }, enabled = !state.busy)
                }
                if(state.source == HubSource.TERMUX) {
                    Card { Column(Modifier.padding(16.dp)) {
                        Text("Chat sedang menggunakan Termux.")
                        TextButton({ controller.setEnginePreference(EnginePreference.ANDROID) }, enabled = !state.busy) { Text("Gunakan Android") }
                    } }
                }
                if(state.androidAiMode == OnlineAiConfigStore.MODE_LOCAL) {
                    state.androidModels.forEach { model ->
                        Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .45f)) {
                            Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text(model.name, style = MaterialTheme.typography.titleMedium)
                                Text(model.subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                val downloading = model.state in setOf("running", "downloading", "verifying", "queued")
                                Text(when(model.state) {
                                    "ready" -> if(state.localModelLoaded && model.selected) "Aktif di memori" else "Tersedia di perangkat"
                                    "running", "downloading", "queued" -> "Mengunduh…"
                                    "verifying" -> "Memeriksa berkas…"
                                    "paused" -> "Unduhan terhenti"
                                    "failed" -> "Unduhan gagal"
                                    else -> "Belum diunduh"
                                }, style = MaterialTheme.typography.labelLarge)
                                if(downloading || model.state == "paused") {
                                    if(model.totalBytes > 0) LinearProgressIndicator({ model.progress }, Modifier.fillMaxWidth()) else LinearProgressIndicator(Modifier.fillMaxWidth())
                                    Text(formatBytes(model.downloadedBytes) + " / " + formatBytes(model.totalBytes), style = MaterialTheme.typography.labelSmall)
                                }
                                if(model.error.isNotBlank()) Text(model.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    if(model.state == "ready") {
                                        if(!model.selected) Button({ controller.selectAndroidModel(model.id) }, enabled = !state.busy) { Text("Pilih") }
                                        else if(state.localModelLoaded) OutlinedButton(controller::releaseLocalModel, enabled = !state.busy) { Text("Lepas dari memori") }
                                        else Button(controller::prepareLocalModel, enabled = !state.busy) { Text("Siapkan model") }
                                    } else if(!downloading) Button({ onDownload(model.id) }, enabled = !state.busy) { Text(if(model.downloadedBytes > 0) "Lanjutkan unduhan" else "Unduh model") }
                                    if(model.downloadedBytes > 0 || downloading) TextButton({ deleteModel = model }, enabled = !state.busy) { Text(if(downloading) "Batalkan" else "Hapus berkas") }
                                }
                            }
                        }
                    }
                    if(state.busy) Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        Text(state.status, Modifier.padding(start = 12.dp), style = MaterialTheme.typography.bodyMedium)
                    }
                } else {
                    state.providers.forEach { p ->
                        Surface(shape = RoundedCornerShape(16.dp), color = if(p.selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .35f)) {
                            Row(Modifier.fillMaxWidth().clickable(enabled = !state.busy) { controller.selectProvider(p.id) }.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f)) {
                                    Text(p.name, style = MaterialTheme.typography.titleMedium)
                                    Text(if(p.validated) "Siap" else if(p.configured) "Perlu diuji" else "Belum terhubung", style = MaterialTheme.typography.bodySmall)
                                }
                                TextButton({ providerDialog = p }, enabled = !state.busy) { Text(if(p.configured) "Kelola" else "Hubungkan") }
                            }
                        }
                    }
                    OnlineModelsCard(state, controller)
                }
                if(state.firstResponseMs > 0) {
                    HorizontalDivider()
                    Text("Jawaban terakhir", style = MaterialTheme.typography.titleSmall)
                    Text("Mulai menjawab " + "%.1f".format(state.firstResponseMs / 1000.0) + " dtk · selesai " + "%.1f".format(state.responseDurationMs / 1000.0) + " dtk", style = MaterialTheme.typography.bodySmall)
                }
            }
            HubDestination.APPEARANCE -> {
                Text("Tema", style = MaterialTheme.typography.titleMedium)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    HubThemeMode.entries.forEach { mode -> FilterChip(state.themeMode == mode, { controller.setTheme(mode) }, label = { Text(when(mode) { HubThemeMode.SYSTEM -> "Sistem"; HubThemeMode.LIGHT -> "Terang"; HubThemeMode.DARK -> "Gelap" }) }) }
                }
                Text("Wallpaper", style = MaterialTheme.typography.titleMedium)
                WallpaperSettingsCard(state, controller, { imagePicker.launch("image/*") }, { videoPicker.launch("video/*") })
            }
            HubDestination.TERMUX -> {
                Text(if(state.connected) "Furina Core terhubung" else state.connectionMessage, style = MaterialTheme.typography.titleMedium)
                Text("Gunakan model dan percakapan dari Furina Lite di Termux.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onConnect, enabled = !state.busy) { Text(if(state.connected) "Hubungkan ulang" else "Hubungkan") }
                    if(state.connected) OutlinedButton(controller::disconnectTermux, enabled = !state.busy) { Text("Putuskan") }
                }
                Text("Sumber percakapan", style = MaterialTheme.typography.titleMedium)
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    EnginePreference.entries.forEach { preference ->
                        FilterChip(state.enginePreference == preference, { controller.setEnginePreference(preference) }, enabled = !state.busy,
                            label = { Text(when(preference) { EnginePreference.AUTO -> "Otomatis"; EnginePreference.ANDROID -> "Android"; EnginePreference.TERMUX -> "Termux" }) })
                    }
                }
                Text("Otomatis memakai Core saat terhubung. Riwayat Android dan Termux tetap memiliki ruang masing-masing.", style = MaterialTheme.typography.bodySmall)
                CoreSettingsCard(state, controller)
            }
            HubDestination.DATA -> HubDataCard(state, controller)
            else -> Unit
        }
        Spacer(Modifier.height(8.dp))
    }
    providerDialog?.let { p -> ProviderDialog(p, state.busy, { providerDialog = null }) { key ->
        controller.selectProvider(p.id); controller.saveAndTestProvider(p.id, key); providerDialog = null
    } }
    deleteModel?.let { model -> AlertDialog(onDismissRequest = { deleteModel = null }, title = { Text("Hapus berkas model?") }, text = { Text("Model perlu diunduh kembali untuk digunakan. Percakapan tetap tersimpan.") },
        confirmButton = { TextButton(enabled = !state.busy, onClick = { controller.deleteAndroidModel(model.id); deleteModel = null }) { Text("Hapus") } },
        dismissButton = { TextButton({ deleteModel = null }) { Text("Batal") } }) }
}

@Composable private fun SettingsLink(title: String, detail: String, icon: ImageVector, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).clickable(onClick = onClick).padding(vertical = 12.dp, horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = MaterialTheme.colorScheme.primary)
        Column(Modifier.weight(1f).padding(horizontal = 16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Icon(Icons.Outlined.ChevronRight, null)
    }
}
private fun formatBytes(bytes: Long): String = if(bytes <= 0) "—" else if(bytes >= 1024L * 1024 * 1024) "%.1f GB".format(bytes.toDouble() / (1024L * 1024 * 1024)) else "%.0f MB".format(bytes.toDouble() / (1024 * 1024))
