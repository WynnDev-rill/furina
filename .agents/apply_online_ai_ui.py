from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# --- Native Settings UI -----------------------------------------------------
p = ROOT / "src/routes/native.tsx"
s = p.read_text()

s = replace_once(s,
'''      { title: "Furina — Offline Companion" },
      { name: "description", content: "Furina offline companion dengan Qwen lokal, memori jangka panjang, dan backup terenkripsi." },''',
'''      { title: "Furina — Private AI Companion" },
      { name: "description", content: "Furina companion dengan AI lokal atau API key pribadi, memori jangka panjang, dan backup terenkripsi." },''',
"route metadata")

s = replace_once(s,
'''type GenerationMetrics = { firstTokenMs: number; tokensPerSecond: number; tokenCount: number; warmStart: boolean };
type MemoryItem =''',
'''type GenerationMetrics = { firstTokenMs: number; tokensPerSecond: number; tokenCount: number; warmStart: boolean; provider?: string; model?: string; fallbackCount?: number };
type OnlineModel = { id: string; name: string; contextWindow: number; maxOutputTokens: number; vision?: boolean; tools?: boolean; reasoning?: boolean };
type OnlineProvider = { id: string; name: string; note: string; configured: boolean; selectedModelId: string; models: OnlineModel[]; lastRefresh: number };
type OnlineAiSettings = { mode: "local" | "online"; providerId: string; autoFallback: boolean; providers: OnlineProvider[] };
type OnlineResult = { success: boolean; message: string; keyValid?: boolean; generationReady?: boolean; settings?: OnlineAiSettings };
type MemoryItem =''',
"online UI types")

s = replace_once(s,
'''type TTSProvider = "voicevox" | "clone";

type NativeBridge = {''',
'''type TTSProvider = "voicevox" | "clone";

const DEFAULT_ONLINE_AI: OnlineAiSettings = { mode: "local", providerId: "openrouter", autoFallback: true, providers: [] };

type NativeBridge = {''',
"online default")

s = replace_once(s,
'''  selectModel(modelId: string): string;
  createSession(): string;''',
'''  selectModel(modelId: string): string;
  onlineAiSettings(): string;
  setAiMode(mode: string): string;
  selectOnlineProvider(providerId: string): string;
  selectOnlineModel(providerId: string, modelId: string): string;
  setOnlineAutoFallback(enabled: boolean): string;
  removeOnlineApiKey(providerId: string): string;
  saveAndTestOnlineApiKey(providerId: string, apiKey: string, requestId: string): void;
  refreshOnlineModels(providerId: string, requestId: string): void;
  createSession(): string;''',
"bridge online methods")

s = replace_once(s,
'''    __furinaNativeState?: (state: string, modelId: string, progress: number) => void;
    __furinaNativeBackup?:''',
'''    __furinaNativeState?: (state: string, modelId: string, progress: number) => void;
    __furinaOnlineResult?: (requestId: string, payload: OnlineResult) => void;
    __furinaNativeBackup?:''',
"window online callback")

s = replace_once(s,
'''  const [selectedModel, setSelectedModel] = useState("");
  const [runtimeState, setRuntimeState] = useState("idle");''',
'''  const [selectedModel, setSelectedModel] = useState("");
  const [onlineAi, setOnlineAi] = useState<OnlineAiSettings>(DEFAULT_ONLINE_AI);
  const [onlineKeyDraft, setOnlineKeyDraft] = useState<Record<string, string>>({});
  const [onlineBusy, setOnlineBusy] = useState("");
  const [runtimeState, setRuntimeState] = useState("idle");''',
"online states")

s = replace_once(s,
'''  const bridge = () => typeof window !== "undefined" ? window.FurinaNative : undefined;

  const refreshStats = useCallback(() => {''',
'''  const bridge = () => typeof window !== "undefined" ? window.FurinaNative : undefined;

  const refreshOnlineAi = useCallback(() => {
    const b = bridge();
    if (!b) return;
    setOnlineAi(parseJson<OnlineAiSettings>(b.onlineAiSettings(), DEFAULT_ONLINE_AI));
  }, []);

  const refreshStats = useCallback(() => {''',
"refresh online settings")

s = replace_once(s,
'''    setNativeReady(true);
    refreshModels();
    refreshSessions();''',
'''    setNativeReady(true);
    refreshModels();
    refreshOnlineAi();
    refreshSessions();''',
"initialize online settings")

s = replace_once(s,
'''  }, [refreshMemories, refreshModels, refreshSessions, refreshStats]);''',
'''  }, [refreshMemories, refreshModels, refreshOnlineAi, refreshSessions, refreshStats]);''',
"initialize deps")

