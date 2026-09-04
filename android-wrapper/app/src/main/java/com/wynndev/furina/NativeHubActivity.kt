package com.wynndev.furina

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Chat
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Link
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.Menu
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material.icons.outlined.Terminal
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.rememberDrawerState
import androidx.compose.material3.DrawerValue
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import kotlinx.coroutines.launch

class NativeHubActivity : ComponentActivity() {
    private lateinit var controller: NativeHubController

    private val runCommandPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) controller.connectTermux(this) else controller.permissionDenied()
    }

    private val notificationPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        controller = NativeHubController(applicationContext)
        setContent {
            FurinaHubTheme {
                FurinaHubApp(
                    controller = controller,
                    onConnect = {
                        if (controller.canRunTermux()) controller.connectTermux(this)
                        else runCommandPermission.launch(TermuxBridgeClient.RUN_COMMAND_PERMISSION)
                    },
                    onTraining = {
                        if (controller.canRunTermux()) controller.openTrainingRoom(this)
                        else runCommandPermission.launch(TermuxBridgeClient.RUN_COMMAND_PERMISSION)
                    },
                    onDownload = { modelId ->
                        if (Build.VERSION.SDK_INT >= 33) notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                        controller.downloadAndroidModel(modelId)
                    },
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (::controller.isInitialized) controller.refresh()
    }

    override fun onDestroy() {
        if (::controller.isInitialized) controller.close()
        super.onDestroy()
    }
}

private val LightColors = lightColorScheme(
    primary = Color(0xFF6256C7),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE6E0FF),
    onPrimaryContainer = Color(0xFF1D1763),
    secondary = Color(0xFF49688D),
    surface = Color(0xFFFCF8FF),
    surfaceVariant = Color(0xFFE7E1EB),
    background = Color(0xFFF8F4FC),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFC8BFFF),
    onPrimary = Color(0xFF302879),
    primaryContainer = Color(0xFF47408F),
    onPrimaryContainer = Color(0xFFE6E0FF),
    secondary = Color(0xFFAFC9EF),
    surface = Color(0xFF15131A),
    surfaceVariant = Color(0xFF302D36),
    background = Color(0xFF111016),
)

@Composable
private fun FurinaHubTheme(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val dark = androidx.compose.foundation.isSystemInDarkTheme()
    val colors = if (Build.VERSION.SDK_INT >= 31) {
        if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
    } else if (dark) DarkColors else LightColors
    val view = LocalView.current
    DisposableEffect(dark) {
        val window = (view.context as? ComponentActivity)?.window
        if (window != null) {
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !dark
                isAppearanceLightNavigationBars = !dark
            }
        }
        onDispose { }
    }
    MaterialTheme(colorScheme = colors, content = content)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun FurinaHubApp(
    controller: NativeHubController,
    onConnect: () -> Unit,
    onTraining: () -> Unit,
    onDownload: (String) -> Unit,
) {
    val state by controller.state.collectAsState()
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val coroutineScope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbar.showSnackbar(it)
            controller.clearError()
        }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        gesturesEnabled = state.destination == HubDestination.CHAT,
        drawerContent = {
            ModalDrawerSheet(modifier = Modifier.widthIn(max = 340.dp)) {
                DrawerContent(
                    state = state,
                    onNew = {
                        controller.newConversation()
                        coroutineScope.launch { drawerState.close() }
                    },
                    onSwitch = {
                        controller.switchConversation(it)
                        coroutineScope.launch { drawerState.close() }
                    },
                    onDelete = controller::deleteConversation,
                )
            }
        },
    ) {
        Scaffold(
            snackbarHost = { SnackbarHost(snackbar) },
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text(
                                when (state.destination) {
                                    HubDestination.CHAT -> state.assistantName
                                    HubDestination.PERSONA -> "Persona"
                                    HubDestination.MEMORY -> "Memori"
                                    HubDestination.SETTINGS -> "Pengaturan"
                                },
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            if (state.destination == HubDestination.CHAT) Text(state.activeSource, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    },
                    navigationIcon = {
                        if (state.destination == HubDestination.CHAT) IconButton(onClick = { coroutineScope.launch { drawerState.open() } }) {
                            Icon(Icons.Outlined.Menu, "Riwayat percakapan")
                        }
                    },
                    actions = {
                        ConnectionPill(state.connected, state.busy, onConnect)
                        if (state.destination == HubDestination.CHAT) IconButton(onClick = controller::newConversation) {
                            Icon(Icons.Outlined.Add, "Percakapan baru")
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = .96f)),
                )
            },
            bottomBar = {
                NavigationBar {
                    DestinationItem(HubDestination.CHAT, state.destination, Icons.AutoMirrored.Outlined.Chat, "Chat", controller::setDestination)
                    DestinationItem(HubDestination.PERSONA, state.destination, Icons.Outlined.Psychology, "Persona", controller::setDestination)
                    DestinationItem(HubDestination.MEMORY, state.destination, Icons.Outlined.Memory, "Memori", controller::setDestination)
                    DestinationItem(HubDestination.SETTINGS, state.destination, Icons.Outlined.Settings, "Setelan", controller::setDestination)
                }
            },
        ) { padding ->
            when (state.destination) {
                HubDestination.CHAT -> ChatScreen(state, controller::send, controller::stopGeneration, Modifier.padding(padding))
                HubDestination.PERSONA -> PersonaScreen(state, controller, onTraining, Modifier.padding(padding))
                HubDestination.MEMORY -> MemoryScreen(state, controller, Modifier.padding(padding))
                HubDestination.SETTINGS -> SettingsScreen(state, controller, onConnect, onDownload, Modifier.padding(padding))
            }
        }
    }
}

