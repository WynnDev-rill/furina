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
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.json.JSONObject

/** UI orchestration only. HubDataRepository owns persistence and source-specific identifiers. */
class NativeHubController(context: Context) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val prefs = appContext.getSharedPreferences("furinahub_native", Context.MODE_PRIVATE)
    private val bridge = TermuxBridgeClient(appContext)
    private val store = MemoryStore(appContext)
    private val repository = HubDataRepository(appContext, store, bridge)
    private val backups = BackupManager(appContext, store)
    private val contextEngine = ContextEngine(appContext, store)
    private val runtime = AiRuntimeController(appContext)
    private val downloads = ModelDownloadManager(appContext)
    private val _state = MutableStateFlow(initialState())
    private val localProvider = LocalLlamaProvider(appContext, downloads) { status, _, _ -> _state.update { it.copy(status = status.replace('_', ' ')) } }
    private val aiEngine = UnifiedAiEngine(store, contextEngine, buildMap { put(localProvider.id, localProvider); putAll(runtime.onlineProviders) })
    private var generationJob: Job? = null
    private var operationJob: Job? = null
    private var draftJob: Job? = null
    private val downloadJobs = mutableMapOf<String, Job>()
    private var activeRequestId: String? = null
    private var activeRequestSource: HubSource? = null
    private var messageLimit = 200
    val state: StateFlow<HubUiState> = _state.asStateFlow()

    init { refresh() }

    private fun initialState(): HubUiState = repository.persona().applyTo(HubUiState(
        termuxInstalled = bridge.isTermuxInstalled(),
        enginePreference = runCatching { EnginePreference.valueOf(prefs.getString("engine_preference", "AUTO").orEmpty()) }.getOrDefault(EnginePreference.AUTO),
        androidAiMode = runtime.config.mode(), selectedProvider = runtime.config.selectedProvider(),
        autoFallback = runtime.config.autoFallback(), chatAppearance = ChatAppearanceStore.load(appContext), personaPending = repository.personaPending(),
    ))

    /** Synchronous admission on Main prevents competing session mutations from rapid taps. */
    private fun operation(label: String, block: suspend () -> Unit): Boolean {
        if (_state.value.busy || operationJob?.isActive == true) return false
        _state.update { it.copy(busy = true, status = label, error = null) }
        operationJob = scope.launch {
            try { block() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { showError(e) }
            finally { _state.update { it.copy(busy = false, loading = false) } }
        }
        return true
    }

    private fun desiredSource(): HubSource = if (_state.value.enginePreference != EnginePreference.ANDROID && _state.value.connected) HubSource.TERMUX else HubSource.ANDROID
    private suspend fun apply(snapshot: HubSnapshot) {
        val draft = repository.draft(snapshot.source, snapshot.id)
        _state.update { old -> snapshot.persona.applyTo(old).copy(
            source = snapshot.source, activeConversationId = snapshot.id, messages = snapshot.messages, conversations = snapshot.conversations,
            activeSource = if (snapshot.source == HubSource.TERMUX) "Termux Core" else "Android ${if (runtime.config.mode() == OnlineAiConfigStore.MODE_ONLINE) "Online" else "Lokal"}",
            coreVersion = snapshot.coreVersion.ifBlank { old.coreVersion }, historyLimited = snapshot.historyLimited,
            draft = draft, loading = false, personaPending = repository.personaPending(),
        ) }
    }
    private suspend fun saveDraftNow() {
        draftJob?.cancelAndJoin()
        val current = _state.value
        repository.saveDraft(current.source, current.activeConversationId, current.draft)
    }
    fun setDraft(value: String) {
        _state.update { it.copy(draft = value.take(12_000)) }
        val current = _state.value
        draftJob?.cancel()
        draftJob = scope.launch { delay(250); repository.saveDraft(current.source, current.activeConversationId, current.draft) }
    }

    fun refresh() { operation("Memeriksa koneksi…") {
        saveDraftNow()
        _state.update { it.copy(connectionState = "checking", termuxInstalled = bridge.isTermuxInstalled()) }
        val health = try { bridge.health() } catch (e: CancellationException) { throw e } catch (_: Exception) { null }
        _state.update { it.copy(connected = health != null, connectionState = if (health != null) "connected" else "disconnected",
            connectionMessage = if (health != null) "Furina Core terhubung" else if (it.termuxInstalled) "Core belum aktif" else "Termux belum terpasang",
            coreVersion = health?.optString("version").orEmpty()) }
        loadSource(); refreshAndroidModels(); refreshProviders()
    } }
    private suspend fun loadSource() {
        val target = desiredSource()
        try {
            apply(repository.snapshot(target, messageLimit)); refreshMemoriesNow()
            if (target == HubSource.TERMUX) loadCoreSettings()
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) {
            if (target != HubSource.TERMUX) throw e
            _state.update { it.copy(connected = false, connectionState = "error", connectionMessage = "Core tidak dapat dibaca") }
            if (_state.value.enginePreference == EnginePreference.AUTO) {
                apply(repository.snapshot(HubSource.ANDROID, messageLimit)); refreshMemoriesNow()
                _state.update { it.copy(notice = "Core terputus. Sumber berpindah ke Android; riwayat Termux tetap tersimpan di Core.") }
            } else throw e
        }
    }
    fun setDestination(destination: HubDestination) {
        _state.update { it.copy(destination = destination) }
        if (destination == HubDestination.MEMORY && !_state.value.busy) refreshMemories()
    }
    fun canRunTermux(): Boolean = bridge.hasRunCommandPermission()
    fun connectTermux(activity: Activity) { operation("Menyalakan Furina Core…") {
        saveDraftNow(); _state.update { it.copy(connectionState = "connecting", connected = false) }
        try {
            val health = bridge.waitUntilHealthy(bridge.startCore(activity))
            _state.update { it.copy(connected = true, connectionState = "connected", coreVersion = health.optString("version"), connectionMessage = "Core terhubung") }
            loadSource()
        } catch (e: CancellationException) { throw e }
        catch (e: Exception) { _state.update { it.copy(connected = false, connectionState = "error", connectionMessage = "Koneksi gagal") }; throw e }
    } }
    fun disconnectTermux() { operation("Melepas koneksi…") {
        saveDraftNow(); bridge.forget()
        _state.update { it.copy(connected = false, connectionState = "disconnected", connectionMessage = "Sesi Core dilepas") }; loadSource()
    } }
    fun setEnginePreference(preference: EnginePreference) { operation("Mengganti sumber…") {
        saveDraftNow(); prefs.edit().putString("engine_preference", preference.name).apply()
        _state.update { it.copy(enginePreference = preference) }; messageLimit = 200; loadSource()
    } }

    private fun conversation(action: String, id: String = "", title: String = "", pinned: Boolean = false) { operation("Memperbarui percakapan…") {
        saveDraftNow(); val current = _state.value
        check(current.source != HubSource.TERMUX || current.connected) { "Hubungkan Core untuk mengubah percakapan Termux" }
        apply(repository.conversation(current.source, action, id, title, pinned)); _state.update { it.copy(destination = HubDestination.CHAT) }
    } }
    fun newConversation() = conversation("create")
    fun switchConversation(id: String) = conversation("switch", id)
    fun deleteConversation(id: String) = conversation("delete", id)
    fun renameConversation(id: String, title: String) = conversation("rename", id, title)
    fun pinConversation(id: String, pinned: Boolean) = conversation("pin", id, pinned = pinned)
    fun loadOlderMessages() { operation("Memuat riwayat…") {
        saveDraftNow()
        check(_state.value.source == HubSource.ANDROID) { "Core menyediakan jendela riwayat terbaru. Arsip lengkap tetap ada di Termux." }
        messageLimit += 200; apply(repository.snapshot(HubSource.ANDROID, messageLimit))
    } }
    fun editInBranch(message: HubMessage) { operation("Membuat cabang aman…") {
        check(_state.value.source == HubSource.ANDROID) { "Cabang non-destruktif belum didukung API Core ini" }
        saveDraftNow(); apply(repository.branchBefore(_state.value.activeConversationId, message.id)); setDraft(message.content)
        _state.update { it.copy(notice = "Cabang baru dibuat. Percakapan asli tetap utuh.") }
    } }

    /** False leaves the draft intact. Accepted sends capture their source/session until finally. */
    fun send(text: String): Boolean {
        val clean = text.trim(); val current = _state.value
        if (clean.isBlank() || current.busy || current.loading || current.activeConversationId.isBlank()) return false
        if (current.enginePreference == EnginePreference.TERMUX && !current.connected) {
            showError(IllegalStateException("Hubungkan Termux terlebih dahulu, atau pilih Android.")); return false
        }
        if (current.source == HubSource.ANDROID) {
            if (runtime.config.mode() == OnlineAiConfigStore.MODE_LOCAL && downloads.status(selectedModel()).optString("state") != "ready") {
                showError(IllegalStateException("Unduh model lokal di Setelan atau pilih provider online.")); return false
            }
            if (runtime.config.mode() == OnlineAiConfigStore.MODE_ONLINE && !runtime.config.isValidated(runtime.config.selectedProvider(), runtime.keys.fingerprint(runtime.config.selectedProvider()))) {
                showError(IllegalStateException("Atur dan tes API key di Setelan terlebih dahulu.")); return false
            }
        }
        val source = current.source; val session = current.activeConversationId
        val request = "hub-${UUID.randomUUID()}"; val pending = "assistant-$request"
        activeRequestSource = source; activeRequestId = request
        _state.update { it.copy(busy = true, generating = true, draft = "", error = null, status = "Menyiapkan jawaban…",
            messages = it.messages + HubMessage("user-$request", "user", clean) + HubMessage(pending, "assistant", "", true)) }
        generationJob = scope.launch {
            var status = "Siap"
            try {
                draftJob?.cancelAndJoin(); repository.saveDraft(source, session, "")
                if (source == HubSource.TERMUX) sendRemote(clean, request, pending)
                else {
                    val (providerId, model) = runtime.resolve(selectedModel())
                    val persona = withContext(Dispatchers.IO) { repository.persona() }
                    val result = withContext(Dispatchers.IO) {
                        aiEngine.generate(request, providerId, model, session, clean, persona.name, personaPrompt(persona)) { token ->
                            updatePending(pending) { it.copy(content = it.content + token) }
                        }
                    }
                    _state.update { it.copy(activeModel = result.metrics.optString("model", model.displayName)) }
                }
            } catch (e: TimeoutCancellationException) { status = "Gagal"; showError(IllegalStateException("Core melewati batas waktu jawaban. Periksa koneksi sebelum mencoba lagi.")) }
            catch (e: CancellationException) { status = "Dihentikan" }
            catch (e: Exception) { status = "Gagal"; showError(e) }
            finally {
                withContext(NonCancellable) {
                    if (source == HubSource.TERMUX && status != "Siap") {
                        try { bridge.post("/api/chat/cancel", JSONObject().put("request_id", activeRequestId ?: request)) } catch (_: Exception) { }
                    }
                    // The user may already be typing the next turn. Flush it before reloading.
                    saveDraftNow()
                    try { apply(repository.snapshot(source, messageLimit)); refreshMemoriesNow() }
                    catch (_: Exception) { _state.update { it.copy(messages = it.messages.filterNot { row -> row.id == pending && row.content.isBlank() }.map { row -> row.copy(pending = false) }) } }
                    if (status == "Gagal" && _state.value.draft.isBlank() && _state.value.activeConversationId == session) {
                        _state.update { it.copy(draft = clean) }; repository.saveDraft(source, session, clean)
                    }
                    _state.update { it.copy(busy = false, generating = false, status = status) }
                    activeRequestId = null; activeRequestSource = null
                }
            }
        }
        return true
    }
    private fun updatePending(id: String, change: (HubMessage) -> HubMessage) {
        _state.update { it.copy(status = "Menjawab…", messages = it.messages.map { row -> if (row.id == id) change(row) else row }) }
    }
    private suspend fun sendRemote(text: String, request: String, pending: String) = withTimeout(300_000L) {
        val accepted = bridge.post("/api/chat/start", JSONObject().put("message", text).put("request_id", request))
        check(accepted.optBoolean("accepted")) { "Core tidak menerima pesan" }
        val id = accepted.optString("request_id", request)
        require(Regex("[a-zA-Z0-9_-]{1,80}").matches(id)) { "ID respons Core tidak valid" }; activeRequestId = id
        while (true) {
            delay(160L); val progress = bridge.get("/api/chat/progress/$id")
            val partial = progress.optString("partial").ifBlank { progress.optJSONObject("result")?.optString("answer").orEmpty() }
            updatePending(pending) { it.copy(content = partial, pending = !progress.optBoolean("done")) }
            if (progress.optBoolean("done")) {
                if (progress.optBoolean("cancelled")) throw CancellationException("Dihentikan")
                check(progress.optString("error").isBlank()) { progress.optString("error") }
                check(partial.isNotBlank()) { "Core tidak menghasilkan jawaban akhir" }; break
            }
        }
    }
    fun stopGeneration() {
        val request = activeRequestId ?: return; val source = activeRequestSource
        _state.update { it.copy(status = "Menghentikan…") }
        scope.launch {
            if (source == HubSource.TERMUX) try { bridge.post("/api/chat/cancel", JSONObject().put("request_id", request)) } catch (e: Exception) { showError(e) }
            if (activeRequestId == request) generationJob?.cancel()
        }
    }

    private fun changePersona(change: (HubPersona) -> HubPersona) { operation("Menyimpan persona…") {
        val next = withContext(Dispatchers.IO) { change(repository.persona()).also { repository.savePersona(it, true) } }
        _state.update { next.applyTo(it).copy(personaPending = true) }
        if (_state.value.connected) { repository.syncPersona(); _state.update { it.copy(personaPending = false) } }
        _state.update { it.copy(notice = if (it.personaPending) "Persona disimpan di Android; sinkron saat Core terhubung." else "Persona disimpan dan tersinkron.") }
    } }
    fun saveIdentity(name: String, nickname: String, instructions: String) = changePersona {
        it.copy(name = name.trim().take(48).ifBlank { "Furina" }, nickname = nickname.trim().take(48), instructions = instructions.trim().take(2_000))
    }
    fun toggleTrait(id: String) = changePersona { p ->
        require(FurinaTraits.any { it.id == id }); p.copy(traits = p.traits.toMutableSet().apply { if (!add(id)) remove(id) }.toSet())
    }
    fun setAdvanced(key: String, enabled: Boolean) = changePersona {
        when (key) {
            "partner_mode" -> it.copy(partner = enabled)
            "roleplay_mode" -> it.copy(roleplay = enabled)
            "full_local_memory" -> it.copy(fullMemory = enabled)
            "training_suggestions" -> it.copy(training = enabled)
            "inner_thoughts" -> it.copy(innerThoughts = enabled)
            else -> error("Pengaturan tidak dikenal")
        }
    }
    private fun personaPrompt(p: HubPersona): String = buildString {
        append("Kamu adalah ${p.name}, companion pribadi. Gunakan bahasa Indonesia natural; ikuti bahasa pengguna bila berubah. ")
        append("Tidak memiliki latar atau cerita Genshin. Nama dan kepribadian bukan identitas provider AI. ")
        if (p.traits.isNotEmpty()) append("Satukan sifat sebagai satu watak kontekstual: ${FurinaTraits.filter { it.id in p.traits }.joinToString { "${it.label}: ${it.description}" }}. ")
        append(if (p.partner) "Mode pasangan aktif, romantis sesuai konteks dan batas sehat. " else "Mode pasangan nonaktif; jangan mengasumsikan hubungan romantis. ")
        append(if (p.roleplay) "Roleplay fiksional diizinkan saat diminta. " else "Roleplay nonaktif; jangan menambahkan narasi aksi atau adegan fiksional. ")
        append(if (p.innerThoughts) "Suara batin karakter boleh berupa kata-kata singkat bila relevan, bukan proses penalaran model. " else "Jangan tampilkan suara batin, tag think, atau proses penalaran model. ")
        if (p.nickname.isNotBlank()) append("Panggilan pengguna: ${p.nickname}; gunakan sewajarnya, tidak wajib setiap jawaban. ")
        append("Panjang jawaban adaptif: percakapan santai ringkas, pembahasan rumit cukup terperinci. "); append(p.instructions)
    }

    private suspend fun refreshMemoriesNow() { val rows = repository.memories(_state.value.source); _state.update { it.copy(memories = rows) } }
    fun refreshMemories() { operation("Memuat memori…") { refreshMemoriesNow() } }
    fun addMemory(text: String): Boolean {
        if (text.trim().length !in 4..500) { showError(IllegalArgumentException("Memori harus 4–500 karakter")); return false }
        return operation("Menyimpan memori…") { repository.changeMemory(_state.value.source, text = text); refreshMemoriesNow() }
    }
    fun deleteMemory(id: String) { operation("Menghapus memori…") { repository.changeMemory(_state.value.source, id = id); refreshMemoriesNow() } }

    fun setAndroidAiMode(mode: String) { operation("Mengganti mesin Android…") {
        saveDraftNow(); aiEngine.unload(); runtime.setMode(mode); _state.update { it.copy(androidAiMode = runtime.config.mode()) }; loadSource()
    } }
    fun selectProvider(id: String) { if (!_state.value.busy) { runtime.setProvider(id); refreshProviders() } }
    fun selectOnlineModel(provider: String, model: String) {
        if (!_state.value.busy) try { runtime.setModel(provider, model); refreshProviders() } catch (e: Exception) { showError(e) }
    }
    fun setAutoFallback(enabled: Boolean) { if (!_state.value.busy) { runtime.setAutoFallback(enabled); _state.update { it.copy(autoFallback = enabled) } } }
    fun removeProviderKey(id: String) { if (!_state.value.busy) { runtime.removeKey(id); refreshProviders() } }
    fun saveAndTestProvider(id: String, key: String) { operation("Menguji provider…") {
        _state.update { it.copy(providerBusy = true) }
        try {
            if (key.isNotBlank()) runtime.saveKey(id, key)
            val result = runtime.test(id); check(result.success) { result.message }; _state.update { it.copy(notice = result.message) }
        } finally { refreshProviders(); _state.update { it.copy(providerBusy = false) } }
    } }
    private fun refreshProviders() { _state.update { it.copy(selectedProvider = runtime.config.selectedProvider(), providers = OnlineProviderCatalog.providers.map { p ->
        ProviderState(p.id, p.displayName, runtime.keys.has(p.id), p.id == runtime.config.selectedProvider(),
            runtime.onlineProviders[p.id]?.cachedModels().orEmpty(), runtime.config.selectedModel(p.id).orEmpty())
    }) } }
    private suspend fun loadCoreSettings() {
        val root = bridge.get("/api/settings"); val core = root.optJSONObject("core") ?: JSONObject()
        val models = root.optJSONArray("models"); val providers = root.optJSONArray("providers")
        _state.update { it.copy(coreRoutingMode = core.optString("routing_mode", "local"),
            coreModels = (0 until (models?.length() ?: 0)).mapNotNull { i -> models?.optJSONObject(i)?.takeIf { row -> row.optString("category") == "chat" }?.let { row -> CoreModelState(row.optString("path"), row.optString("name"), row.optBoolean("active")) },
            coreProviders = (0 until (providers?.length() ?: 0)).mapNotNull { i -> providers?.optJSONObject(i)?.let { p -> ProviderState(p.optString("id"), p.optString("label"), p.optBoolean("configured"), false) } }) }
    }
    fun setCoreMode(mode: String, modelPath: String? = null) { operation("Mengatur Core…") {
        check(_state.value.connected); require(mode in setOf("local", "online"))
        val core = JSONObject().put("routing_mode", mode)
        if (modelPath != null) { require(_state.value.coreModels.any { it.path == modelPath }); core.put("model_path", modelPath) }
        bridge.post("/api/settings", JSONObject().put("core", core)); loadCoreSettings()
    } }
    fun testCoreProvider(id: String, key: String) { operation("Menguji provider Core…") {
        check(_state.value.connected); require(_state.value.coreProviders.any { it.id == id })
        if (key.isNotBlank()) bridge.post("/api/provider", JSONObject().put("provider", id).put("key", key))
        val result = bridge.post("/api/provider/test", JSONObject().put("provider", id))
        check(result.optBoolean("ok")) { result.optString("message", "Tes provider Core gagal") }
        loadCoreSettings(); _state.update { it.copy(notice = result.optString("message", "Provider Core siap")) }
    } }

    fun selectAndroidModel(id: String) { if (!_state.value.busy && ModelCatalog.byId(id) != null) { prefs.edit().putString("selected_model", id).apply(); refreshAndroidModels() } }
    private fun selectedModel(): ModelSpec = ModelCatalog.byId(prefs.getString("selected_model", ModelCatalog.models.first().id)) ?: ModelCatalog.models.first()
    private fun refreshAndroidModels() { _state.update { it.copy(androidModels = ModelCatalog.models.map { m ->
        val s = downloads.status(m)
        AndroidModelState(m.id, m.displayName, m.subtitle, s.optString("state", "missing"), s.optDouble("progress", 0.0).toFloat().coerceIn(0f, 1f), m.id == selectedModel().id)
    }) } }
    fun downloadAndroidModel(id: String) {
        val model = ModelCatalog.byId(id) ?: return; downloads.start(model); downloadJobs.remove(id)?.cancel()
        downloadJobs[id] = scope.launch { repeat(7_200) { refreshAndroidModels(); if (downloads.status(model).optString("state") in setOf("ready", "failed", "cancelled")) return@launch; delay(1_000) } }
    }
    fun deleteAndroidModel(id: String) { operation("Melepas model…") { aiEngine.unload(); ModelCatalog.byId(id)?.let(downloads::delete); refreshAndroidModels() } }

    fun selectWallpaperPreset(id: String) {
        if (!_state.value.wallpaperBusy) try { val next = ChatAppearanceStore.selectPreset(appContext, id); _state.update { it.copy(chatAppearance = next) } } catch (e: Exception) { showError(e) }
    }
    fun importChatWallpaper(uri: Uri, kind: ChatWallpaperKind) {
        if (_state.value.wallpaperBusy) return; _state.update { it.copy(wallpaperBusy = true) }
        scope.launch {
            try { val appearance = ChatAppearanceStore.import(appContext, uri, kind).getOrThrow(); _state.update { it.copy(chatAppearance = appearance) } }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { showError(e) }
            finally { _state.update { it.copy(wallpaperBusy = false) } }
        }
    }
    fun setWallpaperDim(amount: Float) { if (!_state.value.wallpaperBusy) { val next = ChatAppearanceStore.setDimAmount(appContext, amount); _state.update { it.copy(chatAppearance = next) } } }
    fun setWallpaperMotion(enabled: Boolean) { if (!_state.value.wallpaperBusy) { val next = ChatAppearanceStore.setMotionEnabled(appContext, enabled); _state.update { it.copy(chatAppearance = next) } } }
    fun resetChatWallpaper() { if (!_state.value.wallpaperBusy) { val next = ChatAppearanceStore.reset(appContext); _state.update { it.copy(chatAppearance = next) } } }

    fun exportConversation(uri: Uri) { operation("Mengekspor percakapan…") {
        val current = _state.value; val text = repository.exportConversation(current.source, current.activeConversationId)
        withContext(Dispatchers.IO) { appContext.contentResolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(text) } ?: error("Berkas tidak dapat ditulis") }
        _state.update { it.copy(notice = "Percakapan diekspor. Berkas berisi teks pribadi tanpa enkripsi.") }
    } }
    fun recoveryKey(): String = backups.getOrCreateRecoveryKey()
    fun exportBackup(uri: Uri) { operation("Mencadangkan data Android…") {
        saveDraftNow()
        withContext(Dispatchers.IO) {
            val bytes = backups.createEncryptedSnapshotBytes(64L * 1024 * 1024)
            appContext.contentResolver.openOutputStream(uri)?.use { it.write(bytes) } ?: error("Berkas tidak dapat ditulis")
        }
        _state.update { it.copy(notice = "Backup Android terenkripsi dibuat. Simpan kunci pemulihan terpisah. Data Core dan media wallpaper tidak disertakan.") }
    } }
    fun restoreBackup(uri: Uri, key: String) { operation("Memulihkan data Android…") {
        saveDraftNow(); aiEngine.unload()
        withContext(Dispatchers.IO) { backups.restoreFrom(uri, key) }
        _state.update { it.copy(enginePreference = EnginePreference.ANDROID) }; prefs.edit().putString("engine_preference", "ANDROID").apply()
        apply(repository.snapshot(HubSource.ANDROID)); refreshMemoriesNow(); _state.update { it.copy(notice = "Backup Android dipulihkan. API key tidak diimpor.") }
    } }
    fun openTrainingRoom(activity: Activity) {
        try {
            check(bridge.isTermuxInstalled()) { "Termux belum terpasang" }; check(bridge.hasRunCommandPermission()) { "Izin RUN_COMMAND Termux diperlukan" }
            val intent = Intent("com.termux.RUN_COMMAND").apply {
                component = ComponentName("com.termux", "com.termux.app.RunCommandService")
                putExtra("com.termux.RUN_COMMAND_PATH", "/data/data/com.termux/files/usr/bin/furina")
                putExtra("com.termux.RUN_COMMAND_ARGUMENTS", emptyArray<String>())
                putExtra("com.termux.RUN_COMMAND_WORKDIR", "/data/data/com.termux/files/home")
                putExtra("com.termux.RUN_COMMAND_BACKGROUND", false); putExtra("com.termux.RUN_COMMAND_SESSION_ACTION", "0")
            }; activity.startService(intent)
        } catch (e: Exception) { showError(e) }
    }
    fun clearError() = _state.update { it.copy(error = null) }
    fun clearNotice() = _state.update { it.copy(notice = null) }
    fun permissionDenied() = showError(IllegalStateException("Izinkan ‘Run commands in Termux environment’ pada info aplikasi FurinaHub; Termux juga harus mengaktifkan allow-external-apps."))
    private fun showError(error: Throwable) = _state.update { it.copy(error = error.message?.take(500)?.ifBlank { null } ?: "Terjadi kesalahan; silakan coba lagi.") }
    fun close() { scope.launch {
        operationJob?.cancelAndJoin(); generationJob?.cancelAndJoin(); saveDraftNow()
        try { aiEngine.unload() } finally { aiEngine.destroy(); store.close(); scope.cancel() }
    } }
}