s = replace_once(s,
'''    window.__furinaNativeReady = initialize;
    window.__furinaNativeToken =''',
'''    window.__furinaNativeReady = initialize;
    window.__furinaOnlineResult = (requestId, payload) => {
      if (payload.settings) setOnlineAi(payload.settings);
      setOnlineBusy((current) => current === requestId ? "" : current);
      if (payload.success) {
        toast.success(payload.message);
        if (requestId.startsWith("key:")) {
          const providerId = requestId.split(":")[1];
          setOnlineKeyDraft((prev) => ({ ...prev, [providerId]: "" }));
        }
      } else toast.error(payload.message);
    };
    window.__furinaNativeToken =''',
"online callback handler")

s = replace_once(s,
'''      delete window.__furinaNativeReady;
      delete window.__furinaNativeToken;''',
'''      delete window.__furinaNativeReady;
      delete window.__furinaOnlineResult;
      delete window.__furinaNativeToken;''',
"online callback cleanup")

s = replace_once(s,
'''  }, [initialize, refreshMemories, refreshSessions, refreshStats]);''',
'''  }, [initialize, refreshMemories, refreshSessions, refreshStats]);''',
"effect deps guard")

s = replace_once(s,
'''  const selectedStatus = statuses[selectedModel];
  const canSend = nativeReady && selectedStatus?.state === "ready" && !sending && input.trim().length > 0;

  useEffect(() => {
    if (!nativeReady || !activeSessionId || selectedStatus?.state !== "ready" || sending) return;
    const timer = window.setTimeout(() => bridge()?.prepareModel(activeSessionId, name, effectivePersona), 450);
    return () => window.clearTimeout(timer);
  }, [nativeReady, activeSessionId, selectedModel, selectedStatus?.state, name, effectivePersona, sending]);''',
'''  const selectedStatus = statuses[selectedModel];
  const activeOnlineProvider = onlineAi.providers.find((provider) => provider.id === onlineAi.providerId);
  const activeOnlineModel = activeOnlineProvider?.models.find((model) => model.id === activeOnlineProvider.selectedModelId);
  const onlineReady = onlineAi.mode === "online" && Boolean(activeOnlineProvider?.configured && activeOnlineProvider.selectedModelId);
  const canSend = nativeReady && (onlineAi.mode === "online" ? onlineReady : selectedStatus?.state === "ready") && !sending && input.trim().length > 0;

  useEffect(() => {
    if (onlineAi.mode === "online" || !nativeReady || !activeSessionId || selectedStatus?.state !== "ready" || sending) return;
    const timer = window.setTimeout(() => bridge()?.prepareModel(activeSessionId, name, effectivePersona), 450);
    return () => window.clearTimeout(timer);
  }, [onlineAi.mode, nativeReady, activeSessionId, selectedModel, selectedStatus?.state, name, effectivePersona, sending]);''',
"online readiness")

s = replace_once(s,
'''    if (statuses[selectedModel]?.state !== "ready") {
      toast.error("Unduh dan pilih model AI terlebih dahulu.");
      setOpenSettings(true);
      return;
    }''',
'''    if (onlineAi.mode === "online") {
      if (!onlineReady) {
        toast.error("Pasang dan tes API key online, lalu pilih model gratis terlebih dahulu.");
        setOpenSettings(true);
        return;
      }
    } else if (statuses[selectedModel]?.state !== "ready") {
      toast.error("Unduh dan pilih model AI lokal terlebih dahulu.");
      setOpenSettings(true);
      return;
    }''',
"send readiness")

old_status = '''  const statusText = useMemo(() => {
    if (!nativeReady) return "Buka halaman ini melalui APK Furina untuk AI lokal.";
    if (runtimeState === "verifying" || selectedStatus?.state === "verifying") return `Memverifikasi model… ${Math.round((selectedStatus?.progress ?? runtimeProgress) * 100)}%`;
    if (runtimeState === "loading") return "Memuat model ke RAM…";
    if (runtimeState === "prompting") return "Menerapkan kepribadian…";
    if (runtimeState === "preparing") return "Menyiapkan mesin AI…";
    if (runtimeState === "thinking") return `${name} sedang berpikir…`;
    if (runtimeState === "error") return "Mesin AI perlu perhatian";
    if (selectedStatus?.state === "ready") return "AI lokal siap";
    return "Model belum diunduh";
  }, [nativeReady, runtimeState, runtimeProgress, selectedStatus?.state, name]);

  const runtimeBusy = ["verifying", "loading", "prompting", "preparing", "thinking"].includes(runtimeState)
    || selectedStatus?.state === "verifying";
  const runtimeReady = selectedStatus?.state === "ready" && runtimeState !== "error";'''