@Composable
private fun RowScope.DestinationItem(
    destination: HubDestination,
    selected: HubDestination,
    icon: ImageVector,
    label: String,
    navigate: (HubDestination) -> Unit,
) {
    NavigationBarItem(
        selected = destination == selected,
        onClick = { navigate(destination) },
        icon = { Icon(icon, label) },
        label = { Text(label) },
    )
}

@Composable
private fun ConnectionPill(connected: Boolean, busy: Boolean, onConnect: () -> Unit) {
    AssistChip(
        onClick = onConnect,
        label = { Text(if (busy) "Menghubungkan" else if (connected) "Core aktif" else "Hubungkan") },
        leadingIcon = {
            if (busy) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
            else Box(Modifier.size(9.dp).clip(CircleShape).background(if (connected) Color(0xFF2BA56B) else MaterialTheme.colorScheme.outline))
        },
        modifier = Modifier.padding(end = 4.dp),
    )
}

@Composable
private fun DrawerContent(
    state: HubUiState,
    onNew: () -> Unit,
    onSwitch: (String) -> Unit,
    onDelete: (String) -> Unit,
) {
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
        Button(onClick = onNew, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.Add, null)
            Spacer(Modifier.width(8.dp))
            Text("Percakapan baru")
        }
        Spacer(Modifier.height(12.dp))
        Text("Percakapan", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(10.dp))
        LazyColumn(Modifier.weight(1f)) {
            items(state.conversations, key = { it.id }) { conversation ->
                NavigationDrawerItem(
                    label = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(conversation.title, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                            IconButton(onClick = { onDelete(conversation.id) }, modifier = Modifier.size(34.dp)) {
                                Icon(Icons.Outlined.DeleteOutline, "Hapus", Modifier.size(18.dp))
                            }
                        }
                    },
                    selected = conversation.id == state.activeConversationId,
                    onClick = { onSwitch(conversation.id) },
                    icon = { Icon(Icons.Outlined.History, null) },
                )
            }
        }
        Text(
            if (state.connected) "Termux Core ${state.coreVersion.ifBlank { "aktif" }}" else "Mode Android tetap dapat dipakai tanpa Termux",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(12.dp),
        )
    }
}

@Composable
private fun ChatScreen(
    state: HubUiState,
    send: (String) -> Unit,
    stop: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var input by rememberSaveable { mutableStateOf("") }
    val listState = rememberLazyListState()
    val keyboard = LocalSoftwareKeyboardController.current
    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.content) {
        if (state.messages.isNotEmpty()) listState.animateScrollToItem(state.messages.lastIndex)
    }
    Column(modifier.fillMaxSize().imePadding()) {
        if (state.connectionState == "checking") LinearProgressIndicator(Modifier.fillMaxWidth())
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 14.dp, vertical = 18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (state.messages.isEmpty()) item { WelcomeCard(state) }
            items(state.messages, key = { it.id }) { message -> MessageBubble(message) }
        }
        Text(
            state.status,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 20.dp, vertical = 3.dp),
        )
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.Bottom) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it.take(12_000) },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Kirim pesan…") },
                minLines = 1,
                maxLines = 6,
                shape = RoundedCornerShape(24.dp),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = {
                    if (input.isNotBlank() && !state.busy) {
                        val value = input
                        input = ""
                        keyboard?.hide()
                        send(value)
                    }
                }),
            )
            Spacer(Modifier.width(8.dp))
            FilledIconButton(
                onClick = {
                    if (state.busy) stop()
                    else if (input.isNotBlank()) {
                        val value = input
                        input = ""
                        keyboard?.hide()
                        send(value)
                    }
                },
                enabled = state.busy || input.isNotBlank(),
                modifier = Modifier.size(52.dp),
            ) {
                Icon(if (state.busy) Icons.Outlined.Stop else Icons.AutoMirrored.Outlined.Send, if (state.busy) "Hentikan" else "Kirim")
            }
        }
    }
}

