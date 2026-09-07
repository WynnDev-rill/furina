package com.wynndev.furina

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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.Terminal
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp


@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun PersonaScreen(state: HubUiState, controller: NativeHubController, onTraining: () -> Unit, modifier: Modifier = Modifier) {
    var name by rememberSaveable(state.assistantName) { mutableStateOf(state.assistantName) }
    var nickname by rememberSaveable(state.userNickname) { mutableStateOf(state.userNickname) }
    var instructions by rememberSaveable(state.customInstructions) { mutableStateOf(state.customInstructions) }
    Column(modifier.fillMaxSize().imePadding().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        SectionHeader("Kenali satu sama lain", "Atur nama dan cara kalian berbicara.")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), label = { Text("Nama companion") }, singleLine = true)
                OutlinedTextField(nickname, { nickname = it }, Modifier.fillMaxWidth(), label = { Text("Nama panggilanmu") }, singleLine = true)
                OutlinedTextField(instructions, { instructions = it }, Modifier.fillMaxWidth(), label = { Text("Instruksi personal") }, minLines = 3, maxLines = 7)
                Button(onClick = { controller.saveIdentity(name, nickname, instructions) }, enabled = !state.busy, modifier = Modifier.align(Alignment.End)) { Text("Simpan identitas") }
            }
        }

        SectionHeader("Kepribadian", "Pilih sifat yang kamu sukai.")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            FurinaTraits.forEach { trait ->
                FilterChip(
                    selected = trait.id in state.selectedTraits,
                    onClick = { controller.toggleTrait(trait.id) },
                    enabled = !state.busy,
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

        SectionHeader("Cara berinteraksi", "")
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(horizontal = 16.dp)) {
                SettingSwitch("Mode pasangan", "Izinkan percakapan romantis.", state.partnerMode) { controller.setAdvanced("partner_mode", it) }
                SettingSwitch("Roleplay", "Izinkan Furina mengikuti adegan fiksional saat diminta.", state.roleplayMode) { controller.setAdvanced("roleplay_mode", it) }
                SettingSwitch("Memori lokal penuh", "Ingat konteks dari percakapan lain.", state.fullLocalMemory) { controller.setAdvanced("full_local_memory", it) }
                SettingSwitch("Saran latihan di Core", "Bandingkan jawaban untuk memilih yang kamu sukai.", state.trainingSuggestions) { controller.setAdvanced("training_suggestions", it) }
                SettingSwitch("Suara batin fiksional", "Tambahkan pikiran singkat dari karakter.", state.innerThoughts) { controller.setAdvanced("inner_thoughts", it) }
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
                Text("Pilih jawaban yang lebih kamu sukai melalui Furina Lite di Termux.", style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(12.dp))
                OutlinedButton(onClick = onTraining) {
                    Icon(Icons.Outlined.Terminal, null)
                    Spacer(Modifier.width(8.dp))
                    Text("Buka Furina Lite")
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

