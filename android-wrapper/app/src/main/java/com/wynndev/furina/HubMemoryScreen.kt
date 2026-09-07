package com.wynndev.furina

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.key
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp



@Composable internal fun MemoryScreen(state: HubUiState, controller: NativeHubController, modifier: Modifier = Modifier) {
    var query by rememberSaveable { mutableStateOf("") }
    var input by rememberSaveable { mutableStateOf("") }
    var adding by rememberSaveable { mutableStateOf(false) }
    var removing by remember { mutableStateOf<HubMemory?>(null) }
    val matches = remember(query, state.memories) { state.memories.filter { it.text.contains(query, true) } }
    Column(modifier.fillMaxSize().imePadding().padding(horizontal = 16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(query, { query = it }, Modifier.weight(1f), placeholder = { Text("Cari memori…") }, singleLine = true, shape = RoundedCornerShape(16.dp))
            IconButton({ adding = true }, enabled = !state.busy) { Icon(Icons.Outlined.Add, "Tambah memori") }
        }
        if(matches.isEmpty()) EmptyState(Icons.Outlined.Memory, if(query.isBlank()) "Hal yang ingin diingat" else "Tidak ada hasil",
            if(query.isBlank()) "Simpan hal penting tentang dirimu dan percakapan kalian." else "Coba kata lain.", Modifier.weight(1f))
        else LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(matches, key = { it.id }) { memory ->
                Surface(shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .4f)) {
                    Row(Modifier.fillMaxWidth().padding(start = 16.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                        SelectionContainer(Modifier.weight(1f)) { Text(memory.text, style = MaterialTheme.typography.bodyLarge) }
                        IconButton({ removing = memory }, enabled = !state.busy) { Icon(Icons.Outlined.DeleteOutline, "Hapus memori") }
                    }
                }
            }
        }
    }
    if(adding) AlertDialog(onDismissRequest = { adding = false }, title = { Text("Memori baru") }, text = {
        OutlinedTextField(input, { input = it.take(500) }, label = { Text("Hal yang perlu diingat") }, minLines = 3, maxLines = 6)
    }, confirmButton = { TextButton(enabled = !state.busy && input.trim().length >= 4, onClick = {
        controller.addMemory(input) { input = ""; adding = false }
    }) { Text("Simpan") } }, dismissButton = { TextButton({ adding = false }) { Text("Batal") } })
    removing?.let { memory -> AlertDialog(onDismissRequest = { removing = null }, title = { Text("Hapus memori?") }, text = { Text(memory.text) },
        confirmButton = { TextButton(enabled = !state.busy, onClick = { controller.deleteMemory(memory.id); removing = null }) { Text("Hapus") } },
        dismissButton = { TextButton({ removing = null }) { Text("Batal") } }) }
}