new_status = '''  const statusText = useMemo(() => {
    if (!nativeReady) return "Buka halaman ini melalui APK Furina.";
    if (runtimeState === "fallback") return "Model penuh — mencoba model gratis cadangan…";
    if (onlineAi.mode === "online") {
      if (runtimeState === "thinking") return `${name} sedang berpikir via ${activeOnlineProvider?.name || "AI online"}…`;
      if (runtimeState === "error") return "Provider online perlu perhatian";
      if (onlineReady) return `${activeOnlineProvider?.name || "Online"} · ${activeOnlineModel?.name || activeOnlineProvider?.selectedModelId || "model gratis"}`;
      return "Pasang dan tes API key online";
    }
    if (runtimeState === "verifying" || selectedStatus?.state === "verifying") return `Memverifikasi model… ${Math.round((selectedStatus?.progress ?? runtimeProgress) * 100)}%`;
    if (runtimeState === "loading") return "Memuat model ke RAM…";
    if (runtimeState === "prompting") return "Menerapkan kepribadian…";
    if (runtimeState === "preparing") return "Menyiapkan mesin AI…";
    if (runtimeState === "thinking") return `${name} sedang berpikir…`;
    if (runtimeState === "error") return "Mesin AI perlu perhatian";
    if (selectedStatus?.state === "ready") return "AI lokal siap";
    return "Model belum diunduh";
  }, [nativeReady, runtimeState, runtimeProgress, selectedStatus?.state, name, onlineAi.mode, onlineReady, activeOnlineProvider?.name, activeOnlineProvider?.selectedModelId, activeOnlineModel?.name]);

  const runtimeBusy = ["verifying", "loading", "prompting", "preparing", "thinking", "fallback"].includes(runtimeState)
    || (onlineAi.mode === "local" && selectedStatus?.state === "verifying");
  const runtimeReady = onlineAi.mode === "online" ? onlineReady && runtimeState !== "error" : selectedStatus?.state === "ready" && runtimeState !== "error";'''
s = replace_once(s, old_status, new_status, "hybrid status")

s = replace_once(s,
'''            placeholder={selectedStatus?.state === "ready" ? "Ketik pesan…" : "Unduh model AI dari Pengaturan…"}''',
'''            placeholder={onlineAi.mode === "online" ? (onlineReady ? "Ketik pesan…" : "Pasang API key online dari Pengaturan…") : (selectedStatus?.state === "ready" ? "Ketik pesan…" : "Unduh model AI dari Pengaturan…")}''',
"composer placeholder")

s = replace_once(s,
'''            <SheetDescription className="max-w-sm text-xs leading-relaxed">Identitas, AI lokal, suara, memori, dan backup.</SheetDescription>''',
'''            <SheetDescription className="max-w-sm text-xs leading-relaxed">Identitas, AI lokal/online, suara, memori, dan backup.</SheetDescription>''',
"settings description")

voice_anchor = '''            <details className="group rounded-2xl border bg-muted/10 shadow-sm">
              <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
                <span className="flex items-center gap-2 text-sm font-semibold"><Volume2 className="h-4 w-4 text-primary" />Suara</span>'''
