import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Brain, Check, ChevronLeft, Cloud, Copy, Download, HardDrive, Loader2,
  MessageSquarePlus, MessagesSquare, Play, Send, Settings, Square, Trash2, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import furinaDefault from "@/assets/furina.jpg";
import { speakVoicevoxUrl } from "@/lib/furina.functions";

export const Route = createFileRoute("/native")({
  head: () => ({
    meta: [
      { title: "Furina — Offline Companion" },
      { name: "description", content: "Furina offline companion dengan Qwen lokal, memori jangka panjang, dan backup terenkripsi." },
    ],
  }),
  component: FurinaNativeApp,
});

type NativeModel = {
  id: string;
  name: string;
  subtitle: string;
  expectedBytes: number;
  recommended: boolean;
};
type ModelStatus = {
  id?: string;
  state: "not_downloaded" | "downloading" | "paused" | "verifying" | "ready" | "corrupt" | "failed" | "missing" | "unknown";
  downloadedBytes?: number;
  totalBytes?: number;
  progress?: number;
  verified?: boolean;
  selected?: boolean;
  reason?: number;
};
type NativeMessage = { id: string; role: "user" | "assistant"; content: string; createdAt: number };
type NativeSession = { id: string; title: string; createdAt: number; updatedAt?: number; messageCount?: number };
type MemoryStats = { sessions: number; messages: number; memories: number; firstSeen: number; relationship?: string };
type BackupInfo = { folderSelected: boolean; folderUri?: string; recoveryKey: string; lastBackup: number };

type NativeBridge = {
  nativeInfo(): string;
  modelCatalog(): string;
  modelStatus(modelId: string): string;
  startModelDownload(modelId: string): string;
  cancelModelDownload(modelId: string): string;
  deleteModel(modelId: string): void;
  selectModel(modelId: string): string;
  createSession(): string;
  listSessions(): string;
  loadSession(sessionId: string): string;
  deleteSession(sessionId: string): void;
  memoryStats(): string;
  generate(requestId: string, sessionId: string, userText: string, persona: string): void;
  stopGeneration(): void;
  backupInfo(): string;
  chooseBackupFolder(): void;
  backupNow(): void;
  chooseRestoreFile(): void;
  setRecoveryKey(key: string): void;
};

declare global {
  interface Window {
    FurinaNative?: NativeBridge;
    __furinaNativeReady?: () => void;
    __furinaNativeToken?: (requestId: string, chunk: string) => void;
    __furinaNativeDone?: (requestId: string, userId: string, assistantId: string) => void;
    __furinaNativeError?: (requestId: string, message: string) => void;
    __furinaNativeState?: (state: string, modelId: string, progress: number) => void;
    __furinaNativeBackup?: (success: boolean, message: string) => void;
    __furinaNativeRestored?: () => void;
  }
}

const PREF = {
  name: "furina:native:name",
  persona: "furina:native:persona",
  autoVoice: "furina:native:autoVoice",
  speed: "furina:native:voiceSpeed",
};

function parseJson<T>(raw: string | undefined, fallback: T): T {
  try { return raw ? JSON.parse(raw) as T : fallback; } catch { return fallback; }
}

