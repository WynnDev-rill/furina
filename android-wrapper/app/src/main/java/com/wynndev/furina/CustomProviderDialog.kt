package com.wynndev.furina

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable internal fun CustomProviderDialog(state: HubUiState, onDismiss: () -> Unit, onConfirm: (String, String, String) -> Unit) {
    var endpoint by remember { mutableStateOf(state.customEndpoint) }
    var model by remember { mutableStateOf(state.customModelId) }
    var key by remember { mutableStateOf("") }
    AlertDialog(onDismissRequest = onDismiss, title = { Text("Endpoint sendiri") }, text = {
        Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Gunakan server OpenAI-compatible. Tes mengirim satu pesan singkat; biaya mengikuti server.")
            OutlinedTextField(endpoint, { endpoint = it }, Modifier.fillMaxWidth(), label = { Text("Alamat endpoint") }, placeholder = { Text("https://server.example/v1") }, singleLine = true)
            OutlinedTextField(model, { model = it }, Modifier.fillMaxWidth(), label = { Text("ID model") }, singleLine = true)
            OutlinedTextField(key, { key = it }, Modifier.fillMaxWidth(), label = { Text("API key (opsional)") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
            Text("Untuk server di Termux, gunakan http://127.0.0.1:PORT/v1. Kosongkan key untuk memakai key tersimpan pada alamat yang sama.", style = MaterialTheme.typography.bodySmall)
        }
    }, confirmButton = { Button(enabled = !state.busy && endpoint.isNotBlank() && model.isNotBlank(), onClick = { onConfirm(endpoint, model, key) }) { Text("Simpan & tes") } },
        dismissButton = { TextButton(onDismiss) { Text("Batal") } })
}
