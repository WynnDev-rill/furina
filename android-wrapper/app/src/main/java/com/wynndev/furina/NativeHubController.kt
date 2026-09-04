package com.wynndev.furina

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.ComponentName
import android.net.Uri
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject

class NativeHubController(context: Context) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val prefs = appContext.getSharedPreferences("furinahub_native", Context.MODE_PRIVATE)
    private val bridge = TermuxBridgeClient(appContext)
    private val store = MemoryStore(appContext)
    private val downloads = ModelDownloadManager(appContext)
    private val contextEngine = ContextEngine(appContext, store)
    private val runtime = AiRuntimeController(appContext)
    private val _state = MutableStateFlow(initialState())
    private val localProvider = LocalLlamaProvider(appContext, downloads) { status, _, _ ->
        _state.update { it.copy(status = status.replace('_', ' ').replaceFirstChar { char -> char.uppercase() }, error = null) }
        refreshAndroidModels()
    }
    private val providers: Map<String, AiProvider> = buildMap {
        put(localProvider.id, localProvider)
        putAll(runtime.onlineProviders)
    }
    private val aiEngine = UnifiedAiEngine(store, contextEngine, providers)
    private val aiMutex = Mutex()
    private var generationJob: Job? = null

    val state: StateFlow<HubUiState> = _state.asStateFlow()

    init {
        refresh()
    }

    private fun initialState(): HubUiState {
        val preference = runCatching {
            EnginePreference.valueOf(prefs.getString("engine_preference", EnginePreference.AUTO.name).orEmpty())
        }.getOrDefault(EnginePreference.AUTO)
        return HubUiState(
            termuxInstalled = bridge.isTermuxInstalled(),
            enginePreference = preference,
            assistantName = prefs.getString("assistant_name", "Furina") ?: "Furina",
            userNickname = prefs.getString("user_nickname", "").orEmpty(),
            selectedTraits = prefs.getStringSet("traits", emptySet()).orEmpty(),
            partnerMode = prefs.getBoolean("partner_mode", false),
            roleplayMode = prefs.getBoolean("roleplay_mode", false),
            fullLocalMemory = prefs.getBoolean("full_local_memory", false),
            trainingSuggestions = prefs.getBoolean("training_suggestions", false),
            innerThoughts = prefs.getBoolean("inner_thoughts", false),
            customInstructions = prefs.getString("custom_instructions", "").orEmpty(),
            androidAiMode = runtime.config.mode(),
            selectedProvider = runtime.config.selectedProvider(),
            chatAppearance = ChatAppearanceStore.load(appContext),
        )
    }

    fun selectWallpaperPreset(id: String) {
        runCatching { ChatAppearanceStore.selectPreset(appContext, id) }
            .onSuccess { appearance ->
                _state.update { it.copy(chatAppearance = appearance, error = null) }
            }
            .onFailure { error ->
                _state.update { it.copy(error = friendly(error)) }
            }
    }

    fun importChatWallpaper(uri: Uri, kind: ChatWallpaperKind) {
        if (_state.value.wallpaperBusy) return
        scope.launch {
            _state.update { it.copy(wallpaperBusy = true, error = null) }
            ChatAppearanceStore.import(appContext, uri, kind)
                .onSuccess { appearance ->
                    _state.update { it.copy(chatAppearance = appearance, wallpaperBusy = false, error = null) }
                }
                .onFailure { error ->
                    _state.update { it.copy(wallpaperBusy = false, error = friendly(error)) }
                }
        }
    }

    fun setWallpaperDim(amount: Float) {
        val appearance = ChatAppearanceStore.setDimAmount(appContext, amount)
        _state.update { it.copy(chatAppearance = appearance) }
    }

    fun setWallpaperMotion(enabled: Boolean) {
        val appearance = ChatAppearanceStore.setMotionEnabled(appContext, enabled)
        _state.update { it.copy(chatAppearance = appearance) }
    }

    fun resetChatWallpaper() {
        val appearance = ChatAppearanceStore.reset(appContext)
        _state.update { it.copy(chatAppearance = appearance, error = null) }
    }

    fun setDestination(destination: HubDestination) {
        _state.update { it.copy(destination = destination, error = null) }
        if (destination == HubDestination.MEMORY) refreshMemories()
    }

    fun canRunTermux(): Boolean = bridge.hasRunCommandPermission()

    fun refresh() {
        scope.launch {
            _state.update { it.copy(connectionState = "checking", connectionMessage = "Memeriksa Furina Core…") }
            val connected = runCatching { bridge.health() }.getOrNull()
            if (connected != null) {
                _state.update {
                    it.copy(
                        connected = true,
                        connectionState = "connected",
                        connectionMessage = "Furina Core terhubung",
                        coreVersion = connected.optString("version"),
                    )
                }
            } else {
                _state.update {
                    it.copy(
                        connected = false,
                        connectionState = "disconnected",
                        connectionMessage = if (it.termuxInstalled) "Core belum aktif" else "Termux belum terpasang",
                    )
                }
            }
            loadActiveSource()
            refreshAndroidModels()
            refreshProviders()
        }
    }

    fun connectTermux(activity: Activity) {
        if (_state.value.busy) return
        scope.launch {
            try {
                _state.update { it.copy(busy = true, connectionState = "connecting", connectionMessage = "Menyalakan Furina Core…", error = null) }
                val candidate = bridge.startCore(activity)
                val health = bridge.waitUntilHealthy(candidate)
                _state.update {
                    it.copy(
                        busy = false,
                        connected = true,
                        connectionState = "connected",
                        connectionMessage = "Core dan APK memakai memori yang sama",
                        coreVersion = health.optString("version"),
                    )
                }
                if (_state.value.enginePreference != EnginePreference.ANDROID) loadRemote()
            } catch (error: Throwable) {
                _state.update { it.copy(busy = false, connected = false, connectionState = "error", connectionMessage = "Koneksi gagal", error = friendly(error)) }
            }
        }
    }

    fun disconnectTermux() {
        bridge.forget()
        _state.update { it.copy(connected = false, connectionState = "disconnected", connectionMessage = "Sesi Core dilepas") }
        loadLocal()
    }

    fun setEnginePreference(preference: EnginePreference) {
        prefs.edit().putString("engine_preference", preference.name).apply()
        _state.update { it.copy(enginePreference = preference, error = null) }
        loadActiveSource()
    }

    private fun usesTermux(): Boolean = when (_state.value.enginePreference) {
        EnginePreference.AUTO -> _state.value.connected
        EnginePreference.TERMUX -> true
        EnginePreference.ANDROID -> false
    }

    private fun loadActiveSource() {
        if (usesTermux() && _state.value.connected) loadRemote() else loadLocal()
    }

    private fun loadRemote() {
        scope.launch {
            try {
                val boot = bridge.get("/api/bootstrap")
                applyRemoteBootstrap(boot)
                refreshMemories()
            } catch (error: Throwable) {
                onBridgeFailure(error)
            }
        }
    }

    private fun applyRemoteBootstrap(boot: JSONObject) {
        val settings = boot.optJSONObject("settings") ?: JSONObject()
        _state.update { current ->
            current.copy(
                activeSource = "Termux Core",
                coreVersion = boot.optString("core_version", current.coreVersion),
                assistantName = boot.optString("assistant_name", settings.optString("assistant_name", current.assistantName)),
                userNickname = boot.optString("user_nickname", settings.optString("user_nickname", current.userNickname)),
                selectedTraits = settings.optJSONArray("personality_traits").stringSet(),
                partnerMode = settings.optBoolean("partner_mode"),
                roleplayMode = settings.optBoolean("roleplay_mode"),
                fullLocalMemory = settings.optBoolean("full_local_memory"),
                trainingSuggestions = settings.optBoolean("training_suggestions"),
                innerThoughts = settings.optBoolean("inner_thoughts"),
                customInstructions = settings.optString("custom_instructions"),
                activeConversationId = boot.opt("active_conversation_id")?.toString().orEmpty(),
                messages = boot.optJSONArray("history").messages(),
                conversations = boot.optJSONArray("conversations").conversations(),
                status = "Core ${boot.optString("core_version", "aktif")}",
                error = null,
            )
        }
    }

    private fun loadLocal() {
        scope.launch(Dispatchers.IO) {
            try {
                var sessionId = prefs.getString("local_session", "").orEmpty()
                if (sessionId.isBlank()) {
                    sessionId = store.createSession()
                    prefs.edit().putString("local_session", sessionId).apply()
                } else store.ensureSession(sessionId)
                val messages = JSONArray(store.loadSessionJson(sessionId)).messages()
                val conversations = JSONArray(store.sessionsJson()).conversations()
                _state.update {
                    it.copy(
                        activeSource = "Android ${if (runtime.config.mode() == OnlineAiConfigStore.MODE_ONLINE) "Online" else "Lokal"}",
                        activeConversationId = sessionId,
                        messages = messages,
                        conversations = conversations,
                        androidAiMode = runtime.config.mode(),
                        error = null,
                    )
                }
                refreshMemories()
            } catch (error: Throwable) {
                _state.update { it.copy(error = friendly(error)) }
            }
        }
    }

    fun newConversation() {
        if (_state.value.busy) return
        scope.launch {
            try {
                if (usesTermux() && _state.value.connected) {
                    applyRemoteBootstrap(bridge.post("/api/conversations", JSONObject().put("action", "create")))
                } else {
                    val id = store.createSession()
                    prefs.edit().putString("local_session", id).apply()
                    loadLocal()
                }
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun switchConversation(id: String) {
        if (_state.value.busy || id == _state.value.activeConversationId) return
        scope.launch {
            try {
                if (usesTermux() && _state.value.connected) {
                    applyRemoteBootstrap(bridge.post("/api/conversations", JSONObject().put("action", "switch").put("id", id.toInt())))
                } else {
                    store.ensureSession(id)
                    prefs.edit().putString("local_session", id).apply()
                    loadLocal()
                }
                _state.update { it.copy(destination = HubDestination.CHAT) }
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun deleteConversation(id: String) {
        scope.launch {
            try {
                if (usesTermux() && _state.value.connected) {
                    applyRemoteBootstrap(bridge.post("/api/conversations", JSONObject().put("action", "delete").put("id", id.toInt())))
                } else {
                    store.deleteSession(id)
                    if (id == _state.value.activeConversationId) prefs.edit().remove("local_session").apply()
                    loadLocal()
                }
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun send(text: String) {
        val clean = text.trim()
        if (clean.isBlank() || _state.value.busy) return
        if (_state.value.enginePreference == EnginePreference.TERMUX && !_state.value.connected) {
            _state.update { it.copy(error = "Hubungkan Termux terlebih dahulu, atau pilih mode Otomatis/Android.") }
            return
        }
        generationJob = scope.launch {
            val requestId = "hub-${UUID.randomUUID()}"
            val user = HubMessage("user-$requestId", "user", clean)
            val pending = HubMessage("assistant-$requestId", "assistant", "", pending = true)
            _state.update { it.copy(busy = true, status = "Menyiapkan jawaban…", error = null, messages = it.messages + user + pending) }
            try {
                if (usesTermux() && _state.value.connected) sendRemote(clean, requestId, pending.id)
                else sendAndroid(clean, requestId, pending.id)
            } catch (cancelled: CancellationException) {
                _state.update { it.copy(busy = false, status = "Dihentikan", messages = it.messages.filterNot { row -> row.id == pending.id && row.content.isBlank() }) }
                throw cancelled
            } catch (error: Throwable) {
                _state.update { current ->
                    current.copy(
                        busy = false,
                        status = "Gagal",
                        error = friendly(error),
                        messages = current.messages.map { row -> if (row.id == pending.id) row.copy(content = "Jawaban gagal dibuat.", pending = false) else row },
                    )
                }
            }
        }
    }

    private suspend fun sendRemote(text: String, requestId: String, pendingId: String) {
        val accepted = bridge.post("/api/chat/start", JSONObject().put("message", text).put("request_id", requestId))
        val id = accepted.optString("request_id", requestId)
        while (true) {
            delay(110L)
            val progress = bridge.get("/api/chat/progress/$id")
            val partial = progress.optString("partial")
            _state.update { current ->
                current.copy(
                    status = progress.optString("label", "Menjawab…"),
                    messages = current.messages.map { row -> if (row.id == pendingId) row.copy(content = partial, pending = !progress.optBoolean("done")) else row },
                )
            }
            if (progress.optBoolean("done")) {
                if (progress.optBoolean("cancelled")) throw CancellationException("Dihentikan")
                val error = progress.optString("error")
                if (error.isNotBlank()) throw IllegalStateException(error)
                _state.update { it.copy(busy = false, status = "Siap") }
                loadRemote()
                return
            }
        }
    }

    private suspend fun sendAndroid(text: String, requestId: String, pendingId: String) {
        aiMutex.withLock {
            val selected = selectedModel()
            if (runtime.config.mode() != OnlineAiConfigStore.MODE_ONLINE) {
                check(downloads.status(selected).optString("state") == "ready") { "Unduh ${selected.displayName} dahulu di Pengaturan." }
            }
            val (providerId, model) = runtime.resolve(selected)
            val persona = personaPrompt(_state.value)
            val session = _state.value.activeConversationId.ifBlank { store.createSession() }
            aiEngine.generate(requestId, providerId, model, session, text, _state.value.assistantName, persona) { token ->
                _state.update { current ->
                    current.copy(
                        status = "Menjawab…",
                        messages = current.messages.map { row -> if (row.id == pendingId) row.copy(content = row.content + token) else row },
                    )
                }
            }
        }
        _state.update { it.copy(busy = false, status = "Siap") }
        loadLocal()
    }

    fun stopGeneration() {
        val active = generationJob ?: return
        if (usesTermux() && _state.value.connected) {
            val request = _state.value.messages.lastOrNull { it.pending }?.id?.removePrefix("assistant-")
            if (!request.isNullOrBlank()) scope.launch { runCatching { bridge.post("/api/chat/cancel", JSONObject().put("request_id", request)) } }
        }
        active.cancel()
        generationJob = null
    }

    fun saveIdentity(name: String, nickname: String, instructions: String) {
        val cleanName = name.trim().take(48).ifBlank { "Furina" }
        val cleanNickname = nickname.trim().take(48)
        val cleanInstructions = instructions.trim().take(2_000)
        prefs.edit().putString("assistant_name", cleanName).putString("user_nickname", cleanNickname).putString("custom_instructions", cleanInstructions).apply()
        _state.update { it.copy(assistantName = cleanName, userNickname = cleanNickname, customInstructions = cleanInstructions, status = "Personalisasi disimpan") }
        syncPersona()
    }

    fun toggleTrait(id: String) {
        val next = _state.value.selectedTraits.toMutableSet().apply { if (!add(id)) remove(id) }.toSet()
        prefs.edit().putStringSet("traits", next).apply()
        _state.update { it.copy(selectedTraits = next) }
        syncPersona()
    }

    fun setAdvanced(key: String, enabled: Boolean) {
        when (key) {
            "partner_mode" -> _state.update { it.copy(partnerMode = enabled) }
            "roleplay_mode" -> _state.update { it.copy(roleplayMode = enabled) }
            "full_local_memory" -> _state.update { it.copy(fullLocalMemory = enabled) }
            "training_suggestions" -> _state.update { it.copy(trainingSuggestions = enabled) }
            "inner_thoughts" -> _state.update { it.copy(innerThoughts = enabled) }
            else -> return
        }
        prefs.edit().putBoolean(key, enabled).apply()
        syncPersona()
    }

    private fun syncPersona() {
        if (!_state.value.connected) return
        scope.launch {
            try {
                val current = _state.value
                val hub = JSONObject()
                    .put("assistant_name", current.assistantName)
                    .put("user_nickname", current.userNickname)
                    .put("personality_traits", JSONArray(current.selectedTraits.toList()))
                    .put("partner_mode", current.partnerMode)
                    .put("roleplay_mode", current.roleplayMode)
                    .put("full_local_memory", current.fullLocalMemory)
                    .put("training_suggestions", current.trainingSuggestions)
                    .put("inner_thoughts", current.innerThoughts)
                    .put("custom_instructions", current.customInstructions)
                bridge.post("/api/settings", JSONObject().put("hub", hub).put("core", JSONObject().put("persona_name", current.assistantName).put("user_nickname", current.userNickname)))
                _state.update { it.copy(status = "Tersinkron ke Termux", error = null) }
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun refreshMemories() {
        scope.launch(Dispatchers.IO) {
            try {
                val rows = if (usesTermux() && _state.value.connected) {
                    bridge.get("/api/memory").optJSONArray("memories").memories()
                } else JSONArray(store.memoriesJson()).memories()
                _state.update { it.copy(memories = rows, error = null) }
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun addMemory(text: String) {
        val clean = text.trim()
        if (clean.isBlank()) return
        scope.launch(Dispatchers.IO) {
            try {
                if (usesTermux() && _state.value.connected) bridge.post("/api/memory", JSONObject().put("action", "add").put("text", clean))
                else store.addMemory(clean)
                refreshMemories()
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun deleteMemory(id: String) {
        scope.launch(Dispatchers.IO) {
            try {
                if (usesTermux() && _state.value.connected) bridge.post("/api/memory", JSONObject().put("action", "delete").put("id", id.toInt()))
                else store.deleteMemory(id)
                refreshMemories()
            } catch (error: Throwable) { showError(error) }
        }
    }

    fun setAndroidAiMode(mode: String) {
        runtime.setMode(mode)
        _state.update { it.copy(androidAiMode = runtime.config.mode()) }
        scope.launch { aiMutex.withLock { aiEngine.unload() } }
        loadActiveSource()
    }

    fun selectProvider(id: String) {
        runtime.setProvider(id)
        refreshProviders()
    }

    fun saveAndTestProvider(id: String, key: String) {
        scope.launch {
            try {
                if (key.isNotBlank()) runtime.saveKey(id, key)
                _state.update { it.copy(busy = true, status = "Menguji ${OnlineProviderCatalog.byId(id)?.displayName ?: id}…", error = null) }
                val result = runtime.test(id)
                _state.update { it.copy(busy = false, status = result.message, error = if (result.success) null else result.message) }
                refreshProviders()
            } catch (error: Throwable) { _state.update { it.copy(busy = false, error = friendly(error)) } }
        }
    }

    fun selectAndroidModel(id: String) {
        require(ModelCatalog.byId(id) != null)
        prefs.edit().putString("selected_model", id).apply()
        refreshAndroidModels()
    }

    fun downloadAndroidModel(id: String) {
        val model = ModelCatalog.byId(id) ?: return
        downloads.start(model)
        scope.launch {
            repeat(7_200) {
                refreshAndroidModels()
                val status = downloads.status(model).optString("state")
                if (status in setOf("ready", "failed", "cancelled")) return@launch
                delay(1_000L)
            }
        }
    }

    fun deleteAndroidModel(id: String) {
        ModelCatalog.byId(id)?.let(downloads::delete)
        refreshAndroidModels()
    }

    private fun selectedModel(): ModelSpec {
        val fallback = ModelCatalog.models.first()
        return ModelCatalog.byId(prefs.getString("selected_model", fallback.id)) ?: fallback
    }

    private fun refreshAndroidModels() {
        val selected = selectedModel().id
        val rows = ModelCatalog.models.map { model ->
            val status = downloads.status(model)
            AndroidModelState(
                id = model.id,
                name = model.displayName,
                subtitle = model.subtitle,
                state = status.optString("state", "missing"),
                progress = status.optDouble("progress", 0.0).toFloat().coerceIn(0f, 1f),
                selected = selected == model.id,
            )
        }
        _state.update { it.copy(androidModels = rows) }
    }

    private fun refreshProviders() {
        val selected = runtime.config.selectedProvider()
        _state.update { current ->
            current.copy(
                selectedProvider = selected,
                providers = OnlineProviderCatalog.providers.map {
                    ProviderState(it.id, it.displayName, runtime.keys.has(it.id), it.id == selected)
                },
            )
        }
    }

    fun openTrainingRoom(activity: Activity) {
        try {
            check(bridge.isTermuxInstalled()) { "Termux belum terpasang" }
            check(bridge.hasRunCommandPermission()) { "Izin RUN_COMMAND Termux diperlukan" }
            val intent = Intent("com.termux.RUN_COMMAND").apply {
                component = ComponentName("com.termux", "com.termux.app.RunCommandService")
                putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/furina")
                putExtra("com.termux.RUN_COMMAND_ARGUMENTS", emptyArray<String>())
                putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home")
                putExtra("com.termux.RUN_COMMAND_BACKGROUND", false)
                putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0")
            }
            activity.startService(intent)
        } catch (error: Throwable) { showError(error) }
    }

    fun clearError() = _state.update { it.copy(error = null) }

    fun permissionDenied() = _state.update {
        it.copy(error = "Izin ‘Run commands in Termux environment’ diperlukan untuk menyalakan Core dari FurinaHub.")
    }

    private fun personaPrompt(state: HubUiState): String {
        val traits = FurinaTraits.filter { it.id in state.selectedTraits }.joinToString { "${it.label}: ${it.description}" }
        return buildString {
            append("Kamu adalah ${state.assistantName}, companion pribadi yang berbicara natural dalam bahasa pengguna. ")
            if (traits.isNotBlank()) append("Kepribadian aktif menyatu sebagai satu watak: $traits. ")
            append(if (state.partnerMode) "Mode pasangan romantis aktif dengan batas sehat. " else "Hubungan companion non-romantis kecuali konteks berkembang secara eksplisit. ")
            if (state.roleplayMode) append("Roleplay fiksional boleh diikuti saat diminta. ")
            if (state.innerThoughts) append("Boleh tampilkan satu suara batin fiksional singkat bila cocok, bukan reasoning model. ")
            if (state.userNickname.isNotBlank()) append("Nama panggilan user: ${state.userNickname}. ")
            if (state.customInstructions.isNotBlank()) append(state.customInstructions)
        }
    }

    private fun onBridgeFailure(error: Throwable) {
        if (error is CoreBridgeException && error.status in setOf(401, 403)) bridge.forget()
        _state.update { it.copy(connected = false, connectionState = "disconnected", connectionMessage = "Core terputus", error = friendly(error)) }
        if (_state.value.enginePreference == EnginePreference.AUTO) loadLocal()
    }

    private fun showError(error: Throwable) = _state.update { it.copy(error = friendly(error)) }

    private fun friendly(error: Throwable): String {
        val raw = error.message.orEmpty()
        return when {
            raw.contains("permission", true) || raw.contains("izin", true) -> "Izinkan ‘Run commands in Termux environment’ pada info aplikasi FurinaHub."
            raw.contains("Connection refused", true) -> "Furina Core belum aktif. Tekan Hubungkan Termux."
            raw.isNotBlank() -> raw.take(500)
            else -> "Terjadi kesalahan yang tidak diketahui."
        }
    }

    fun close() {
        generationJob?.cancel()
        aiEngine.destroy()
        scope.cancel()
        store.close()
    }
}

private fun JSONArray?.stringSet(): Set<String> = buildSet {
    val array = this@stringSet ?: return@buildSet
    for (index in 0 until array.length()) array.optString(index).takeIf(String::isNotBlank)?.let(::add)
}

private fun JSONArray?.messages(): List<HubMessage> {
    val array = this ?: return emptyList()
    return buildList {
        for (index in 0 until array.length()) {
            val row = array.optJSONObject(index) ?: continue
            add(HubMessage(row.opt("id")?.toString() ?: "message-$index", row.optString("role", "assistant"), row.optString("content", row.optString("text"))))
        }
    }
}

private fun JSONArray?.conversations(): List<HubConversation> {
    val array = this ?: return emptyList()
    return buildList {
        for (index in 0 until array.length()) {
            val row = array.optJSONObject(index) ?: continue
            val id = row.opt("id")?.toString() ?: continue
            add(
                HubConversation(
                    id = id,
                    title = row.optString("title", "Percakapan baru"),
                    messageCount = row.optInt("messageCount", row.optInt("message_count")),
                    pinned = row.optBoolean("pinned"),
                ),
            )
        }
    }
}

private fun JSONArray?.memories(): List<HubMemory> {
    val array = this ?: return emptyList()
    return buildList {
        for (index in 0 until array.length()) {
            val row = array.optJSONObject(index) ?: continue
            val id = row.opt("id")?.toString() ?: continue
            add(HubMemory(id, row.optString("text", row.optString("content")), row.optString("kind", "memory")))
        }
    }
}
