import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Brain, Check, Cloud, Loader2, RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";

export type AiMode = "local" | "online";

type OnlineModel = {
  id: string;
  name: string;
  contextWindow: number;
  maxOutputTokens: number;
};

type OnlineProvider = {
  id: string;
  name: string;
  description: string;
  keyHint: string;
  keyConfigured: boolean;
  keyValidated: boolean;
  selectedModel: string;
  models: OnlineModel[];
};

type OnlineAiSettings = {
  mode: AiMode;
  selectedProvider: string;
  autoFallback: boolean;
  providers: OnlineProvider[];
};

type OnlineBridge = {
  onlineAiSettings(): string;
  setAiMode(mode: string): void;
  setOnlineProvider(providerId: string): void;
  setOnlineModel(providerId: string, modelId: string): void;
  setOnlineAutoFallback(enabled: boolean): void;
  saveOnlineApiKey(providerId: string, apiKey: string): void;
  deleteOnlineApiKey(providerId: string): void;
  testOnlineProvider(providerId: string): void;
  refreshOnlineModels(providerId: string): void;
};

const EMPTY: OnlineAiSettings = {
  mode: "local",
  selectedProvider: "openrouter",
  autoFallback: true,
  providers: [],
};

function bridge(): OnlineBridge | undefined {
  if (typeof window === "undefined") return undefined;
  return (window as unknown as { FurinaNative?: OnlineBridge }).FurinaNative;
}

function parseSettings(raw?: string): OnlineAiSettings {
  try {
    const parsed = raw ? JSON.parse(raw) as OnlineAiSettings : EMPTY;
    return {
      mode: parsed.mode === "online" ? "online" : "local",
      selectedProvider: parsed.selectedProvider || "openrouter",
      autoFallback: parsed.autoFallback !== false,
      providers: Array.isArray(parsed.providers) ? parsed.providers : [],
    };
  } catch {
    return EMPTY;
  }
}

function announceChange() {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("furina-ai-config-changed"));
}