online_section = '''            <section className="space-y-4 rounded-2xl border bg-muted/10 p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Cloud className="h-[18px] w-[18px]" /></span>
                <div className="min-w-0 flex-1">
                  <Label>Mesin AI online</Label>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">Gunakan API key milikmu sendiri. Memori, identitas, dan hubungan Furina tetap sama saat berpindah model atau provider.</p>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-xs">Mode AI</Label>
                <Select value={onlineAi.mode} onValueChange={(value) => {
                  const b = bridge(); if (!b) return;
                  setOnlineAi(parseJson<OnlineAiSettings>(b.setAiMode(value), onlineAi));
                  setRuntimeError("");
                }}>
                  <SelectTrigger className="min-h-11"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="local">Lokal — Deckard 4B di perangkat</SelectItem>
                    <SelectItem value="online">Online — API key pribadi</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {onlineAi.mode === "online" && (
                <div className="space-y-4 rounded-xl border bg-background/30 p-3">
                  <div className="space-y-2">
                    <Label className="text-xs">Provider</Label>
                    <Select value={onlineAi.providerId} onValueChange={(value) => {
                      const b = bridge(); if (!b) return;
                      setOnlineAi(parseJson<OnlineAiSettings>(b.selectOnlineProvider(value), onlineAi));
                      setRuntimeError("");
                    }}>
                      <SelectTrigger className="min-h-11"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {onlineAi.providers.map((provider) => <SelectItem key={provider.id} value={provider.id}>{provider.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>

                  {activeOnlineProvider ? (
                    <>
                      <div className={`rounded-lg border p-2.5 text-[11px] ${activeOnlineProvider.configured ? "border-emerald-500/25 bg-emerald-500/10" : "border-amber-500/25 bg-amber-500/10"}`}>
                        <div className="flex items-center gap-2 font-medium">
                          {activeOnlineProvider.configured ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <AlertCircle className="h-3.5 w-3.5 text-amber-500" />}
                          {activeOnlineProvider.configured ? "API key tersimpan dan terenkripsi" : "API key belum dipasang"}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label className="text-xs">API key {activeOnlineProvider.name}</Label>
                        <Input
                          type="password"
                          autoComplete="off"
                          value={onlineKeyDraft[activeOnlineProvider.id] || ""}
                          placeholder={activeOnlineProvider.configured ? "Isi hanya jika ingin mengganti key" : "Tempel API key di sini"}
                          onChange={(e) => setOnlineKeyDraft((prev) => ({ ...prev, [activeOnlineProvider.id]: e.target.value }))}
                        />
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" disabled={Boolean(onlineBusy)} onClick={() => {
                            const key = (onlineKeyDraft[activeOnlineProvider.id] || "").trim();
                            if (!key) { toast.error("Masukkan API key terlebih dahulu."); return; }
                            const requestId = `key:${activeOnlineProvider.id}:${Date.now()}`;
                            setOnlineBusy(requestId);
                            bridge()?.saveAndTestOnlineApiKey(activeOnlineProvider.id, key, requestId);
                          }}>
                            {onlineBusy.startsWith("key:") ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Check className="mr-1.5 h-3.5 w-3.5" />}
                            Simpan & tes
                          </Button>
                          <Button size="sm" variant="outline" disabled={!activeOnlineProvider.configured || Boolean(onlineBusy)} onClick={() => {
                            const requestId = `models:${activeOnlineProvider.id}:${Date.now()}`;
                            setOnlineBusy(requestId);
                            bridge()?.refreshOnlineModels(activeOnlineProvider.id, requestId);
                          }}>
                            {onlineBusy.startsWith("models:") ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
                            Perbarui model
                          </Button>
                          {activeOnlineProvider.configured && <Button size="sm" variant="ghost" disabled={Boolean(onlineBusy)} onClick={() => {
                            if (!confirm(`Hapus API key ${activeOnlineProvider.name} dari perangkat?`)) return;
                            const b = bridge(); if (!b) return;
                            setOnlineAi(parseJson<OnlineAiSettings>(b.removeOnlineApiKey(activeOnlineProvider.id), onlineAi));
                            setOnlineKeyDraft((prev) => ({ ...prev, [activeOnlineProvider.id]: "" }));
                          }}><Trash2 className="mr-1 h-3.5 w-3.5" />Hapus key</Button>}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label className="text-xs">Model gratis</Label>
                        <Select value={activeOnlineProvider.selectedModelId || ""} disabled={!activeOnlineProvider.models.length} onValueChange={(value) => {
                          const b = bridge(); if (!b) return;
                          setOnlineAi(parseJson<OnlineAiSettings>(b.selectOnlineModel(activeOnlineProvider.id, value), onlineAi));
                        }}>
                          <SelectTrigger className="min-h-11"><SelectValue placeholder="Tes key untuk memuat model gratis" /></SelectTrigger>
                          <SelectContent>
                            {activeOnlineProvider.models.map((model) => (
                              <SelectItem key={model.id} value={model.id}>{model.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <p className="text-[10px] leading-relaxed text-muted-foreground">{activeOnlineProvider.models.length ? `${activeOnlineProvider.models.length} model gratis/free-tier terdeteksi dari provider.` : "Daftar model dimuat setelah API key berhasil diuji."}</p>
                      </div>

                      <div className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 p-3">
                        <div className="min-w-0">
                          <Label className="text-xs">Fallback otomatis</Label>
                          <p className="mt-0.5 text-[10px] leading-relaxed text-muted-foreground">Jika model gagal sebelum mengirim jawaban karena kuota, rate limit, atau unavailable, coba model gratis berikutnya.</p>
                        </div>
                        <Switch checked={onlineAi.autoFallback} onCheckedChange={(checked) => {
                          const b = bridge(); if (!b) return;
                          setOnlineAi(parseJson<OnlineAiSettings>(b.setOnlineAutoFallback(checked), onlineAi));
                        }} />
                      </div>

                      <p className="text-[10px] leading-relaxed text-muted-foreground">{activeOnlineProvider.note}</p>
                    </>
                  ) : <p className="text-xs text-muted-foreground">Provider belum tersedia. Tutup dan buka kembali Pengaturan.</p>}
                </div>
              )}

              <p className="text-[10px] leading-relaxed text-muted-foreground">API key tidak disimpan di web/localStorage dan tidak ikut backup memori. Key dienkripsi oleh Android Keystore di perangkat.</p>
            </section>

''' + voice_anchor
s = replace_once(s, voice_anchor, online_section, "online settings section")