function formatBytes(bytes = 0) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** i).toFixed(i >= 3 ? 2 : 0)} ${units[i]}`;
}

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function FurinaNativeApp() {
  const tts = useServerFn(speakVoicevoxUrl);
  const [nativeReady, setNativeReady] = useState(false);
  const [models, setModels] = useState<NativeModel[]>([]);
  const [statuses, setStatuses] = useState<Record<string, ModelStatus>>({});
  const [selectedModel, setSelectedModel] = useState("");
  const [runtimeState, setRuntimeState] = useState("idle");
  const [runtimeProgress, setRuntimeProgress] = useState(0);
  const [sessions, setSessions] = useState<NativeSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [messages, setMessages] = useState<NativeMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [openSettings, setOpenSettings] = useState(false);
  const [openSessions, setOpenSessions] = useState(false);
  const [name, setName] = useState("Furina");
  const [persona, setPersona] = useState("");
  const [autoVoice, setAutoVoice] = useState(false);
  const [voiceSpeed, setVoiceSpeed] = useState(1.0);
  const [stats, setStats] = useState<MemoryStats>({ sessions: 0, messages: 0, memories: 0, firstSeen: 0 });
  const [backup, setBackup] = useState<BackupInfo>({ folderSelected: false, recoveryKey: "", lastBackup: 0 });
  const [recoveryDraft, setRecoveryDraft] = useState("");
  const [playingId, setPlayingId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const requestRef = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const activeSessionRef = useRef("");

  const bridge = () => typeof window !== "undefined" ? window.FurinaNative : undefined;

  const refreshStats = useCallback(() => {
    const b = bridge();
    if (!b) return;
    setStats(parseJson<MemoryStats>(b.memoryStats(), { sessions: 0, messages: 0, memories: 0, firstSeen: 0 }));
    const bi = parseJson<BackupInfo>(b.backupInfo(), { folderSelected: false, recoveryKey: "", lastBackup: 0 });
    setBackup(bi);
    setRecoveryDraft(bi.recoveryKey || "");
  }, []);

  const refreshSessions = useCallback((preferred?: string) => {
    const b = bridge();
    if (!b) return;
    let list = parseJson<NativeSession[]>(b.listSessions(), []);
    if (!list.length) {
      const created = parseJson<NativeSession>(b.createSession(), { id: "", title: "Percakapan baru", createdAt: Date.now() });
      if (created.id) list = [created];
    }
    setSessions(list);
    const next = preferred && list.some((s) => s.id === preferred) ? preferred : (activeSessionRef.current && list.some((s) => s.id === activeSessionRef.current) ? activeSessionRef.current : list[0]?.id || "");
    if (next) {
      activeSessionRef.current = next;
      setActiveSessionId(next);
      setMessages(parseJson<NativeMessage[]>(b.loadSession(next), []));
    }
  }, []);

  const refreshModels = useCallback(() => {
    const b = bridge();
    if (!b) return;
    const catalog = parseJson<NativeModel[]>(b.modelCatalog(), []);
    setModels(catalog);
    const info = parseJson<{ selectedModelId?: string }>(b.nativeInfo(), {});
    if (info.selectedModelId) setSelectedModel(info.selectedModelId);
    const next: Record<string, ModelStatus> = {};
    catalog.forEach((m) => { next[m.id] = parseJson<ModelStatus>(b.modelStatus(m.id), { state: "unknown" }); });
    setStatuses(next);
  }, []);

  const initialize = useCallback(() => {
    const b = bridge();
    if (!b) return;
    setNativeReady(true);
    refreshModels();
    refreshSessions();
    refreshStats();
  }, [refreshModels, refreshSessions, refreshStats]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setName(localStorage.getItem(PREF.name) || "Furina");
    setPersona(localStorage.getItem(PREF.persona) || "");
    setAutoVoice(localStorage.getItem(PREF.autoVoice) === "1");
    setVoiceSpeed(Number(localStorage.getItem(PREF.speed) || 1));

    window.__furinaNativeReady = initialize;
    window.__furinaNativeToken = (requestId, chunk) => {
      if (requestRef.current !== requestId) return;
      const pendingId = `pending:${requestId}`;
      setMessages((prev) => prev.map((m) => m.id === pendingId ? { ...m, content: m.content + chunk } : m));
    };
    window.__furinaNativeDone = (requestId) => {
      if (requestRef.current !== requestId) return;
      requestRef.current = null;
      setSending(false);
      refreshSessions(activeSessionRef.current);
      refreshStats();
    };
    window.__furinaNativeError = (requestId, message) => {
      if (requestRef.current === requestId) {
        requestRef.current = null;
        setSending(false);
        setMessages((prev) => prev.filter((m) => m.id !== `pending:${requestId}`));
      }
      toast.error(message);
    };
    window.__furinaNativeState = (state, _modelId, progress) => {
      setRuntimeState(state);
      setRuntimeProgress(progress || 0);
    };
    window.__furinaNativeBackup = (success, message) => {
      success ? toast.success(message) : toast.error(message);
      refreshStats();
    };
    window.__furinaNativeRestored = () => {
      refreshSessions();
      refreshStats();
    };

    initialize();
    return () => {
      delete window.__furinaNativeReady;
      delete window.__furinaNativeToken;
      delete window.__furinaNativeDone;
      delete window.__furinaNativeError;
      delete window.__furinaNativeState;
      delete window.__furinaNativeBackup;
      delete window.__furinaNativeRestored;
    };
  }, [initialize, refreshSessions, refreshStats]);

  useEffect(() => {
    if (!nativeReady || !models.length) return;
    const timer = window.setInterval(refreshModels, 1300);
    return () => window.clearInterval(timer);
  }, [nativeReady, models.length, refreshModels]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const selectedStatus = statuses[selectedModel];
  const canSend = nativeReady && selectedStatus?.state === "ready" && !sending && input.trim().length > 0;

  async function send() {
    const text = input.trim();
    const b = bridge();
    if (!b || !activeSessionId || !text || sending) return;
    if (statuses[selectedModel]?.state !== "ready") {
      toast.error("Unduh dan pilih model AI terlebih dahulu.");
      setOpenSettings(true);
      return;
    }
    const requestId = crypto.randomUUID();
    requestRef.current = requestId;
    setInput("");
    setSending(true);
    const now = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: `local-user:${requestId}`, role: "user", content: text, createdAt: now },
      { id: `pending:${requestId}`, role: "assistant", content: "", createdAt: now + 1 },
    ]);
    b.generate(requestId, activeSessionId, text, persona);
  }

  function newSession() {
    const b = bridge();
    if (!b || sending) return;
    const created = parseJson<NativeSession>(b.createSession(), { id: "", title: "Percakapan baru", createdAt: Date.now() });
    if (!created.id) return;
    activeSessionRef.current = created.id;
    setActiveSessionId(created.id);
    setMessages([]);
    setSessions((prev) => [created, ...prev]);
    setOpenSessions(false);
  }

  function selectSession(id: string) {
    if (sending) return;
    const b = bridge();
    if (!b) return;
    activeSessionRef.current = id;
    setActiveSessionId(id);
    setMessages(parseJson<NativeMessage[]>(b.loadSession(id), []));
    setOpenSessions(false);
  }

  async function playVoice(message: NativeMessage) {
    if (playingId === message.id) {
      audioRef.current?.pause();
      audioRef.current = null;
      setPlayingId(null);
      return;
    }
    try {
      const clean = message.content.replace(/\*[^*]+\*/g, "").trim();
      if (!clean) return;
      setPlayingId(message.id);
      const { mp3Url } = await tts({ data: { text: clean.slice(0, 1000), speaker: 14, speed: voiceSpeed, translateToJa: true } });
      const audio = new Audio(mp3Url);
      audioRef.current = audio;
      audio.onended = () => { setPlayingId(null); audioRef.current = null; };
      audio.onerror = () => { setPlayingId(null); audioRef.current = null; };
      await audio.play();
    } catch (e) {
      setPlayingId(null);
      toast.error(e instanceof Error ? e.message : "Suara gagal diputar");
    }
  }

  useEffect(() => {
    if (!autoVoice || sending) return;
    const last = messages[messages.length - 1];
    if (last?.role === "assistant" && last.content && !last.id.startsWith("pending:")) playVoice(last);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, sending, autoVoice]);

  const statusText = useMemo(() => {
    if (!nativeReady) return "Buka halaman ini melalui APK Furina untuk AI lokal.";
    if (runtimeState === "verifying" || selectedStatus?.state === "verifying") return `Memverifikasi model… ${Math.round((selectedStatus?.progress ?? runtimeProgress) * 100)}%`;
    if (runtimeState === "loading" || runtimeState === "preparing") return "Menyiapkan model lokal…";
    if (runtimeState === "thinking") return `${name} sedang berpikir…`;
    if (selectedStatus?.state === "ready") return "AI lokal siap";
    return "Model belum diunduh";
  }, [nativeReady, runtimeState, runtimeProgress, selectedStatus?.state, name]);

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-[#050712] text-white">
      <img src={furinaDefault} alt="Furina" className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <div className="absolute inset-0 bg-gradient-to-b from-[#050712]/25 via-[#050712]/35 to-[#050712]/90" />

      <header className="absolute inset-x-0 top-0 z-30 flex h-16 items-center justify-between border-b border-white/10 bg-[#050712]/65 px-3 backdrop-blur-xl">
        <Button variant="ghost" size="icon" className="text-white" onClick={() => setOpenSessions(true)}>
          <MessagesSquare className="h-5 w-5" />
        </Button>
        <div className="min-w-0 text-center">
          <p className="truncate text-sm font-semibold">{name}</p>
          <p className="text-[10px] text-white/60">{statusText}</p>
        </div>
        <Button variant="ghost" size="icon" className="text-white" onClick={() => setOpenSettings(true)}>
          <Settings className="h-5 w-5" />
        </Button>
      </header>

      <main ref={scrollRef} className="absolute inset-0 z-10 overflow-y-auto px-3 pb-32 pt-20">
        <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-3">
          {messages.length === 0 && (
            <div className="mt-auto mb-3 max-w-[88%] rounded-2xl border border-white/10 bg-[#0c1022]/85 px-4 py-3 text-sm shadow-xl backdrop-blur-md">
              Halo… akhirnya kamu datang juga. Aku {name}. Sesi boleh baru, tapi aku tidak perlu melupakan yang lama.
            </div>
          )}
          <div className="mt-auto" />
          {messages.map((m) => {
            const user = m.role === "user";
            const pending = m.id.startsWith("pending:");
            return (
              <div key={m.id} className={`flex flex-col ${user ? "items-end" : "items-start"}`}>
                <div className={`max-w-[90%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-lg ${user ? "bg-sky-600/90 text-white" : "border border-white/10 bg-[#0c1022]/88 text-white backdrop-blur-md"}`}>
                  {pending && !m.content ? <Loader2 className="h-4 w-4 animate-spin text-white/60" /> : <div className="whitespace-pre-wrap break-words">{m.content}</div>}
                </div>
                <div className="mt-1 flex items-center gap-1.5 px-1 text-[10px] text-white/55">
                  <span>{fmtTime(m.createdAt)}</span>
                  {!user && !pending && (
                    <button className="rounded-full p-1 hover:bg-white/10" onClick={() => playVoice(m)} aria-label="Putar suara">
                      {playingId === m.id ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </main>

      <div className="absolute inset-x-0 bottom-0 z-30 border-t border-white/10 bg-[#050712]/80 p-3 pb-[max(12px,env(safe-area-inset-bottom))] backdrop-blur-xl">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (canSend) send(); } }}
            placeholder={selectedStatus?.state === "ready" ? "Ketik pesan…" : "Unduh model AI dari Pengaturan…"}
            rows={1}
            className="max-h-32 min-h-11 resize-none border-white/15 bg-white/8 text-white placeholder:text-white/45"
          />
          {sending ? (
            <Button size="icon" variant="secondary" className="shrink-0" aria-label="Hentikan jawaban" onClick={() => bridge()?.stopGeneration()}><Square className="h-4 w-4" /></Button>
          ) : (
            <Button size="icon" className="shrink-0" disabled={!canSend} onClick={send}><Send className="h-4 w-4" /></Button>
          )}
        </div>
      </div>

      <Sheet open={openSessions} onOpenChange={setOpenSessions}>
        <SheetContent side="left" className="w-[88vw] max-w-sm overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Percakapan</SheetTitle>
            <SheetDescription>Sesi hanya mengelompokkan tampilan. Memori Furina tetap global.</SheetDescription>
          </SheetHeader>
          <Button className="mt-4 w-full" onClick={newSession} disabled={sending}><MessageSquarePlus className="mr-2 h-4 w-4" /> Percakapan baru</Button>
          <div className="mt-3 space-y-1">
            {sessions.map((s) => (
              <div key={s.id} className={`flex items-center gap-1 rounded-lg border p-2 ${s.id === activeSessionId ? "bg-muted" : ""}`}>
                <button onClick={() => selectSession(s.id)} className="min-w-0 flex-1 text-left">
                  <p className="truncate text-sm font-medium">{s.title}</p>
                  <p className="text-[10px] text-muted-foreground">{s.messageCount ?? 0} pesan</p>
                </button>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => {
                  if (!confirm("Hapus sesi ini? Memori penting lintas-sesi tetap ada.")) return;
                  bridge()?.deleteSession(s.id);
                  refreshSessions(s.id === activeSessionId ? undefined : activeSessionId);
                  refreshStats();
                }}><Trash2 className="h-3.5 w-3.5" /></Button>
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>

      <Sheet open={openSettings} onOpenChange={setOpenSettings}>
        <SheetContent side="right" className="w-[94vw] max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Pengaturan</SheetTitle>
            <SheetDescription>Karakter, mesin AI lokal, suara, memori, dan backup.</SheetDescription>
          </SheetHeader>

          <div className="mt-5 space-y-6 pb-10">
            <section className="space-y-2">
              <Label>Nama karakter</Label>
              <Input value={name} onChange={(e) => { setName(e.target.value); localStorage.setItem(PREF.name, e.target.value); }} />
            </section>

            <section className="space-y-2">
              <Label>Kepribadian / system prompt (opsional)</Label>
              <Textarea rows={5} value={persona} placeholder="Kosongkan untuk kepribadian Furina default…" onChange={(e) => {
                setPersona(e.target.value); localStorage.setItem(PREF.persona, e.target.value);
              }} />
              <p className="text-[11px] text-muted-foreground">Perubahan persona diterapkan saat model dimuat ulang. Persona, memori, dan riwayat dipisahkan dari file model.</p>
            </section>

            <section className="space-y-3 rounded-xl border p-3">
              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4" />
                <div>
                  <Label>Mesin AI lokal</Label>
                  <p className="text-[11px] text-muted-foreground">Dua model Qwen uncensored Q4_K_M. Gemma tidak digunakan.</p>
                </div>
              </div>

              {!nativeReady && <div className="rounded-lg bg-destructive/10 p-2 text-xs text-destructive">Menu download hanya aktif di APK Furina.</div>}

              {models.map((model) => {
                const st = statuses[model.id] ?? { state: "not_downloaded" as const };
                const total = st.totalBytes || model.expectedBytes;
                const progress = Math.max(0, Math.min(1, st.progress || 0));
                const selected = selectedModel === model.id;
                return (
                  <div key={model.id} className={`rounded-xl border p-3 ${selected ? "border-primary bg-primary/5" : ""}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold">{model.name} {model.recommended && <span className="ml-1 text-[10px] text-primary">REKOMENDASI</span>}</p>
                        <p className="text-[11px] text-muted-foreground">{model.subtitle} · ±{formatBytes(model.expectedBytes)}</p>
                      </div>
                      {selected && <Check className="h-4 w-4 shrink-0 text-primary" />}
                    </div>

                    {(st.state === "downloading" || st.state === "paused" || st.state === "verifying") && (
                      <div className="mt-3 space-y-1">
                        <div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-[width] duration-300" style={{ width: `${progress * 100}%` }} /></div>
                        <p className="text-[10px] text-muted-foreground">{st.state === "verifying" ? `Memverifikasi integritas… ${Math.round(progress * 100)}%` : `${formatBytes(st.downloadedBytes)} / ${formatBytes(total)} · unduhan berjalan di latar belakang`}</p>
                      </div>
                    )}

                    <div className="mt-3 flex flex-wrap gap-2">
                      {st.state === "ready" ? (
                        <>
                          <Button size="sm" variant={selected ? "secondary" : "default"} onClick={() => {
                            bridge()?.selectModel(model.id); setSelectedModel(model.id); refreshModels();
                          }}>{selected ? "Dipilih" : "Gunakan model"}</Button>
                          <Button size="sm" variant="outline" onClick={() => bridge()?.deleteModel(model.id)}><Trash2 className="mr-1 h-3.5 w-3.5" /> Hapus</Button>
                        </>
                      ) : st.state === "downloading" || st.state === "paused" ? (
                        <Button size="sm" variant="outline" onClick={() => bridge()?.cancelModelDownload(model.id)}><X className="mr-1 h-3.5 w-3.5" /> Batalkan</Button>
                      ) : st.state === "verifying" ? (
                        <Button size="sm" variant="secondary" disabled><Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> Memverifikasi</Button>
                      ) : (
                        <Button size="sm" disabled={!nativeReady} onClick={() => { bridge()?.startModelDownload(model.id); refreshModels(); }}>
                          <Download className="mr-1 h-3.5 w-3.5" /> Download
                        </Button>
                      )}
                    </div>
                    {st.state === "failed" && <p className="mt-2 text-[10px] text-destructive">Download gagal (kode {st.reason ?? "?"}). Coba unduh ulang.</p>}
                    {st.state === "corrupt" && <p className="mt-2 text-[10px] text-destructive">File model tidak utuh atau checksum salah. Hapus lalu unduh ulang.</p>}
                    {model.id.includes("9b") && <p className="mt-2 text-[10px] text-muted-foreground">9B memerlukan RAM jauh lebih besar. Jika Android menutup aplikasi atau respons terlalu lambat, kembali ke 4B.</p>}
                  </div>
                );
              })}

              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Runtime memakai llama.cpp native Android. Model tetap dimuat selama sesi aktif, token di-stream dan digabung sebelum update UI untuk mengurangi latency serta kedipan layar.
              </p>
            </section>

            <section className="space-y-3">
              <Label>Mesin suara (TTS)</Label>
              <div className="rounded-lg border p-3 text-xs">
                <p className="font-medium">VOICEVOX — 冥鳴ひまり</p>
                <p className="mt-1 text-muted-foreground">TTS tetap online; otak percakapan Qwen berjalan lokal.</p>
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-xs">Putar suara otomatis</Label>
                <Switch checked={autoVoice} onCheckedChange={(v) => { setAutoVoice(v); localStorage.setItem(PREF.autoVoice, v ? "1" : "0"); }} />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-xs"><span>Kecepatan bicara</span><span>{voiceSpeed.toFixed(2)}x</span></div>
                <Slider min={0.75} max={1.35} step={0.05} value={[voiceSpeed]} onValueChange={(v) => {
                  const next = v[0] ?? 1; setVoiceSpeed(next); localStorage.setItem(PREF.speed, String(next));
                }} />
              </div>
            </section>

            <section className="space-y-3 rounded-xl border p-3">
              <div className="flex items-center gap-2"><HardDrive className="h-4 w-4" /><Label>Memory & Data</Label></div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-muted p-2"><p className="text-lg font-semibold">{stats.messages}</p><p className="text-[10px] text-muted-foreground">pesan</p></div>
                <div className="rounded-lg bg-muted p-2"><p className="text-lg font-semibold">{stats.sessions}</p><p className="text-[10px] text-muted-foreground">sesi</p></div>
                <div className="rounded-lg bg-muted p-2"><p className="text-lg font-semibold">{stats.memories}</p><p className="text-[10px] text-muted-foreground">memori fakta</p></div>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">Semua pesan disimpan utuh di SQLite. Sesi baru tidak mereset hubungan. Saat model dimuat ulang, Furina mengambil percakapan lama yang relevan tanpa memasukkan seluruh arsip ke context.</p>
              {stats.firstSeen > 0 && <p className="text-[11px]">Mengenalmu sejak <span className="font-medium">{new Date(stats.firstSeen).toLocaleDateString()}</span></p>}
            </section>

            <section className="space-y-3 rounded-xl border p-3">
              <div className="flex items-center gap-2"><Cloud className="h-4 w-4" /><Label>Backup Google / Cloud</Label></div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">Pilih folder melalui pemilih file Android. Kamu bisa memilih Google Drive jika tersedia. Backup SQLite dienkripsi dan dibuat otomatis berkala setelah percakapan.</p>
              <Button variant="outline" className="w-full" onClick={() => bridge()?.chooseBackupFolder()}>
                <Cloud className="mr-2 h-4 w-4" /> {backup.folderSelected ? "Ganti folder backup" : "Pilih folder Google Drive"}
              </Button>
              <div className="space-y-1">
                <Label className="text-xs">Recovery key</Label>
                <div className="flex gap-2">
                  <Input value={recoveryDraft} onChange={(e) => setRecoveryDraft(e.target.value)} className="font-mono text-[11px]" />
                  <Button variant="outline" size="icon" onClick={async () => {
                    await navigator.clipboard.writeText(recoveryDraft); toast.success("Recovery key disalin");
                  }}><Copy className="h-4 w-4" /></Button>
                </div>
                <p className="text-[10px] text-muted-foreground">Simpan key ini. HP baru membutuhkannya untuk membuka backup terenkripsi.</p>
                {recoveryDraft !== backup.recoveryKey && <Button size="sm" variant="outline" onClick={() => bridge()?.setRecoveryKey(recoveryDraft)}>Gunakan key ini</Button>}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button disabled={!backup.folderSelected} onClick={() => bridge()?.backupNow()}>Backup sekarang</Button>
                <Button variant="outline" onClick={() => bridge()?.chooseRestoreFile()}>Restore backup</Button>
              </div>
              {backup.lastBackup > 0 && <p className="text-[10px] text-muted-foreground">Backup terakhir: {new Date(backup.lastBackup).toLocaleString()}</p>}
            </section>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