@Composable
private fun WelcomeCard(state: HubUiState) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 36.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = .55f)),
    ) {
        Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.primary) {
                Icon(Icons.Outlined.AutoAwesome, null, Modifier.padding(15.dp).size(28.dp), tint = MaterialTheme.colorScheme.onPrimary)
            }
            Spacer(Modifier.height(16.dp))
            Text("${state.assistantName} siap", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(7.dp))
            Text(
                if (state.connected) "Terhubung ke memori dan hubungan Furina Lite di Termux."
                else "Gunakan mesin Android mandiri, atau hubungkan Termux untuk memakai Core dan memori yang sama.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun MessageBubble(message: HubMessage) {
    val user = message.role == "user"
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (user) Arrangement.End else Arrangement.Start) {
        Surface(
            modifier = Modifier.widthIn(max = 690.dp).fillMaxWidth(if (user) .86f else .94f),
            shape = RoundedCornerShape(
                topStart = if (user) 20.dp else 7.dp,
                topEnd = if (user) 7.dp else 20.dp,
                bottomStart = 20.dp,
                bottomEnd = 20.dp,
            ),
            color = if (user) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .58f),
            tonalElevation = if (user) 0.dp else 1.dp,
        ) {
            Column(Modifier.padding(horizontal = 15.dp, vertical = 12.dp)) {
                if (message.content.isBlank() && message.pending) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(9.dp))
                        Text("Sedang berpikir…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                } else Text(message.content, style = MaterialTheme.typography.bodyLarge, lineHeight = 24.sp)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PersonaScreen(state: HubUiState, controller: NativeHubController, onTraining: () -> Unit, modifier: Modifier = Modifier) {
    var name by rememberSaveable(state.assistantName) { mutableStateOf(state.assistantName) }
    var nickname by rememberSaveable(state.userNickname) { mutableStateOf(state.userNickname) }
    var instructions by rememberSaveable(state.customInstructions) { mutableStateOf(state.customInstructions) }
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        SectionHeader("Identitas", "Satu identitas yang dipakai di Android dan Termux.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), label = { Text("Nama companion") }, singleLine = true)
                OutlinedTextField(nickname, { nickname = it }, Modifier.fillMaxWidth(), label = { Text("Nama panggilanmu") }, singleLine = true)
                OutlinedTextField(instructions, { instructions = it }, Modifier.fillMaxWidth(), label = { Text("Instruksi personal") }, minLines = 3, maxLines = 7)
                Button(onClick = { controller.saveIdentity(name, nickname, instructions) }, modifier = Modifier.align(Alignment.End)) { Text("Simpan identitas") }
            }
        }

        SectionHeader("Kepribadian", "Pilih kombinasi bebas. Semua sifat menyatu, bukan berganti-ganti preset.")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            FurinaTraits.forEach { trait ->
                FilterChip(
                    selected = trait.id in state.selectedTraits,
                    onClick = { controller.toggleTrait(trait.id) },
                    label = { Text(trait.label) },
                    leadingIcon = if (trait.id in state.selectedTraits) ({ Icon(Icons.Outlined.AutoAwesome, null, Modifier.size(17.dp)) }) else null,
                )
            }
        }
        if (state.selectedTraits.isNotEmpty()) {
            Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .45f))) {
                Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                    FurinaTraits.filter { it.id in state.selectedTraits }.forEach { Text("${it.label} — ${it.description}", style = MaterialTheme.typography.bodySmall) }
                }
            }
        }

        SectionHeader("Lanjutan", "Mode yang sebelumnya hanya ada di Furina Lite kini dapat diatur dari Hub.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(horizontal = 16.dp)) {
                SettingSwitch("Mode pasangan", "Hubungan romantis eksplisit dengan batas sehat.", state.partnerMode) { controller.setAdvanced("partner_mode", it) }
                SettingSwitch("Roleplay", "Izinkan Furina mengikuti adegan fiksional saat diminta.", state.roleplayMode) { controller.setAdvanced("roleplay_mode", it) }
                SettingSwitch("Memori lokal penuh", "Arsipkan percakapan baru secara lokal untuk kontinuitas.", state.fullLocalMemory) { controller.setAdvanced("full_local_memory", it) }
                SettingSwitch("Saran latihan", "Tawarkan A/B ketika gaya respons perlu dipelajari.", state.trainingSuggestions) { controller.setAdvanced("training_suggestions", it) }
                SettingSwitch("Suara batin fiksional", "Tambahkan pikiran karakter singkat bila cocok; bukan reasoning.", state.innerThoughts) { controller.setAdvanced("inner_thoughts", it) }
            }
        }
        Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = .42f))) {
            Column(Modifier.padding(17.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Psychology, null, tint = MaterialTheme.colorScheme.primary)
                    Spacer(Modifier.width(10.dp))
                    Text("Training Room", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                }
                Spacer(Modifier.height(7.dp))
                Text("Latih preferensi respons A/B tanpa menjadikan skenario latihan sebagai memori. Training Room lengkap dibuka pada Furina Lite agar memakai mesin dan data yang sama.", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = onTraining) {
                    Icon(Icons.Outlined.Terminal, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Buka Training Room di Termux")
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun MemoryScreen(state: HubUiState, controller: NativeHubController, modifier: Modifier = Modifier) {
    var input by rememberSaveable { mutableStateOf("") }
    Column(modifier.fillMaxSize().padding(16.dp)) {
        SectionHeader("Memori bersama", if (state.activeSource.startsWith("Termux")) "Disimpan oleh Core dan terlihat di Furina Lite." else "Disimpan privat di database Android.")
        Card(Modifier.fillMaxWidth()) {
            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(input, { input = it.take(600) }, Modifier.weight(1f), placeholder = { Text("Tambahkan hal yang perlu diingat…") }, minLines = 1, maxLines = 4)
                Spacer(Modifier.width(8.dp))
                FilledIconButton(onClick = { controller.addMemory(input); input = "" }, enabled = input.trim().length >= 3) { Icon(Icons.Outlined.Add, "Tambah") }
            }
        }
        Spacer(Modifier.height(12.dp))
        if (state.memories.isEmpty()) {
            EmptyState(Icons.Outlined.Memory, "Belum ada memori", "Fakta penting dari percakapan akan muncul di sini.", Modifier.weight(1f))
        } else {
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(state.memories, key = { it.id }) { memory ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(start = 15.dp, top = 12.dp, bottom = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(memory.text, style = MaterialTheme.typography.bodyMedium)
                                Text(memory.kind.replace('_', ' '), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            IconButton(onClick = { controller.deleteMemory(memory.id) }) { Icon(Icons.Outlined.DeleteOutline, "Hapus memori") }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SettingsScreen(
    state: HubUiState,
    controller: NativeHubController,
    onConnect: () -> Unit,
    onDownload: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var providerDialog by remember { mutableStateOf<ProviderState?>(null) }
    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        SectionHeader("Sumber mesin", "Otomatis memakai Termux saat tersedia dan berpindah ke Android saat Core mati.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    EnginePreference.entries.forEach { preference ->
                        FilterChip(
                            selected = state.enginePreference == preference,
                            onClick = { controller.setEnginePreference(preference) },
                            label = { Text(when (preference) { EnginePreference.AUTO -> "Otomatis"; EnginePreference.TERMUX -> "Termux"; EnginePreference.ANDROID -> "Android" }) },
                        )
                    }
                }
                HorizontalDivider()
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Terminal, null, tint = if (state.connected) Color(0xFF2BA56B) else MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.width(11.dp))
                    Column(Modifier.weight(1f)) {
                        Text(if (state.connected) "Termux Core ${state.coreVersion}" else state.connectionMessage, fontWeight = FontWeight.Medium)
                        Text(if (state.connected) "Token sesi aktif · hanya localhost" else "Izin RUN_COMMAND diminta sekali oleh Android.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = onConnect, enabled = !state.busy) { Icon(Icons.Outlined.Link, null); Spacer(Modifier.width(7.dp)); Text(if (state.connected) "Hubungkan ulang" else "Hubungkan") }
                    if (state.connected) OutlinedButton(onClick = controller::disconnectTermux) { Text("Lepas sesi") }
                    IconButton(onClick = controller::refresh) { Icon(Icons.Outlined.Refresh, "Segarkan") }
                }
            }
        }

        SectionHeader("Mesin Android mandiri", "Dari fondasi Furina lama: llama.cpp lokal dan provider online tetap tersedia tanpa Termux.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = state.androidAiMode == OnlineAiConfigStore.MODE_LOCAL, onClick = { controller.setAndroidAiMode(OnlineAiConfigStore.MODE_LOCAL) }, label = { Text("Model lokal") })
                    FilterChip(selected = state.androidAiMode == OnlineAiConfigStore.MODE_ONLINE, onClick = { controller.setAndroidAiMode(OnlineAiConfigStore.MODE_ONLINE) }, label = { Text("Provider online") })
                }
                AnimatedVisibility(state.androidAiMode == OnlineAiConfigStore.MODE_LOCAL) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        state.androidModels.forEach { model -> ModelRow(model, { controller.selectAndroidModel(model.id) }, { onDownload(model.id) }, { controller.deleteAndroidModel(model.id) }) }
                    }
                }
                AnimatedVisibility(state.androidAiMode == OnlineAiConfigStore.MODE_ONLINE) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("API key dienkripsi dengan Android Keystore. Furina hanya menawarkan model yang masuk katalog free-tier.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        state.providers.forEach { provider ->
                            Surface(
                                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable { controller.selectProvider(provider.id) },
                                color = if (provider.selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .5f),
                            ) {
                                Row(Modifier.padding(13.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Icon(Icons.Outlined.AutoAwesome, null)
                                    Spacer(Modifier.width(10.dp))
                                    Column(Modifier.weight(1f)) { Text(provider.name, fontWeight = FontWeight.Medium); Text(if (provider.configured) "Key tersimpan" else "Belum dikonfigurasi", style = MaterialTheme.typography.labelSmall) }
                                    TextButton(onClick = { providerDialog = provider }) { Text(if (provider.configured) "Tes" else "Atur") }
                                }
                            }
                        }
                    }
                }
            }
        }

        Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .38f))) {
            Column(Modifier.padding(16.dp)) {
                Text("Privasi & batas integrasi", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(6.dp))
                Text("FurinaHub tidak membaca folder privat Termux. APK hanya menyalakan executable Furina yang sudah terpasang, lalu berbicara ke 127.0.0.1:8787 memakai token acak. Tidak ada akses root, Shizuku, atau Accessibility di build ini.", style = MaterialTheme.typography.bodySmall)
            }
        }
        Spacer(Modifier.height(8.dp))
    }

    providerDialog?.let { provider ->
        ProviderDialog(provider, state.busy, onDismiss = { providerDialog = null }) { key ->
            controller.selectProvider(provider.id)
            controller.saveAndTestProvider(provider.id, key)
            providerDialog = null
        }
    }
}

