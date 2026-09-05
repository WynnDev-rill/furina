package com.wynndev.furina

import android.app.Activity
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
internal fun OnlineModelsCard(state: HubUiState, controller: NativeHubController) {
    if (state.androidAiMode != OnlineAiConfigStore.MODE_ONLINE) return
    val provider = state.providers.firstOrNull { it.selected } ?: return
    var choosing by remember { mutableStateOf(false) }
    var search by remember { mutableStateOf("") }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Model ${provider.name}", style = MaterialTheme.typography.titleMedium)
            Text(provider.selectedModel.ifBlank { "Tes API key untuk memuat katalog model." }, style = MaterialTheme.typography.bodySmall)
            Row {
                OutlinedButton(enabled = !state.busy && provider.models.isNotEmpty(), onClick = { choosing = true }) { Text("Pilih model") }
                TextButton(enabled = !state.busy && provider.configured, onClick = { controller.saveAndTestProvider(provider.id, "") }) { Text("Segarkan") }
                TextButton(enabled = !state.busy && provider.configured, onClick = { controller.removeProviderKey(provider.id) }) { Text("Lepas key") }
            }
            Row {
                Text("Fallback model gratis", Modifier.weight(1f))
                Switch(state.autoFallback, controller::setAutoFallback, enabled = !state.busy)
            }
            Text("Pilihan model berlaku untuk mesin Android. Kuota gratis tetap mengikuti aturan provider; katalog bukan jaminan kuota akun.", style = MaterialTheme.typography.bodySmall)
        }
    }
    if (choosing) AlertDialog(onDismissRequest = { choosing = false }, title = { Text("Model ${provider.name}") }, text = {
        Column {
            OutlinedTextField(search, { search = it }, label = { Text("Cari model") }, singleLine = true)
            LazyColumn(Modifier.heightIn(max = 360.dp)) {
                items(provider.models.filter { it.id.contains(search, true) || it.displayName.contains(search, true) }, key = { it.id }) { model ->
                    TextButton(enabled = !state.busy, onClick = { controller.selectOnlineModel(provider.id, model.id); choosing = false }) {
                        Column(Modifier.fillMaxWidth()) { Text(model.displayName); Text(model.id, style = MaterialTheme.typography.labelSmall) }
                    }
                }
            }
        }
    }, confirmButton = { TextButton(onClick = { choosing = false }) { Text("Tutup") } })
}

@Composable
internal fun CoreSettingsCard(state: HubUiState, controller: NativeHubController) {
    if (!state.connected) return
    var editProvider by remember { mutableStateOf<ProviderState?>(null) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Mesin Termux Core", style = MaterialTheme.typography.titleMedium)
            Text("Pengaturan ini mengubah mesin Core, bukan provider Android. API key hanya dikirim ke Core lokal saat disimpan.", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(state.coreRoutingMode == "local", { controller.setCoreMode("local") }, label = { Text("Lokal") }, enabled = !state.busy)
                FilterChip(state.coreRoutingMode == "online", { controller.setCoreMode("online") }, label = { Text("Online") }, enabled = !state.busy)
            }
            if (state.coreRoutingMode == "local") {
                if (state.coreModels.isEmpty()) Text("Belum ada model chat terpasang di Core. Kelola unduhan di Furina Lite.", style = MaterialTheme.typography.bodySmall)
                state.coreModels.forEach { model ->
                    FilterChip(model.selected, { controller.setCoreMode("local", model.path) }, label = { Text(model.name) }, enabled = !state.busy)
                }
            } else state.coreProviders.forEach { p ->
                Row(Modifier.fillMaxWidth()) {
                    Column(Modifier.weight(1f)) { Text(p.name); Text(if (p.configured) "Key ada di Core" else "Belum diatur", style = MaterialTheme.typography.labelSmall) }
                    TextButton(enabled = !state.busy, onClick = { editProvider = p }) { Text("Atur / tes") }
                }
            }
        }
    }
    editProvider?.let { p -> ProviderDialog(p, state.busy, { editProvider = null }) { key -> controller.testCoreProvider(p.id, key); editProvider = null } }
}

