package com.wynndev.furina

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Send
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material.icons.outlined.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.key
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

import androidx.compose.material.icons.outlined.KeyboardArrowDown
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem


@Composable internal fun ChatScreen(state: HubUiState, controller: NativeHubController, modifier: Modifier = Modifier) {
    val list = rememberLazyListState()
    val scope = rememberCoroutineScope()
    val atBottom by remember { derivedStateOf { !list.canScrollForward } }
    val keyboard = LocalSoftwareKeyboardController.current
    val offset = if (state.historyLimited) 1 else 0
    LaunchedEffect(state.source, state.activeConversationId) {
        if (state.messages.isNotEmpty()) list.scrollToItem(state.messages.lastIndex + offset)
    }
    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.content) {
        if (atBottom && state.messages.isNotEmpty()) list.scrollToItem(state.messages.lastIndex + offset)
    }
    Box(modifier.fillMaxSize()) {
        ChatWallpaper(state.chatAppearance, Modifier.fillMaxSize())
        Column(Modifier.fillMaxSize().imePadding()) {
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            Box(Modifier.weight(1f)) {
                LazyColumn(state = list, modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 20.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    if (state.historyLimited) item(key = "older") {
                        Surface(shape = RoundedCornerShape(16.dp)) {
                            if(state.source == HubSource.ANDROID) TextButton(controller::loadOlderMessages, enabled = !state.busy) { Text("Pesan sebelumnya") }
                            else Text("Arsip lengkap tersedia di Furina Lite.", Modifier.padding(12.dp), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    if (state.messages.isEmpty() && !state.loading) item(key = "welcome") {
                        Surface(Modifier.fillMaxWidth().padding(top = 32.dp), shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface) {
                            Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text(if(state.userNickname.isBlank()) "Halo, aku " + state.assistantName + "." else "Halo, " + state.userNickname + ".", style = MaterialTheme.typography.headlineSmall)
                                Text(if(state.modelReady) "Apa yang ingin kamu ceritakan hari ini?" else "Pilih model untuk memulai percakapan.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                if (!state.modelReady) Button({ controller.setDestination(HubDestination.MODELS) }) { Text("Pilih model") }
                            }
                        }
                    }
                    items(state.messages, key = { it.id }) { message ->
                        MessageBubble(message, if (!state.busy && state.source == HubSource.ANDROID && message.role == "user") ({ controller.editInBranch(message) }) else null)
                    }
                }
                if (!atBottom && state.messages.isNotEmpty()) FilledIconButton(
                    onClick = { scope.launch { list.animateScrollToItem(state.messages.lastIndex + offset) } },
                    modifier = Modifier.align(Alignment.BottomCenter).padding(12.dp)) {
                    Icon(Icons.Outlined.KeyboardArrowDown, "Pesan terbaru")
                }
            }
            Surface(color = MaterialTheme.colorScheme.surface) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.Bottom) {
                    OutlinedTextField(state.draft, controller::setDraft, Modifier.weight(1f),
                        placeholder = { Text("Kirim pesan…") }, minLines = 1, maxLines = 6,
                        shape = RoundedCornerShape(24.dp),
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Default))
                    Spacer(Modifier.width(8.dp))
                    FilledIconButton(onClick = {
                        if(state.generating) controller.stopGeneration() else if(controller.send(state.draft)) keyboard?.hide()
                    }, enabled = state.generating || (!state.busy && !state.loading && state.draft.isNotBlank()), modifier = Modifier.size(48.dp)) {
                        Icon(if(state.generating) Icons.Outlined.Stop else Icons.AutoMirrored.Outlined.Send, if(state.generating) "Hentikan" else "Kirim")
                    }
                }
            }
        }
    }
}

@Composable private fun MessageBubble(message: HubMessage, onBranch: (() -> Unit)?) {
    val user = message.role == "user"
    val clipboard = LocalClipboardManager.current
    var menu by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if(user) Arrangement.End else Arrangement.Start) {
        Surface(Modifier.widthIn(max = 720.dp).fillMaxWidth(if(user) .88f else .96f), shape = RoundedCornerShape(20.dp),
            color = if(user) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface) {
            Column(Modifier.padding(start = 16.dp, end = 12.dp, top = 14.dp, bottom = 6.dp)) {
                if (message.pending && message.content.isBlank()) Row(Modifier.padding(bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Text("Menyiapkan jawaban…", Modifier.padding(start = 12.dp), style = MaterialTheme.typography.bodyMedium)
                } else SelectionContainer { HubMessageText(message.content) }
                if(!message.pending && message.content.isNotBlank()) Box(Modifier.align(Alignment.End)) {
                    IconButton({ menu = true }, Modifier.size(48.dp)) { Icon(Icons.Outlined.MoreHoriz, "Opsi pesan", Modifier.size(20.dp)) }
                    DropdownMenu(menu, { menu = false }) {
                        DropdownMenuItem(text = { Text("Salin") }, onClick = { clipboard.setText(AnnotatedString(message.content)); menu = false })
                        if(onBranch != null) DropdownMenuItem(text = { Text("Edit di percakapan baru") }, onClick = { menu = false; onBranch() })
                    }
                }
            }
        }
    }
}