p.write_text(s)

# --- Online provider correctness -------------------------------------------
p = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/OnlineAiProvider.kt"
s = p.read_text()
s = replace_once(s,
'''    suspend fun streamChat(def: OnlineProviderDefinition, key: String, request: AiGenerationRequest, emit: suspend (String) -> Unit) = withContext(Dispatchers.IO) {''',
'''    // Keep Flow emissions in the collector coroutine. Emitting from withContext(IO)
    // violates Flow context preservation and can crash streaming at runtime.
    suspend fun streamChat(def: OnlineProviderDefinition, key: String, request: AiGenerationRequest, emit: suspend (String) -> Unit) {''',
"flow context preservation")
s = replace_once(s,
'''            FreeModelStrategy.GEMINI_FREE_TIER ->
                (lower.contains("flash") || lower.contains("gemma")) && !lower.contains("live")''',
'''            FreeModelStrategy.GEMINI_FREE_TIER ->
                lower.contains("flash") && !lower.contains("live") && !lower.contains("image")''',
"Gemini free-tier conservative filter")
p.write_text(s)

# --- Bridge switch safety --------------------------------------------------
p = ROOT / "android-wrapper/app/src/main/java/com/wynndev/furina/FurinaBridge.kt"
s = p.read_text()
s = replace_once(s,
'''    fun setAiMode(mode: String): String {
        val result = onlineManager.setMode(mode)
        scope.launch { aiEngine.unload() }
        return result
    }''',
'''    fun setAiMode(mode: String): String {
        prepareJob?.cancel()
        prepareJob = null
        val result = onlineManager.setMode(mode)
        scope.launch { aiEngine.unload() }
        return result
    }''',
"cancel prepare on mode switch")
s = replace_once(s,
'''    fun selectOnlineProvider(providerId: String): String {
        val result = onlineManager.setProvider(providerId)
        scope.launch { aiEngine.unload() }
        return result
    }''',
'''    fun selectOnlineProvider(providerId: String): String {
        prepareJob?.cancel()
        prepareJob = null
        val result = onlineManager.setProvider(providerId)
        scope.launch { aiEngine.unload() }
        return result
    }''',
"cancel prepare on provider switch")
p.write_text(s)

# --- CI assertions ---------------------------------------------------------
p = ROOT / ".github/workflows/build-furina-apk.yml"
s = p.read_text()
anchor = '''          grep -q 'PrivateContextStreamFilter' android-wrapper/app/src/main/java/com/wynndev/furina/LocalLlamaProvider.kt
          grep -q 'prepareModel(activeSessionId, name, effectivePersona)' src/routes/native.tsx'''
replacement = '''          grep -q 'PrivateContextStreamFilter' android-wrapper/app/src/main/java/com/wynndev/furina/LocalLlamaProvider.kt
          grep -q 'class ApiKeyVault' android-wrapper/app/src/main/java/com/wynndev/furina/ApiKeyVault.kt
          grep -q 'AndroidKeyStore' android-wrapper/app/src/main/java/com/wynndev/furina/ApiKeyVault.kt
          grep -q 'class OnlineProviderManager' android-wrapper/app/src/main/java/com/wynndev/furina/OnlineAiProvider.kt
          grep -q 'openrouter/free' android-wrapper/app/src/main/java/com/wynndev/furina/OnlineAiProvider.kt
          grep -q 'saveAndTestOnlineApiKey' android-wrapper/app/src/main/java/com/wynndev/furina/FurinaBridge.kt
          grep -q 'Fallback otomatis' src/routes/native.tsx
          grep -q 'Simpan & tes' src/routes/native.tsx
          grep -q 'prepareModel(activeSessionId, name, effectivePersona)' src/routes/native.tsx'''
s = replace_once(s, anchor, replacement, "CI online assertions")
p.write_text(s)

# Remove this one-shot migration and its trigger workflow before committing.
Path(__file__).unlink(missing_ok=True)
(ROOT / ".github/workflows/apply-online-ai-ui.yml").unlink(missing_ok=True)
print("Online AI UI migration applied successfully")