export function OnlineAiSettingsCard({ nativeReady }: { nativeReady: boolean }) {
  const [settings, setSettings] = useState<OnlineAiSettings>(EMPTY);
  const [keyDraft, setKeyDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const autoRefreshAttempted = useRef(new Set<string>());

  const refresh = useCallback(() => {
    const b = bridge();
    if (!b) return;
    setSettings(parseSettings(b.onlineAiSettings()));
    announceChange();
  }, []);

  useEffect(() => {
    if (!nativeReady) return;
    refresh();
    const host = window as unknown as {
      __furinaOnlineAi?: (event: string, providerId: string, success: boolean, message: string) => void;
    };
    host.__furinaOnlineAi = (event, _providerId, success, nextMessage) => {
      if (event === "testing" || event === "refreshing") {
        setBusy(true);
        setMessage(nextMessage);
        return;
      }
      setBusy(false);
      setMessage(nextMessage);
      refresh();
      if (event === "saved" && success) return;
      success ? toast.success(nextMessage) : toast.error(nextMessage);
    };
    return () => { delete host.__furinaOnlineAi; };
  }, [nativeReady, refresh]);

  const provider = useMemo(
    () => settings.providers.find((item) => item.id === settings.selectedProvider) ?? settings.providers[0],
    [settings],
  );
  const selectedModel = provider?.models.find((model) => model.id === provider.selectedModel) ?? provider?.models[0];

  useEffect(() => {
    if (!nativeReady || !provider?.keyConfigured || provider.models.length > 0 || busy) return;
    const refreshKey = `${provider.id}:${provider.keyValidated ? "validated" : "pending"}`;
    if (autoRefreshAttempted.current.has(refreshKey)) return;
    autoRefreshAttempted.current.add(refreshKey);
    setBusy(true);
    setMessage("Memuat katalog model gratis…");
    bridge()?.refreshOnlineModels(provider.id);
  }, [nativeReady, provider?.id, provider?.keyConfigured, provider?.keyValidated, provider?.models.length, busy]);

  function chooseMode(mode: AiMode) {
    bridge()?.setAiMode(mode);
    setSettings((current) => ({ ...current, mode }));
    announceChange();
  }

  function chooseProvider(providerId: string) {
    bridge()?.setOnlineProvider(providerId);
    setKeyDraft("");
    setMessage("");
    setSettings((current) => ({ ...current, selectedProvider: providerId }));
    window.setTimeout(refresh, 50);
  }

  function saveAndTest() {
    const clean = keyDraft.trim();
    if (!provider || clean.length < 8 || busy) return;
    autoRefreshAttempted.current.delete(`${provider.id}:validated`);
    autoRefreshAttempted.current.delete(`${provider.id}:pending`);
    setBusy(true);
    setMessage("Menyimpan dan menguji API key…");
    bridge()?.saveOnlineApiKey(provider.id, clean);
    setKeyDraft("");
  }

  function testExisting() {
    if (!provider?.keyConfigured || busy) return;
    setBusy(true);
    setMessage("Menguji API key dan model gratis…");
    bridge()?.testOnlineProvider(provider.id);
  }

  function refreshModels() {
    if (!provider?.keyConfigured || busy) return;
    setBusy(true);
    setMessage("Memperbarui model gratis…");
    bridge()?.refreshOnlineModels(provider.id);
  }

  function deleteKey() {
    if (!provider?.keyConfigured || busy) return;
    if (!confirm(`Hapus API key ${provider.name}?`)) return;
    autoRefreshAttempted.current.delete(`${provider.id}:validated`);
    autoRefreshAttempted.current.delete(`${provider.id}:pending`);
    bridge()?.deleteOnlineApiKey(provider.id);
    setKeyDraft("");
    setMessage("");
    window.setTimeout(refresh, 50);
  }

  return (
    <section className="space-y-4 rounded-2xl border bg-muted/10 p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Cloud className="h-[18px] w-[18px]" /></span>
        <div className="min-w-0 flex-1">
          <Label>Mesin AI</Label>
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">Gunakan model lokal atau API online. Identitas, memori, dan riwayat Furina tetap sama saat mesin diganti.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 rounded-xl bg-muted/40 p-1">
        <Button type="button" size="sm" variant={settings.mode === "local" ? "default" : "ghost"} onClick={() => chooseMode("local")}>Lokal</Button>
        <Button type="button" size="sm" variant={settings.mode === "online" ? "default" : "ghost"} onClick={() => chooseMode("online")}>API online</Button>
      </div>

      {settings.mode === "local" ? (
        <div className="rounded-xl border bg-background/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
          Mode lokal aktif. Model GGUF di bawah dipakai tanpa API key dan seluruh inferensi teks tetap di perangkat.
        </div>
      ) : (
        <div className="space-y-4 rounded-xl border bg-background/35 p-3">
          {!nativeReady && <div className="rounded-lg bg-destructive/10 p-2 text-xs text-destructive">Pengaturan API hanya tersedia di APK Furina.</div>}

          <div className="rounded-lg bg-sky-500/10 p-2.5 text-[10px] leading-relaxed text-sky-700 dark:text-sky-200">
            Dalam mode API online, pesan saat ini dan hanya konteks continuity/memory yang relevan untuk jawaban dikirim ke provider yang kamu pilih. Database lengkap tetap lokal di perangkat.
          </div>

          <div className="space-y-2">
            <Label className="text-xs">Provider</Label>
            <Select value={provider?.id || settings.selectedProvider} onValueChange={chooseProvider} disabled={!nativeReady || busy}>
              <SelectTrigger className="min-h-11"><SelectValue placeholder="Pilih provider" /></SelectTrigger>
              <SelectContent>
                {settings.providers.map((item) => <SelectItem key={item.id} value={item.id}>{item.name}</SelectItem>)}
              </SelectContent>
            </Select>
            {provider && <p className="text-[10px] leading-relaxed text-muted-foreground">{provider.description}</p>}
          </div>

          {provider && (
            <>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs">API key</Label>
                  <span className={`inline-flex items-center gap-1 text-[10px] ${provider.keyValidated ? "text-emerald-500" : "text-muted-foreground"}`}>
                    {provider.keyValidated && <Check className="h-3 w-3" />}
                    {provider.keyValidated ? "Terverifikasi" : provider.keyConfigured ? "Tersimpan · belum lolos tes" : "Belum ada"}
                  </span>
                </div>
                <Input
                  type="password"
                  autoComplete="off"
                  value={keyDraft}
                  onChange={(event) => setKeyDraft(event.target.value)}
                  placeholder={provider.keyConfigured ? "Masukkan key baru untuk mengganti" : provider.keyHint}
                  className="font-mono text-xs"
                  disabled={busy}
                />
                <p className="text-[10px] leading-relaxed text-muted-foreground">Key dienkripsi memakai Android Keystore. Nilai asli tidak dikirim ke UI lagi dan tidak ikut backup Furina.</p>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button size="sm" disabled={keyDraft.trim().length < 8 || busy} onClick={saveAndTest}>
                  {busy && keyDraft.trim().length >= 8 ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Check className="mr-1.5 h-3.5 w-3.5" />}
                  Simpan & tes
                </Button>
                <Button size="sm" variant="outline" disabled={!provider.keyConfigured || busy} onClick={testExisting}>Tes key</Button>
                <Button size="sm" variant="outline" disabled={!provider.keyConfigured || busy} onClick={refreshModels}><RotateCcw className="mr-1.5 h-3.5 w-3.5" />Model gratis</Button>
                {provider.keyConfigured && <Button size="sm" variant="ghost" disabled={busy} onClick={deleteKey}><Trash2 className="mr-1.5 h-3.5 w-3.5" />Hapus key</Button>}
              </div>

              {message && (
                <div className={`flex items-start gap-2 rounded-lg p-2.5 text-[11px] leading-relaxed ${message.toLowerCase().includes("gagal") || message.toLowerCase().includes("tidak valid") ? "bg-destructive/10 text-destructive" : "bg-muted/60 text-muted-foreground"}`}>
                  {busy ? <Loader2 className="mt-0.5 h-3.5 w-3.5 shrink-0 animate-spin" /> : <Brain className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
                  <span>{message}</span>
                </div>
              )}

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label className="text-xs">Model gratis utama</Label>
                  <span className="text-[10px] text-muted-foreground">{provider.models.length} tersedia</span>
                </div>
                <Select
                  value={selectedModel?.id || ""}
                  onValueChange={(modelId) => {
                    bridge()?.setOnlineModel(provider.id, modelId);
                    setSettings((current) => ({
                      ...current,
                      providers: current.providers.map((item) => item.id === provider.id ? { ...item, selectedModel: modelId } : item),
                    }));
                    announceChange();
                  }}
                  disabled={!provider.keyValidated || busy || provider.models.length === 0}
                >
                  <SelectTrigger className="min-h-11"><SelectValue placeholder={provider.keyConfigured ? "Tes key untuk memuat model gratis" : "Masukkan API key dulu"} /></SelectTrigger>
                  <SelectContent>
                    {provider.models.map((model) => (
                      <SelectItem key={model.id} value={model.id}>{model.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedModel && <p className="text-[10px] leading-relaxed text-muted-foreground">Context terdeteksi: hingga {selectedModel.contextWindow.toLocaleString()} token. Furina menyesuaikan jumlah memory/RAG yang disuntikkan ke model.</p>}
              </div>

              <div className="flex min-h-12 items-center justify-between gap-4 rounded-xl border bg-muted/25 p-3">
                <div className="min-w-0">
                  <Label className="text-xs">Fallback otomatis model gratis</Label>
                  <p className="mt-0.5 text-[10px] leading-relaxed text-muted-foreground">Jika model utama kena quota/rate limit atau sedang unavailable sebelum jawaban dimulai, Furina mencoba model gratis lain pada provider yang sama.</p>
                </div>
                <Switch
                  checked={settings.autoFallback}
                  onCheckedChange={(enabled) => {
                    bridge()?.setOnlineAutoFallback(enabled);
                    setSettings((current) => ({ ...current, autoFallback: enabled }));
                    announceChange();
                  }}
                />
              </div>

              {!provider.keyValidated && (
                <div className="flex items-start gap-2 rounded-lg bg-amber-500/10 p-2.5 text-[11px] leading-relaxed text-amber-700 dark:text-amber-300">
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{provider.keyConfigured ? "API key sudah tersimpan tetapi belum lolos tes. Mode online tetap dikunci sampai tes berhasil." : "Mode online belum dapat dipakai sampai API key provider ini disimpan dan lolos tes."}</span>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}
