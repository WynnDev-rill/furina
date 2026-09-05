package com.wynndev.furina

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Menu
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberDrawerState
import androidx.compose.material3.DrawerValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.key
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.launch

import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material.icons.outlined.PushPin
import androidx.compose.foundation.layout.consumeWindowInsets


@OptIn(ExperimentalMaterial3Api::class)
@Composable internal fun FurinaHubApp(controller: NativeHubController, onConnect: () -> Unit, onTraining: () -> Unit, onDownload: (String) -> Unit) {
    val state by controller.state.collectAsStateWithLifecycle()
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    val chat = state.destination == HubDestination.CHAT
    BackHandler(!chat && !drawer.isOpen) { controller.navigateBack() }
    BackHandler(drawer.isOpen) { scope.launch { drawer.close() } }
    LaunchedEffect(state.error) { state.error?.let { snackbar.showSnackbar(it); controller.clearError() } }
    LaunchedEffect(state.notice) { state.notice?.let { snackbar.showSnackbar(it); controller.clearNotice() } }
    ModalNavigationDrawer(drawerState = drawer, gesturesEnabled = chat, drawerContent = {
        ModalDrawerSheet(Modifier.widthIn(max = 340.dp)) {
            DrawerContent(state,
                onNew = { controller.newConversation(); scope.launch { drawer.close() } },
                onSwitch = { controller.switchConversation(it); scope.launch { drawer.close() } },
                onDelete = controller::deleteConversation, onRename = controller::renameConversation, onPin = controller::pinConversation,
                onNavigate = { controller.setDestination(it); scope.launch { drawer.close() } })
        }
    }) {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbar) },
            topBar = {
                TopAppBar(
                    navigationIcon = {
                        IconButton(onClick = { if (chat) scope.launch { drawer.open() } else controller.navigateBack() }) {
                            Icon(if (chat) Icons.Outlined.Menu else Icons.AutoMirrored.Outlined.ArrowBack, if (chat) "Riwayat percakapan" else "Kembali")
                        }
                    },
                    title = {
                        if (chat) Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(onClick = { controller.setDestination(HubDestination.PERSONA) }) {
                                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer) {
                                    Text(state.assistantName.take(1).uppercase(), Modifier.padding(9.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, fontWeight = FontWeight.SemiBold)
                                }
                            }
                            Column(Modifier.weight(1f).clip(RoundedCornerShape(8.dp)).clickable { controller.setDestination(HubDestination.MODELS) }.padding(vertical = 6.dp)) {
                                Text(state.assistantName, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    val model = if (!state.modelReady) "Pilih model" else if (state.source == HubSource.TERMUX) "Termux Core" else if (state.androidAiMode == OnlineAiConfigStore.MODE_LOCAL) state.androidModels.firstOrNull { it.selected }?.name.orEmpty() else state.providers.firstOrNull { it.selected }?.selectedModel.orEmpty()
                                    Text(model, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, false))
                                    Icon(Icons.Outlined.KeyboardArrowDown, "Model", Modifier.size(16.dp))
                                }
                            }
                        } else Text(when(state.destination) {
                            HubDestination.PERSONA -> "Persona"
                            HubDestination.MEMORY -> "Memori"
                            HubDestination.MODELS -> "Model"
                            HubDestination.APPEARANCE -> "Tampilan chat"
                            HubDestination.DATA -> "Data & aplikasi"
                            HubDestination.TERMUX -> "Termux"
                            else -> "Setelan"
                        }, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    },
                    actions = {
                        if (chat) {
                            IconButton(controller::newConversation, enabled = !state.busy) { Icon(Icons.Outlined.Add, "Percakapan baru") }
                            IconButton({ controller.setDestination(HubDestination.SETTINGS) }) { Icon(Icons.Outlined.Settings, "Setelan") }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
                )
            }
        ) { padding ->
            val body = Modifier.padding(padding).consumeWindowInsets(padding)
            when (state.destination) {
                HubDestination.CHAT -> ChatScreen(state, controller, body)
                HubDestination.PERSONA -> PersonaScreen(state, controller, onTraining, body)
                HubDestination.MEMORY -> MemoryScreen(state, controller, body)
                else -> PreferencesScreen(state, controller, onConnect, onDownload, body)
            }
        }
    }
}

