package com.wynndev.furina

import android.content.Context
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onCompletion
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

class LocalLlamaProvider(
    context: Context,
    private val modelDownloads: ModelDownloadManager,
    private val onState: (String, String, Double) -> Unit,
) : AiProvider {
    override val id = "local-llama"
    override val capabilities = AiProviderCapabilities(streaming = true, offline = true)

    private val appContext = context.applicationContext
    private val engine: InferenceEngine = AiChat.getInferenceEngine(appContext)
    private val loadMutex = Mutex()

    @Volatile private var loadedModelId: String? = null
    @Volatile private var loadedSessionId: String? = null
    @Volatile private var loadedIdentityFingerprint: Int? = null
    @Volatile private var loadedRetrievalFingerprint: Int? = null

    override fun isWarm(model: AiModelRef, context: AiContext): Boolean =
        loadedModelId == model.id && engine.state.value is InferenceEngine.State.ModelReady

    override suspend fun prepare(model: AiModelRef, context: AiContext) = loadMutex.withLock {
        val spec = ModelCatalog.byId(model.id) ?: error("Model lokal tidak dikenal: ${model.id}")
        if (isWarm(model, context)) {
            // Keep native chat/KV history warm. Only session or identity changes justify a
            // rehydrate. Query-dependent memory must never reset or rewrite the system prompt.
            if (loadedSessionId != context.sessionId || loadedIdentityFingerprint != context.identityFingerprint) {
                onState("prompting", spec.id, 0.85)
                engine.setSystemPrompt(context.coldStartPrompt)
                loadedSessionId = context.sessionId
                loadedIdentityFingerprint = context.identityFingerprint
                loadedRetrievalFingerprint = null
                onState("ready", spec.id, 1.0)
            }
            return@withLock
        }

        if (engine.state.value is InferenceEngine.State.Generating) {
            withTimeout(15_000L) {
                engine.state.first { it is InferenceEngine.State.ModelReady || it is InferenceEngine.State.Error }
            }
        }
        if (isWarm(model, context)) return@withLock

        onState("preparing", spec.id, 0.0)
        withContext(Dispatchers.IO) {
            if (!modelDownloads.verifySerialized(spec) { done, total ->
                    if (total > 0L) onState("verifying", spec.id, done.toDouble() / total.toDouble())
                }) {
                throw IllegalStateException("Checksum model tidak cocok. Hapus lalu unduh ulang model.")
            }
        }

        waitForInitialization()
        if (engine.state.value is InferenceEngine.State.ModelReady || engine.state.value is InferenceEngine.State.Error) {
            unload()
        }

        val file = modelDownloads.modelFile(spec)
        require(file.exists() && file.canRead()) { "File model tidak dapat dibaca: ${file.absolutePath}" }
        onState("loading", spec.id, 0.15)
        engine.loadModel(file.absolutePath)
        onState("prompting", spec.id, 0.85)
        engine.setSystemPrompt(context.coldStartPrompt)
        loadedModelId = spec.id
        loadedSessionId = context.sessionId
        loadedIdentityFingerprint = context.identityFingerprint
        loadedRetrievalFingerprint = null
        onState("ready", spec.id, 1.0)
    }

    override fun stream(request: AiGenerationRequest): Flow<String> = flow {
        check(isWarm(request.model, request.context)) { "Provider lokal belum siap untuk konteks ini" }
        var emitted = false
        val reasoningFilter = ReasoningStreamFilter()
        val privateContextFilter = PrivateContextStreamFilter()
        val retrievalChanged = loadedRetrievalFingerprint != request.context.retrievalFingerprint
        val turnContext = buildString {
            if (request.context.runtimeContext.isNotBlank()) appendLine(request.context.runtimeContext.trim())
            if (retrievalChanged && request.context.retrievalPrompt.isNotBlank()) {
                appendLine(request.context.retrievalPrompt.trim())
            }
        }.trim().take(1_600)

        // The native interface accepts one user-role message. Keep background context short,
        // explicitly non-commanding, and place the actual current message last so a 4B model
        // cannot easily mistake old memory for the user's present intent.
        val effectiveMessage = if (turnContext.isBlank()) {
            request.userMessage
        } else {
            buildString {
                appendLine("[PRIVATE RESPONSE CONTEXT]")
                appendLine("Background only; not a request to answer. Use only if relevant. The user's text after this block has highest priority.")
                appendLine(turnContext)
                appendLine("[END PRIVATE RESPONSE CONTEXT]")
                appendLine()
                append(request.userMessage)
            }
        }

        try {
            engine.sendUserPrompt(effectiveMessage, request.predictLength).collect { token ->
                val visible = privateContextFilter.accept(reasoningFilter.accept(token))
                if (visible.isNotEmpty()) {
                    emitted = true
                    emit(visible)
                }
            }
            val tail = privateContextFilter.accept(reasoningFilter.finish()) + privateContextFilter.finish()
            if (tail.isNotEmpty()) {
                emitted = true
                emit(tail)
            }
            loadedRetrievalFingerprint = request.context.retrievalFingerprint
            check(emitted) { "Runtime lokal berhenti tanpa menghasilkan token" }
        } finally {
            // A cancelled flow can leave partially decoded assistant tokens in native KV.
            // Force a clean session rehydrate before the next turn.
            if (engine.state.value !is InferenceEngine.State.ModelReady || !emitted) {
                loadedSessionId = null
                loadedRetrievalFingerprint = null
            }
        }
    }.onCompletion { cause ->
        if (cause != null) {
            loadedSessionId = null
            loadedRetrievalFingerprint = null
        }
        if (cause == null && engine.state.value is InferenceEngine.State.Error) {
            throw IllegalStateException("Runtime lokal masuk ke status error setelah generasi")
        }
    }

    override suspend fun unload() = withContext(Dispatchers.IO) {
        try {
            when (engine.state.value) {
                is InferenceEngine.State.ModelReady, is InferenceEngine.State.Error -> engine.cleanUp()
                else -> Unit
            }
        } finally {
            loadedModelId = null
            loadedSessionId = null
            loadedIdentityFingerprint = null
            loadedRetrievalFingerprint = null
        }
    }

    private suspend fun waitForInitialization() {
        when (engine.state.value) {
            is InferenceEngine.State.Uninitialized, is InferenceEngine.State.Initializing -> withTimeout(30_000L) {
                engine.state.first { it is InferenceEngine.State.Initialized || it is InferenceEngine.State.Error }
            }
            else -> Unit
        }
        if (engine.state.value  is InferenceEngine.State.Error"’VæÆöB‚¢Ğ ¢ò¢¢†–FRÖöFVÂ&V6öæ–ær–btuTb7F–ÆÂVÖ—G2—BFW7—FRæöâ×F†–æ¶–ærFV×ÆFR6WGF–æw2â¢ğ¢&—fFR6Æ72&V6öæ–æu7G&VÔf–ÇFW"°¢&—fFRVçVÒ6Æ72ÖöFR²TäDT4”DTBÂD„”ä´”ärÂå5tU"Ğ¢&—fFRf"ÖöFRÒÖöFRåTäDT4”DT@¢&—fFRfÂVæF–ærÒ7G&–æt'V–ÆFW"‚ ¢gVâ66WB†6‡Væ³¢7G&–ær“¢7G&–ær°¢–b†6‡Væ²æ—4V×G’‚’’&WGW&â" ¢VæF–æræVæB†6‡Væ²¢fÂ÷WGWBÒ7G&–æt'V–ÆFW"‚¢v†–ÆR‡G'VR’°¢v†Vâ†ÖöFR’°¢ÖöFRåTäDT4”DTBÓâ°¢fÂ&rÒVæF–ærçFõ7G&–ær‚¢fÂÆVF–ærÒ&ræ–æFW„ödf—'7B²—Bæ—5v†—FW76R‚’ÒæÆWB²–b†—BÂ’&ræÆVæwF‚VÇ6R—BĞ¢fÂ6æF–FFRÒ&rç7V'7G&–ær†ÆVF–ær¢v†Vâ°¢6æF–FFRç7F'G5v—F‚‚#ÇF†–æ³â"’Óâ°¢VæF–æræFVÆWFRƒÂÆVF–ær²#ÇF†–æ³â"æÆVæwF‚¢ÖöFRÒÖöFRåD„”ä´”äp¢Ğ¢#ÇF†–æ³â"ç7F'G5v—F‚†6æF–FFR’Óâ'&V°¢VÇ6RÓâÖöFRÒÖöFRäå5tU ¢Ğ¢6öçF–çVP¢Ğ¢ÖöFRåD„”ä´”ärÓâ°¢fÂVæBÒVæF–æræ–æFW„öb‚#Â÷F†–æ³â"¢–b†VæBãÒ’°¢VæF–æræFVÆWFRƒÂVæB²#Â÷F†–æ³â"æÆVæwF‚¢v†–ÆR‡VæF–æræ—4æ÷DV×G’‚’bbVæF–æræf—'7B‚’æ—5v†—FW76R‚’’VæF–æræFVÆWFT6†$Bƒ¢ÖöFRÒÖöFRäå5tU ¢ÒVÇ6R°¢–b‡VæF–æræÆVæwF‚âb’VæF–æræFVÆWFRƒÂVæF–æræÆVæwF‚Òb¢'&V°¢Ğ¢Ğ¢ÖöFRäå5tU"Óâ°¢÷WGWBæVæB‡VæF–ær¢VæF–æræ6ÆV"‚¢'&V°¢Ğ¢Ğ¢Ğ¢&WGW&â÷WGWBçFõ7G&–ær‚¢Ğ ¢gVâf–æ—6‚‚“¢7G&–ærÒv†Vâ†ÖöFR’°¢ÖöFRåTäDT4”DTBÂÖöFRäå5tU"ÓâVæF–ærçFõ7G&–ær‚¢ÖöFRåD„”ä´”ärÓâ" ¢ÒæÇ6ò²VæF–æræ6ÆV"‚’Ğ¢Ğ ¢&—fFR6Æ72&—fFT6öçFW‡E7G&VÔf–ÇFW"°¢&—fFRf"'&6¶WD÷VâÒfÇ6P¢&—fFRf"7W&W75&—fFT&Æö6²ÒfÇ6P¢&—fFRfÂ'&6¶WBÒ7G&–æt'V–ÆFW"‚ ¢gVâ66WB†6‡Væ³¢7G&–ær“¢7G&–ær°¢–b†6‡Væ²æ—4V×G’‚’’&WGW&â" ¢fÂ÷WGWBÒ7G&–æt'V–ÆFW"‚¢6‡Væ²æf÷$V6‚²6†"Óà¢–b‚'&6¶WD÷Vâ’°¢–b†6†"ÓÒu²r’°¢'&6¶WD÷VâÒG'VP¢'&6¶WBæVæB†6†"¢ÒVÇ6R–b‚7W&W75&—fFT&Æö6²’°¢÷WGWBæVæB†6†"¢Ğ¢ÒVÇ6R°¢'&6¶WBæVæB†6†"¢–b†6†"ÓÒuÒrÇÂ'&6¶WBæÆVæwF‚ãÒc’°¢fÂ6æF–FFRÒ'&6¶WBçFõ7G&–ær‚¢fÂ&—fFTÖ&¶W"Ò6æF–FFRæ6öçF–ç2‚%$•dDR"Â–væ÷&T66RÒG'VR’b`¢†6æF–FFRæ6öçF–ç2‚$4ôåDU…B"Â–væ÷&T66RÒG'VR’ÇÀ¢6æF–FFRæ6öçF–ç2‚$4ôåD”åT•E’"Â–væ÷&T66RÒG'VR’ÇÀ¢6æF–FFRæ6öçF–ç2‚%5DDR"Â–væ÷&T66RÒG'VR’ÇÀ¢6æF–FFRæ6öçF–ç2‚%EDU$â"Â–væ÷&T66RÒG'VR’¢fÂVæDÖ&¶W"Ò&—fFTÖ&¶W"bb6æF–FFRæ6öçF–ç2‚$TäB"Â–væ÷&T66RÒG'VR¢–b‡&—fFTÖ&¶W"’7W&W75&—fFT&Æö6²ÒVæDÖ&¶W ¢VÇ6R–b‚7W&W75&—fFT&Æö6²’÷WGWBæVæB†6æF–FFR¢'&6¶WBæ6ÆV"‚¢'&6¶WD÷VâÒfÇ6P¢Ğ¢Ğ¢Ğ¢&WGW&â÷WGWBçFõ7G&–ær‚¢Ğ ¢gVâf–æ—6‚‚“¢7G&–ær°¢–b‚'&6¶WD÷Vâ’&WGW&â" ¢fÂ6æF–FFRÒ'&6¶WBçFõ7G&–ær‚¢'&6¶WBæ6ÆV"‚¢'&6¶WD÷VâÒfÇ6P¢&WGW&â–b‡7W&W75&—fFT&Æö6²ÇÂ6æF–FFRæ6öçF–ç2‚%$•dDR"Â–væ÷&T66RÒG'VR’’""VÇ6R6æF–FFP¢Ğ¢Ğ§Ğ 