@Composable
internal fun HubDataCard(state: HubUiState, controller: NativeHubController) {
    val context = LocalContext.current
    var showRecovery by remember { mutableStateOf(false) }
    var licenses by remember { mutableStateOf<String?>(null) }
    var restoreUri by remember { mutableStateOf<Uri?>(null) }
    var recoveryKey by remember { mutableStateOf("") }
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/markdown")) { it?.let(controller::exportConversation) }
    val backup = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { it?.let(controller::exportBackup) }
    val restore = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { restoreUri = it }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Data & aplikasi", style = MaterialTheme.typography.titleMedium)
            Text("FurinaHub ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodySmall)
            Text("Ekspor chat berupa teks tanpa enkripsi. Backup terenkripsi mencakup database/persona Android, bukan arsip Termux, API key, atau wallpaper.", style = MaterialTheme.typography.bodySmall)
            OutlinedButton(enabled = !state.busy && state.activeConversationId.isNotBlank(), onClick = { export.launch("FurinaHub-chat.md") }) { Text("Ekspor percakapan aktif") }
            OutlinedButton(enabled = !state.busy, onClick = { showRecovery = true }) { Text("Buat backup Android") }
            TextButton(enabled = !state.busy, onClick = { restore.launch(arrayOf("application/octet-stream", "application/zip", "*/*")) }) { Text("Pulihkan backup Android…") }
            TextButton(onClick = { (context as? Activity)?.let { (it.application as? FurinaApplication)?.checkUpdate(it) } }) { Text("Periksa update APK") }
            TextButton(onClick = {
                licenses = listOf("LIANYU-NOTICE.txt", "LIANYU-LICENSE.txt", "ECHOFLOW-LICENSE.txt").joinToString("\n\n") { name -> context.assets.open("licenses/$name").bufferedReader().use { it.readText() } }
            }) { Text("Tentang & lisensi open-source") }
        }
    }
    if (showRecovery) AlertDialog(onDismissRequest = { showRecovery = false }, title = { Text("Simpan kunci pemulihan") },
        text = { Column { Text("Tanpa kunci ini backup tidak dapat dipulihkan. Simpan terpisah dari berkas backup."); SelectionContainer { Text(controller.recoveryKey()) } } },
        confirmButton = { TextButton(onClick = { showRecovery = false; backup.launch("FurinaHub-backup.furina") }) { Text("Sudah disimpan · lanjut") } },
        dismissButton = { TextButton(onClick = { showRecovery = false }) { Text("Batal") } })
    restoreUri?.let { uri -> AlertDialog(onDismissRequest = { restoreUri = null; recoveryKey = "" }, title = { Text("Ganti data Android dari backup?") }, text = {
        Column { Text("Pemulihan mengganti database Android saat ini. Buat backup terlebih dahulu jika masih diperlukan. Data Termux tidak berubah.")
            OutlinedTextField(recoveryKey, { recoveryKey = it }, label = { Text("Kunci pemulihan backup") }, visualTransformation = PasswordVisualTransformation()) }
    }, confirmButton = { TextButton(enabled = recoveryKey.isNotBlank() && !state.busy, onClick = { controller.restoreBackup(uri, recoveryKey); restoreUri = null; recoveryKey = "" }) { Text("Pulihkan") } },
        dismissButton = { TextButton(onClick = { restoreUri = null; recoveryKey = "" }) { Text("Batal") } }) }
    licenses?.let { value -> AlertDialog(onDismissRequest = { licenses = null }, title = { Text("LianYu · EchoFlow") },
        text = { SelectionContainer { Text(value, Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), style = MaterialTheme.typography.bodySmall) } },
        confirmButton = { TextButton(onClick = { licenses = null }) { Text("Tutup") } }) }
}