@Composable
private fun DrawerContent(
    state: HubUiState,
    onNew: () -> Unit,
    onSwitch: (String) -> Unit,
    onDelete: (String) -> Unit,
    onRename: (String, String) -> Unit,
    onPin: (String, Boolean) -> Unit,
    onNavigate: (HubDestination) -> Unit,
) {
    var search by rememberSaveable { mutableStateOf("") }
    var selected by remember { mutableStateOf<HubConversation?>(null) }
    var rename by remember { mutableStateOf("") }
    var deleteConfirm by remember { mutableStateOf(false) }
    selected?.let { row ->
        AlertDialog(onDismissRequest = { selected = null; deleteConfirm = false }, title = { Text(if (deleteConfirm) "Hapus percakapan?" else "Kelola percakapan") },
            text = { if (deleteConfirm) Text("Riwayat ini akan dihapus dari sumber ${state.activeSource}. Tindakan ini tidak dapat dibatalkan.") else OutlinedTextField(rename, { rename = it.take(72) }, label = { Text("Judul") }) },
            confirmButton = { TextButton(enabled = !state.busy, onClick = { if (deleteConfirm) onDelete(row.id) else onRename(row.id, rename); selected = null; deleteConfirm = false }) { Text(if (deleteConfirm) "Hapus" else "Simpan") } },
            dismissButton = { Row {
                if (!deleteConfirm) TextButton(enabled = !state.busy, onClick = { onPin(row.id, !row.pinned); selected = null }) { Text(if (row.pinned) "Lepas pin" else "Pin") }
                TextButton(onClick = { if (deleteConfirm) { selected = null; deleteConfirm = false } else deleteConfirm = true }) { Text(if (deleteConfirm) "Batal" else "Hapus…") }
            } })
    }
    Column(Modifier.fillMaxHeight().statusBarsPadding().navigationBarsPadding().padding(horizontal = 12.dp)) {
        Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.primaryContainer) {
                Icon(Icons.Outlined.AutoAwesome, null, Modifier.padding(10.dp), tint = MaterialTheme.colorScheme.primary)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("FurinaHub", fontWeight = FontWeight.Bold, fontSize = 19.sp)
                Text(state.activeSource, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Button(onClick = onNew, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.Add, null)
            Spacer(Modifier.width(8.dp))
            Text("Percakapan baru")
        }
        Spacer(Modifier.height(12.dp))
        Text("Percakapan", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(10.dp))
        OutlinedTextField(search, { search = it }, Modifier.fillMaxWidth(), placeholder = { Text("Cari judul percakapan…") }, singleLine = true)
        LazyColumn(Modifier.weight(1f)) {
            items(state.conversations.filter { it.title.contains(search, true) }, key = { it.id }) { conversation ->
                NavigationDrawerItem(
                    label = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(conversation.title, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                            IconButton(onClick = { selected = conversation; rename = conversation.title }, enabled = !state.busy) {
                                Icon(Icons.Outlined.MoreHoriz, "Kelola percakapan", Modifier.size(18.dp))
                            }
                        }
                    },
                    selected = conversation.id == state.activeConversationId,
                    onClick = { if (!state.busy) onSwitch(conversation.id) },
                    icon = { Icon(if(conversation.pinned) Icons.Outlined.PushPin else Icons.Outlined.History, null) },
                )
            }
        }
        HorizontalDivider()
        listOf(HubDestination.PERSONA to "Persona", HubDestination.MEMORY to "Memori", HubDestination.SETTINGS to "Setelan").forEach { (destination, label) ->
            NavigationDrawerItem(label = { Text(label) }, selected = false, onClick = { onNavigate(destination) })
        }
    }
}