@Composable
private fun ModelRow(model: AndroidModelState, select: () -> Unit, download: () -> Unit, delete: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable(onClick = select),
        color = if (model.selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .5f),
    ) {
        Column(Modifier.padding(13.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Memory, null)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(model.name, fontWeight = FontWeight.Medium)
                    Text(model.subtitle, style = MaterialTheme.typography.labelSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                when (model.state) {
                    "ready" -> IconButton(onClick = delete) { Icon(Icons.Outlined.DeleteOutline, "Hapus") }
                    "running", "downloading", "verifying" -> CircularProgressIndicator(Modifier.size(25.dp), strokeWidth = 2.dp)
                    else -> IconButton(onClick = download) { Icon(Icons.Outlined.Download, "Unduh") }
                }
            }
            if (model.progress > 0f && model.state != "ready") LinearProgressIndicator({ model.progress }, Modifier.fillMaxWidth().padding(top = 8.dp))
        }
    }
}

@Composable
private fun ProviderDialog(provider: ProviderState, busy: Boolean, onDismiss: () -> Unit, onConfirm: (String) -> Unit) {
    var key by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(provider.name) },
        text = {
            Column {
                Text(if (provider.configured) "Biarkan kosong untuk mengetes key yang sudah tersimpan." else "Masukkan API key. Key disimpan terenkripsi di perangkat.")
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(key, { key = it }, Modifier.fillMaxWidth(), label = { Text("API key") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
            }
        },
        confirmButton = { Button(onClick = { onConfirm(key) }, enabled = !busy && (provider.configured || key.length >= 8)) { Text("Simpan & tes") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Batal") } },
    )
}

@Composable
private fun SettingSwitch(title: String, description: String, checked: Boolean, onChecked: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().toggleable(checked, role = Role.Switch, onValueChange = onChecked).padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.Medium)
            Text(description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked, onCheckedChange = null)
    }
}

@Composable
private fun SectionHeader(title: String, subtitle: String) {
    Column {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun EmptyState(icon: ImageVector, title: String, subtitle: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(32.dp)) {
            Icon(icon, null, Modifier.size(42.dp), tint = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.height(12.dp))
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Medium)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
