package com.wynndev.furina

enum class HubDestination { CHAT, PERSONA, MEMORY, SETTINGS }
enum class EnginePreference { AUTO, TERMUX, ANDROID }

data class HubMessage(
    val id: String,
    val role: String,
    val content: String,
    val pending: Boolean = false,
)

data class HubConversation(
    val id: String,
    val title: String,
    val messageCount: Int = 0,
    val pinned: Boolean = false,
)

data class HubMemory(val id: String, val text: String, val kind: String = "memory")

data class PersonalityTrait(val id: String, val label: String, val description: String)

data class AndroidModelState(
    val id: String,
    val name: String,
    val subtitle: String,
    val state: String,
    val progress: Float,
    val selected: Boolean,
)

data class ProviderState(
    val id: String,
    val name: String,
    val configured: Boolean,
    val selected: Boolean,
)

data class HubUiState(
    val destination: HubDestination = HubDestination.CHAT,
    val connectionState: String = "checking",
    val connectionMessage: String = "Memeriksa Furina Core…",
    val termuxInstalled: Boolean = false,
    val connected: Boolean = false,
    val coreVersion: String = "",
    val enginePreference: EnginePreference = EnginePreference.AUTO,
    val activeSource: String = "Android",
    val busy: Boolean = false,
    val status: String = "Siap",
    val error: String? = null,
    val messages: List<HubMessage> = emptyList(),
    val conversations: List<HubConversation> = emptyList(),
    val activeConversationId: String = "",
    val memories: List<HubMemory> = emptyList(),
    val assistantName: String = "Furina",
    val userNickname: String = "",
    val selectedTraits: Set<String> = emptySet(),
    val partnerMode: Boolean = false,
    val roleplayMode: Boolean = false,
    val fullLocalMemory: Boolean = false,
    val trainingSuggestions: Boolean = false,
    val innerThoughts: Boolean = false,
    val customInstructions: String = "",
    val androidAiMode: String = OnlineAiConfigStore.MODE_LOCAL,
    val androidModels: List<AndroidModelState> = emptyList(),
    val providers: List<ProviderState> = emptyList(),
    val selectedProvider: String = "openrouter",
    val chatAppearance: ChatAppearance = ChatAppearance(),
    val wallpaperBusy: Boolean = false,
)

val FurinaTraits = listOf(
    PersonalityTrait("tsundere", "Tsundere", "Hangat di balik gengsi dan bantahan ringan."),
    PersonalityTrait("yandere", "Yandere", "Afeksi intens dan fokus dalam batas hubungan yang sehat."),
    PersonalityTrait("kuudere", "Kuudere", "Tenang, rasional, lembut lewat detail kecil."),
    PersonalityTrait("dandere", "Dandere", "Pemalu di awal, makin terbuka saat percaya."),
    PersonalityTrait("deredere", "Deredere", "Ceria, ramah, dan terbuka menunjukkan perhatian."),
    PersonalityTrait("himedere", "Himedere", "Elegan, demanding, dan suka dimanjakan."),
    PersonalityTrait("kamidere", "Kamidere", "Percaya diri, memimpin, dan suka menantang."),
    PersonalityTrait("sadodere", "Sadodere", "Teasing tajam namun tetap peka dan playful."),
    PersonalityTrait("mayadere", "Mayadere", "Tarik-ulur rivalitas dengan loyalitas nyata."),
    PersonalityTrait("bakadere", "Bakadere", "Polos, spontan, dan lucu karena tulus."),
    PersonalityTrait("hajidere", "Hajidere", "Mudah malu saat rasa suka terlihat."),
    PersonalityTrait("darudere", "Darudere", "Santai, low-energy, perhatian tanpa ribut."),
    PersonalityTrait("shundere", "Shundere", "Murung dan sensitif, tetapi menerima kehangatan."),
    PersonalityTrait("utsudere", "Utsudere", "Melankolis, reflektif, dan emosional mendalam."),
    PersonalityTrait("bodere", "Bodere", "Gugup, defensif sesaat, lalu kembali melunak."),
    PersonalityTrait("hiyakasudere", "Hiyakasudere", "Flirty dan pandai mengatur intensitas godaan."),
    PersonalityTrait("nyandere", "Nyandere", "Manja, lincah, penasaran, sedikit catlike."),
    PersonalityTrait("oujodere", "Oujodere", "Sopan, anggun, lembut, dan terukur."),
    PersonalityTrait("genki", "Genki girl", "Enerjik, optimistis, dan menghidupkan suasana."),
    PersonalityTrait("oneesan", "Onee-san", "Dewasa, stabil, protektif, dan membimbing."),
)
