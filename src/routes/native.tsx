import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle, Brain, Check, Cloud, Copy, Download, HardDrive, Image as ImageIcon, Loader2,
  MessageSquarePlus, MessagesSquare, Moon, Play, Plus, RotateCcw, Send,
  Settings, Sparkles, Square, Sun, Trash2, Volume2, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import furinaDefault from "@/assets/furina.jpg";
import { speakClone, speakVoicevoxUrl } from "@/lib/furina.functions";

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
  error?: string;
};
type NativeMessage = { id: string; role: "user" | "assistant"; content: string; createdAt: number };
type NativeSession = { id: string; title: string; createdAt: number; updatedAt?: number; messageCount?: number };
type MemoryStats = { sessions: number; messages: number; memories: number; firstSeen: number; relationship?: string };
type BackupInfo = { folderSelected: boolean; folderUri?: string; recoveryKey: string; lastBackup: number };
type GenerationMetrics = { firstTokenMs: number; tokensPerSecond: number; tokenCount: number; warmStart: boolean };
type MemoryItem = { id: string; content: string; kind?: string; importance?: number; createdAt?: number; updatedAt?: number };
type ThemeMode = "dark" | "light";
type ReplyLanguage = "auto" | "ja" | "en" | "id";
type TTSProvider = "voicevox" | "clone";

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
  clearSession(sessionId: string): void;
  memoryStats(): string;
  listMemories(): string;
  addMemory(content: string): string;
  deleteMemory(memoryId: string): void;
  clearMemories(): void;
  appSettings(): string;
  saveAppSettings(settingsJson: string): void;
  setSystemTheme(dark: boolean): void;
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
    __furinaNativeDone?: (requestId: string, userId: string, assistantId: string, metrics?: GenerationMetrics) => void;
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
  theme: "furina:native:theme",
  language: "furina:native:language",
  provider: "furina:native:ttsProvider",
  vvSpeaker: "furina:native:vvSpeaker",
  vvTranslate: "furina:native:vvTranslate",
  preGen: "furina:native:preGenAudio",
  background: "furina:native:background",
  cloneSample: "furina:native:cloneSample",
  cloneSampleMime: "furina:native:cloneSampleMime",
  cloneSampleName: "furina:native:cloneSampleName",
};

type CompanionSettings = {
  name?: string;
  persona?: string;
  autoVoice?: boolean;
  voiceSpeed?: number;
  theme?: ThemeMode;
  language?: ReplyLanguage;
  ttsProvider?: TTSProvider;
  vvSpeaker?: number;
  vvTranslate?: boolean;
  preGenAudio?: boolean;
};

const VV_SPEAKERS = [
  { id: 14, label: "★ Rekomendasi Furina — 冥鳴ひまり (ノーマル, anggun)" },
  { id: 8, label: "春日部つむぎ — ノーマル (cerah, energik)" },
  { id: 20, label: "もち子さん — ノーマル (hangat lembut)" },
  { id: 2, label: "四国めたん — ノーマル (manis muda)" },
  { id: 0, label: "四国めたん — あまあま (manja)" },
  { id: 6, label: "四国めたん — ツンツン (tsundere)" },
  { id: 9, label: "波音リツ — ノーマル (dewasa kalem)" },
  { id: 10, label: "雨晴はう — ノーマル (lembut tenang)" },
  { id: 3, label: "ずんだもん — ノーマル (imut ceria)" },
  { id: 7, label: "ずんだもん — ツンツン" },
  { id: 23, label: "WhiteCUL — ノーマル (manis polos)" },
  { id: 27, label: "九州そら — ノーマル (anggun dewasa)" },
  { id: 29, label: "九州そら — あまあま" },
];

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
  const ttsClone = useServerFn(speakClone);
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
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [language, setLanguage] = useState<ReplyLanguage>("auto");
  const [ttsProvider, setTtsProvider] = useState<TTSProvider>("voicevox");
  const [vvSpeaker, setVvSpeaker] = useState(14);
  const [vvTranslate, setVvTranslate] = useState(true);
  const [preGenAudio, setPreGenAudio] = useState(true);
  const [background, setBackground] = useState<string>(furinaDefault);
  const [cloneSampleName, setCloneSampleName] = useState("");
  const [hasCloneSample, setHasCloneSample] = useState(false);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [newMemory, setNewMemory] = useState("");
  const [stats, setStats] = useState<MemoryStats>({ sessions: 0, messages: 0, memories: 0, firstSeen: 0 });
  const [backup, setBackup] = useState<BackupInfo>({ folderSelected: false, recoveryKey: "", lastBackup: 0 });
  const [recoveryDraft, setRecoveryDraft] = useState("");
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [lastMetrics, setLastMetrics] = useState<GenerationMetrics | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const settingsScrollRef = useRef<HTMLDivElement | null>(null);
  const requestRef = useRef<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const backgroundInputRef = useRef<HTMLInputElement | null>(null);
  const preparedAudioRef = useRef<Map<string, string>>(new Map());
  const preparingAudioRef = useRef<Set<string>>(new Set());
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

  const refreshMemories = useCallback(() => {
    const b = bridge();
    if (!b) return;
    setMemories(parseJson<MemoryItem[]>(b.listMemories(), []));
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
    const saved = parseJson<CompanionSettings>(b.appSettings(), {});
    if (saved.name) setName(saved.name);
    if (typeof saved.persona === "string") setPersona(saved.persona);
    if (typeof saved.autoVoice === "boolean") setAutoVoice(saved.autoVoice);
    if (typeof saved.voiceSpeed === "number") setVoiceSpeed(saved.voiceSpeed);
    if (saved.theme === "dark" || saved.theme === "light") setTheme(saved.theme);
    if (saved.language) setLanguage(saved.language);
    if (saved.ttsProvider) setTtsProvider(saved.ttsProvider);
    if (typeof saved.vvSpeaker === "number") setVvSpeaker(saved.vvSpeaker);
    if (typeof saved.vvTranslate === "boolean") setVvTranslate(saved.vvTranslate);
    if (typeof saved.preGenAudio === "boolean") setPreGenAudio(saved.preGenAudio);
    setNativeReady(true);
    refreshModels();
    refreshSessions();
    refreshStats();
    refreshMemories();
  }, [refreshMemories, refreshModels, refreshSessions, refreshStats]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setName(localStorage.getItem(PREF.name) || "Furina");
    setPersona(localStorage.getItem(PREF.persona) || "");
    setAutoVoice(localStorage.getItem(PREF.autoVoice) === "1");
    setVoiceSpeed(Number(localStorage.getItem(PREF.speed) || 1));
    setTheme((localStorage.getItem(PREF.theme) as ThemeMode) || "dark");
    setLanguage((localStorage.getItem(PREF.language) as ReplyLanguage) || "auto");
    setTtsProvider((localStorage.getItem(PREF.provider) as TTSProvider) || "voicevox");
    setVvSpeaker(Number(localStorage.getItem(PREF.vvSpeaker) || 14));
    setVvTranslate(localStorage.getItem(PREF.vvTranslate) !== "0");
    setPreGenAudio(localStorage.getItem(PREF.preGen) !== "0");
    setBackground(localStorage.getItem(PREF.background) || furinaDefault);
    setCloneSampleName(localStorage.getItem(PREF.cloneSampleName) || "");
    setHasCloneSample(Boolean(localStorage.getItem(PREF.cloneSample)));

    window.__furinaNativeReady = initialize;
    window.__furinaNativeToken = (requestId, chunk) => {
      if (requestRef.current !== requestId) return;
      const pendingId = `pending:${requestId}`;
      setMessages((prev) => prev.map((m) => m.id === pendingId ? { ...m, content: m.content + chunk } : m));
    };
    window.__furinaNativeDone = (requestId, _userId, _assistantId, metrics) => {
      if (requestRef.current !== requestId) return;
      requestRef.current = null;
      setSending(false);
      if (metrics) setLastMetrics(metrics);
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
      const restored = parseJson<CompanionSettings>(bridge()?.appSettings(), {});
      if (restored.name) setName(restored.name);
      if (typeof restored.persona === "string") setPersona(restored.persona);
      if (typeof restored.autoVoice === "boolean") setAutoVoice(restored.autoVoice);
      if (typeof restored.voiceSpeed === "number") setVoiceSpeed(restored.voiceSpeed);
      if (restored.theme) setTheme(restored.theme);
      if (restored.language) setLanguage(restored.language);
      if (restored.ttsProvider) setTtsProvider(restored.ttsProvider);
      if (typeof restored.vvSpeaker === "number") setVvSpeaker(restored.vvSpeaker);
      if (typeof restored.vvTranslate === "boolean") setVvTranslate(restored.vvTranslate);
      if (typeof restored.preGenAudio === "boolean") setPreGenAudio(restored.preGenAudio);
      refreshSessions();
      refreshStats();
      refreshMemories();
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
  }, [initialize, refreshMemories, refreshSessions, refreshStats]);

  useEffect(() => {
    if (!nativeReady) return;
    const settings = { name, persona, autoVoice, voiceSpeed, theme, language, ttsProvider, vvSpeaker, vvTranslate, preGenAudio };
    localStorage.setItem(PREF.name, name);
    localStorage.setItem(PREF.persona, persona);
    localStorage.setItem(PREF.autoVoice, autoVoice ? "1" : "0");
    localStorage.setItem(PREF.speed, String(voiceSpeed));
    localStorage.setItem(PREF.theme, theme);
    localStorage.setItem(PREF.language, language);
    localStorage.setItem(PREF.provider, ttsProvider);
    localStorage.setItem(PREF.vvSpeaker, String(vvSpeaker));
    localStorage.setItem(PREF.vvTranslate, vvTranslate ? "1" : "0");
    localStorage.setItem(PREF.preGen, preGenAudio ? "1" : "0");
    bridge()?.saveAppSettings(JSON.stringify(settings));
  }, [nativeReady, name, persona, autoVoice, voiceSpeed, theme, language, ttsProvider, vvSpeaker, vvTranslate, preGenAudio]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
    bridge()?.setSystemTheme(theme === "dark");
  }, [theme, nativeReady]);

  useEffect(() => {
    if (!nativeReady || !models.length) return;
    const timer = window.setInterval(refreshModels, 1300);
    return () => window.clearInterval(timer);
  }, [nativeReady, models.length, refreshModels]);

  useEffect(() => {
    if (!openSettings) return;
    const frame = window.requestAnimationFrame(() => settingsScrollRef.current?.scrollTo({ top: 0 }));
    return () => window.cancelAnimationFrame(frame);
  }, [openSettings]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const selectedStatus = statuses[selectedModel];
  const canSend = nativeReady && selectedStatus?.state === "ready" && !sending && input.trim().length > 0;

  useEffect(() => {
    preparedAudioRef.current.clear();
  }, [ttsProvider, voiceSpeed, vvSpeaker, vvTranslate]);

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
    const languageInstruction: Record<ReplyLanguage, string> = {
      auto: "",
      ja: "Always reply in Japanese unless the user explicitly requests another language.",
      en: "Always reply in English unless the user explicitly requests another language.",
      id: "Selalu balas dalam bahasa Indonesia kecuali pengguna secara eksplisit meminta bahasa lain.",
    };
    b.generate(requestId, activeSessionId, text, [persona, languageInstruction[language]].filter(Boolean).join("\n\n"));
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

  function startDownload(model: NativeModel) {
    const b = bridge();
    if (!b) {
      toast.error("Download model hanya tersedia di APK Furina.");
      return;
    }
    setStatuses((current) => ({
      ...current,
      [model.id]: {
        ...(current[model.id] ?? {}),
        id: model.id,
        state: "downloading",
        downloadedBytes: 0,
        totalBytes: model.expectedBytes,
        progress: 0,
      },
    }));
    try {
      b.startModelDownload(model.id);
      toast.success(`Download ${model.name} dimulai di latar belakang`);
      window.setTimeout(refreshModels, 350);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Download model gagal dimulai.");
      refreshModels();
    }
  }

  const prepareVoice = useCallback(async (message: NativeMessage) => {
    const cached = preparedAudioRef.current.get(message.id);
    if (cached) return cached;
    if (preparingAudioRef.current.has(message.id)) return null;
    const clean = message.content.replace(/\*[^*]+\*/g, "").trim();
    if (!clean) return null;
    preparingAudioRef.current.add(message.id);
    try {
      let source: string;
      if (ttsProvider === "voicevox") {
        const { mp3Url } = await tts({
          data: { text: clean.slice(0, 1000), speaker: vvSpeaker, speed: voiceSpeed, translateToJa: vvTranslate },
        });
        source = mp3Url;
      } else {
        const sampleBase64 = localStorage.getItem(PREF.cloneSample);
        const sampleMime = localStorage.getItem(PREF.cloneSampleMime) || "audio/wav";
        if (!sampleBase64) throw new Error("Belum ada sampel suara. Upload sampel di Pengaturan.");
        const { audio, mime } = await ttsClone({
          data: { text: clean.slice(0, 600), sampleBase64, sampleMime, language: "ja", translateToJa: vvTranslate },
        });
        source = `data:${mime};base64,${audio}`;
      }
      preparedAudioRef.current.set(message.id, source);
      return source;
    } finally {
      preparingAudioRef.current.delete(message.id);
    }
  }, [tts, ttsClone, ttsProvider, voiceSpeed, vvSpeaker, vvTranslate]);

  async function playVoice(message: NativeMessage) {
    if (playingId === message.id) {
      audioRef.current?.pause();
      audioRef.current = null;
      setPlayingId(null);
      return;
    }
    try {
      setPlayingId(message.id);
      const source = await prepareVoice(message);
      if (!source) { setPlayingId(null); return; }
      const audio = new Audio(source);
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
    if (sending) return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant" || !last.content || last.id.startsWith("pending:")) return;
    if (autoVoice) playVoice(last);
    else if (preGenAudio) prepareVoice(last).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, sending, autoVoice, preGenAudio]);

  function handleBackgroundUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("File harus berupa gambar."); return; }
    if (file.size > 8 * 1024 * 1024) { toast.error("Gambar terlalu besar. Maksimal 8 MB."); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const source = String(reader.result);
      try {
        localStorage.setItem(PREF.background, source);
        setBackground(source);
        toast.success("Background karakter diperbarui");
      } catch {
        toast.error("Gambar terlalu besar untuk disimpan. Pilih gambar yang lebih kecil.");
      }
    };
    reader.readAsDataURL(file);
  }

  function handleCloneSampleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error("Sampel terlalu besar. Maksimal 5 MB."); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const data = String(reader.result);
      const base64 = data.slice(data.indexOf(",") + 1);
      try {
        localStorage.setItem(PREF.cloneSample, base64);
        localStorage.setItem(PREF.cloneSampleMime, file.type || "audio/wav");
        localStorage.setItem(PREF.cloneSampleName, file.name);
        setCloneSampleName(file.name);
        setHasCloneSample(true);
        preparedAudioRef.current.clear();
        toast.success("Sampel suara tersimpan");
      } catch { toast.error("Sampel gagal disimpan."); }
    };
    reader.readAsDataURL(file);
  }

  function clearCloneSample() {
    localStorage.removeItem(PREF.cloneSample);
    localStorage.removeItem(PREF.cloneSampleMime);
    localStorage.removeItem(PREF.cloneSampleName);
    preparedAudioRef.current.clear();
    setCloneSampleName("");
    setHasCloneSample(false);
  }

  const statusText = useMemo(() => {
    if (!nativeReady) return "Buka halaman ini melalui APK Furina untuk AI lokal.";
    if (runtimeState === "verifying" || selectedStatus?.state === "verifying") return `Memverifikasi model… ${Math.round((selectedStatus?.progress ?? runtimeProgress) * 100)}%`;
    if (runtimeState === "loading" || runtimeState === "preparing") return "Menyiapkan model lokal…";
    if (runtimeState === "thinking") return `${name} sedang berpikir…`;
    if (selectedStatus?.state === "ready") return "AI lokal siap";
    return "Model belum diunduh";
  }, [nativeReady, runtimeState, runtimeProgress, selectedStatus?.state, name]);

  return (
    <div className={`relative h-[100dvh] w-full overflow-hidden ${theme === "dark" ? "bg-[#050712] text-white" : "bg-slate-100 text-slate-950"}`}>
      <img src={background} alt={`${name} background`} className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <div className={`absolute inset-0 ${theme === "dark" ? "bg-gradient-to-b from-[#050712]/25 via-[#050712]/35 to-[#050712]/90" : "bg-gradient-to-b from-white/20 via-white/20 to-white/75"}`} />

      <header className={`absolute inset-x-0 top-0 z-30 flex h-16 items-center justify-between border-b px-3 shadow-sm backdrop-blur-xl ${theme === "dark" ? "border-white/10 bg-[#080c1b]/88 text-white" : "border-slate-200/80 bg-white/88 text-slate-950"}`}>
        <Button variant="ghost" size="icon" className="h-12 w-12 rounded-full" aria-label="Buka daftar percakapan" onClick={() => setOpenSessions(true)}>
          <MessagesSquare className="h-5 w-5" />
        </Button>
        <div className="min-w-0 text-center">
          <p className="truncate text-sm font-semibold">{name}</p>
          <p className={`text-[10px] ${theme === "dark" ? "text-white/60" : "text-slate-500"}`}>{statusText}</p>
        </div>
        <Button variant="ghost" size="icon" className="h-12 w-12 rounded-full" aria-label="Buka pengaturan" onClick={() => { setOpenSettings(true); refreshMemories(); }}>
          <Settings className="h-5 w-5" />
        </Button>
      </header>

      <main ref={scrollRef} className="absolute inset-0 z-10 overflow-y-auto px-3 pb-32 pt-20">
        <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-3">
          {messages.length === 0 && (
            <div className={`mt-auto mb-3 max-w-[88%] rounded-2xl border px-4 py-3 text-sm shadow-xl backdrop-blur-md ${theme === "dark" ? "border-white/10 bg-[#0c1022]/88 text-white" : "border-white/80 bg-white/88 text-slate-950"}`}>
              Halo… akhirnya kamu datang juga. Aku {name}. Sesi boleh baru, tapi aku tidak perlu melupakan yang lama.
            </div>
          )}
          <div className="mt-auto" />
          {messages.map((m) => {
            const user = m.role === "user";
            const pending = m.id.startsWith("pending:");
            return (
              <div key={m.id} className={`flex flex-col ${user ? "items-end" : "items-start"}`}>
                <div className={`max-w-[90%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-lg ${user ? "bg-sky-600/95 text-white" : theme === "dark" ? "border border-white/10 bg-[#0c1022]/88 text-white backdrop-blur-md" : "border border-white/80 bg-white/90 text-slate-950 backdrop-blur-md"}`}>
                  {pending && !m.content ? <Loader2 className="h-4 w-4 animate-spin opacity-60" /> : <div className="whitespace-pre-wrap break-words">{m.content}</div>}
                </div>
                <div className={`mt-1 flex items-center gap-1.5 px-1 text-[10px] ${theme === "dark" ? "text-white/55" : "text-slate-600"}`}>
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

      <div className={`absolute inset-x-0 bottom-0 z-30 border-t p-3 backdrop-blur-xl ${theme === "dark" ? "border-white/10 bg-[#080c1b]/92" : "border-slate-200/80 bg-white/92"}`}>
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (canSend) send(); } }}
            placeholder={selectedStatus?.state === "ready" ? "Ketik pesan…" : "Unduh model AI dari Pengaturan…"}
            rows={1}
            className={`max-h-32 min-h-12 resize-none rounded-2xl ${theme === "dark" ? "border-white/15 bg-white/8 text-white placeholder:text-white/45" : "border-slate-300 bg-white/80 text-slate-950 placeholder:text-slate-500"}`}
          />
          {sending ? (
            <Button size="icon" variant="secondary" className="h-11 w-11 shrink-0" aria-label="Hentikan jawaban" onClick={() => bridge()?.stopGeneration()}><Square className="h-4 w-4" /></Button>
          ) : (
            <Button size="icon" className="h-11 w-11 shrink-0" aria-label="Kirim pesan" disabled={!canSend} onClick={send}><Send className="h-4 w-4" /></Button>
          )}
        </div>
      </div>

      <Sheet open={openSessions} onOpenChange={setOpenSessions}>
        <SheetContent side="left" className={`w-full max-w-sm overflow-y-auto border-r ${theme === "dark" ? "border-slate-800 bg-[#050712] text-slate-100" : "border-slate-200 bg-white text-slate-950"}`}>
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
        <SheetContent side="right" className={`flex h-full w-full max-w-md flex-col gap-0 overflow-hidden border-l p-0 ${theme === "dark" ? "border-slate-800 bg-[#050712] text-slate-100" : "border-slate-200 bg-white text-slate-950"}`}>
          <SheetHeader className={`relative z-20 shrink-0 border-b px-5 pb-4 pt-5 text-left shadow-sm backdrop-blur-xl ${theme === "dark" ? "border-slate-800 bg-[#050712]/96" : "border-slate-200 bg-white/96"}`}>
            <SheetTitle className="pr-10 text-xl">Pengaturan</SheetTitle>
            <SheetDescription className="max-w-sm text-xs leading-relaxed">Personalisasi karakter, mesin AI lokal, suara, memori, dan backup.</SheetDescription>
          </SheetHeader>

          <div ref={settingsScrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-smooth px-4 py-5 touch-manipulation sm:px-6">
          <div className="space-y-6 pb-8 motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-300">
            <section className="space-y-3 rounded-xl border bg-muted/30 p-4">
              <Label className="text-xs font-semibold uppercase tracking-wider">Tampilan</Label>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm">Tema</span>
                <Button size="sm" variant="outline" onClick={() => setTheme((value) => value === "dark" ? "light" : "dark")}>
                  {theme === "dark" ? <><Sun className="mr-2 h-4 w-4" />Terang</> : <><Moon className="mr-2 h-4 w-4" />Gelap</>}
                </Button>
              </div>
            </section>

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

            <section className="space-y-4 rounded-2xl border bg-muted/10 p-4 shadow-sm">
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
                  <div key={model.id} className={`rounded-2xl border bg-background/35 p-4 shadow-sm transition-[border-color,background-color,box-shadow,transform] duration-200 ease-out active:scale-[0.995] motion-reduce:transition-none ${selected ? "border-primary/80 bg-primary/5 shadow-primary/5" : "hover:border-foreground/20"}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-[15px] font-semibold leading-snug">{model.name} {model.recommended && <span className="ml-1 inline-flex rounded-full bg-primary/10 px-2 py-0.5 align-middle text-[9px] font-semibold tracking-wide text-primary">REKOMENDASI</span>}</p>
                        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{model.subtitle} · ±{formatBytes(model.expectedBytes)}</p>
                      </div>
                      {selected && <Check className="h-4 w-4 shrink-0 text-primary" />}
                    </div>

                    {(st.state === "downloading" || st.state === "paused" || st.state === "verifying") && (
                      <div className="mt-3 space-y-1">
                        <div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full origin-left scale-x-0 rounded-full bg-primary transition-transform duration-300 ease-out motion-reduce:transition-none" style={{ transform: `scaleX(${progress})` }} /></div>
                        <p role="status" className="text-[10px] tabular-nums text-muted-foreground">{st.state === "verifying" ? `Memverifikasi integritas… ${Math.round(progress * 100)}%` : `${formatBytes(st.downloadedBytes)} / ${formatBytes(total)} · unduhan berjalan di latar belakang`}</p>
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
                        <Button size="sm" className="min-h-11 rounded-xl px-4 transition-transform duration-150 active:scale-[0.97] motion-reduce:transition-none" disabled={!nativeReady} onClick={() => startDownload(model)}>
                          <Download className="mr-1.5 h-4 w-4" /> {st.state === "corrupt" || st.state === "failed" ? "Unduh ulang" : "Download"}
                        </Button>
                      )}
                    </div>
                    {st.state === "failed" && <p role="alert" className="mt-3 flex items-start gap-1.5 rounded-lg bg-destructive/10 p-2.5 text-[11px] leading-relaxed text-destructive"><AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />Download terhenti (kode {st.reason ?? "?"}). Tekan Unduh ulang untuk membersihkan file sementara dan melanjutkan dari awal.</p>}
                    {st.state === "corrupt" && <p role="alert" className="mt-3 flex items-start gap-1.5 rounded-lg bg-destructive/10 p-2.5 text-[11px] leading-relaxed text-destructive"><AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />File belum utuh atau gagal diverifikasi. Tekan Unduh ulang; file sementara akan dibersihkan otomatis.</p>}
                    {model.id.includes("9b") && <p className="mt-2 text-[10px] text-muted-foreground">9B memerlukan RAM jauh lebih besar. Jika Android menutup aplikasi atau respons terlalu lambat, kembali ke 4B.</p>}
                  </div>
                );
              })}

              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Runtime memakai llama.cpp native Android. Model tetap dimuat selama sesi aktif, token di-stream dan digabung sebelum update UI untuk mengurangi latency serta kedipan layar.
              </p>
              {lastMetrics && (
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-lg bg-muted p-2"><p className="text-sm font-semibold">{(lastMetrics.firstTokenMs / 1000).toFixed(1)} dtk</p><p className="text-[9px] text-muted-foreground">token pertama</p></div>
                  <div className="rounded-lg bg-muted p-2"><p className="text-sm font-semibold">{lastMetrics.tokensPerSecond.toFixed(1)}</p><p className="text-[9px] text-muted-foreground">token/detik</p></div>
                  <div className="rounded-lg bg-muted p-2"><p className="text-sm font-semibold">{lastMetrics.warmStart ? "Hangat" : "Dingin"}</p><p className="text-[9px] text-muted-foreground">kondisi model</p></div>
                </div>
              )}
            </section>

            <section className="space-y-3">
              <Label>Mesin suara (TTS)</Label>
              <Select value={ttsProvider} onValueChange={(value) => setTtsProvider(value as TTSProvider)}>
                <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="voicevox">VOICEVOX — anime Jepang (gratis, stabil)</SelectItem>
                  <SelectItem value="clone">Voice Clone — suara karakter custom</SelectItem>
                </SelectContent>
              </Select>

              {ttsProvider === "voicevox" ? (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Karakter VOICEVOX</Label>
                    <Select value={String(vvSpeaker)} onValueChange={(value) => setVvSpeaker(Number(value))}>
                      <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {VV_SPEAKERS.map((speaker) => <SelectItem key={speaker.id} value={String(speaker.id)}>{speaker.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex min-h-11 items-center justify-between gap-4">
                    <Label className="text-xs">Auto-terjemah ke Jepang</Label>
                    <Switch checked={vvTranslate} onCheckedChange={setVvTranslate} />
                  </div>
                  <div className="flex min-h-11 items-center justify-between gap-4">
                    <Label className="text-xs">Pre-generate audio (instant play)</Label>
                    <Switch checked={preGenAudio} onCheckedChange={setPreGenAudio} />
                  </div>
                </div>
              ) : (
                <div className="space-y-3 rounded-xl border bg-muted/30 p-3">
                  <Label className="flex items-center gap-2 text-xs font-semibold"><Sparkles className="h-3.5 w-3.5" />Sampel suara karakter</Label>
                  <p className="text-[11px] leading-relaxed text-muted-foreground">Upload MP3/WAV jernih selama 6–15 detik, satu suara, tanpa musik. Voice Clone tetap online.</p>
                  <input type="file" accept="audio/*" onChange={handleCloneSampleUpload} className="block w-full text-xs" />
                  {hasCloneSample && (
                    <div className="flex items-center justify-between rounded-lg border bg-background/60 p-2 text-xs">
                      <span className="min-w-0 truncate">{cloneSampleName || "Sampel tersimpan"}</span>
                      <Button size="icon" variant="ghost" className="h-9 w-9" onClick={clearCloneSample} aria-label="Hapus sampel suara"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  )}
                </div>
              )}

              <p className="text-[11px] leading-relaxed text-muted-foreground"><Volume2 className="mr-1 inline h-3.5 w-3.5" />Tombol putar pada balon Furina menggunakan suara pilihanmu.</p>
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

            <section className="space-y-2">
              <Label>Bahasa balasan</Label>
              <Select value={language} onValueChange={(value) => setLanguage(value as ReplyLanguage)}>
                <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">Auto (mengikuti kamu)</SelectItem>
                  <SelectItem value="ja">日本語</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="id">Indonesia</SelectItem>
                </SelectContent>
              </Select>
            </section>

            <Separator />

            <section className="space-y-3">
              <Label className="flex items-center gap-2"><ImageIcon className="h-4 w-4" />Background karakter</Label>
              <input ref={backgroundInputRef} type="file" accept="image/*" onChange={handleBackgroundUpload} className="block w-full text-sm" />
              <Button variant="outline" size="sm" onClick={() => {
                setBackground(furinaDefault);
                localStorage.removeItem(PREF.background);
                if (backgroundInputRef.current) backgroundInputRef.current.value = "";
              }}><RotateCcw className="mr-2 h-4 w-4" />Kembalikan Furina default</Button>
            </section>

            <Separator />

            <section className="space-y-3 rounded-xl border p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2"><HardDrive className="h-4 w-4" /><Label>Memori (lintas-percakapan)</Label></div>
                <Button variant="ghost" size="sm" onClick={() => {
                  if (!confirm("Hapus semua memori fakta? Riwayat percakapan tidak ikut dihapus.")) return;
                  bridge()?.clearMemories();
                  refreshMemories();
                  refreshStats();
                  toast.success("Memori fakta dibersihkan");
                }}>Hapus semua</Button>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg bg-muted p-2"><p className="text-lg font-semibold">{stats.messages}</p><p className="text-[10px] text-muted-foreground">pesan</p></div>
                <div className="rounded-lg bg-muted p-2"><p className="text-lg font-semibold">{stats.sessions}</p><p className="text-[10px] text-muted-foreground">sesi</p></div>
                <div className="rounded-lg bg-muted p-2"><p className="text-lg font-semibold">{stats.memories}</p><p className="text-[10px] text-muted-foreground">memori fakta</p></div>
              </div>
              <p className="text-[11px] leading-relaxed text-muted-foreground">Fakta tentang kamu dipelajari otomatis dan dapat ditambah manual. Semua pesan tetap tersimpan utuh di SQLite; sesi baru tidak mereset hubungan.</p>
              <div className="flex gap-2">
                <Input value={newMemory} onChange={(event) => setNewMemory(event.target.value)} placeholder="Tambah fakta tentang dirimu…" />
                <Button size="icon" className="h-11 w-11 shrink-0" aria-label="Tambah memori" onClick={() => {
                  const clean = newMemory.trim();
                  if (clean.length < 3) return;
                  bridge()?.addMemory(clean);
                  setNewMemory("");
                  refreshMemories();
                  refreshStats();
                }}><Plus className="h-4 w-4" /></Button>
              </div>
              <div className="max-h-72 space-y-1 overflow-y-auto rounded-lg border p-2">
                {memories.length === 0 ? <p className="p-2 text-sm text-muted-foreground">Belum ada memori.</p> : memories.map((memory) => (
                  <div key={memory.id} className="flex items-start gap-2 rounded-lg p-2 text-sm hover:bg-muted/50">
                    <span className="min-w-0 flex-1 break-words">{memory.content}</span>
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[9px] text-muted-foreground">{memory.importance ?? 5}</span>
                    <Button size="icon" variant="ghost" className="h-8 w-8 shrink-0" aria-label="Hapus memori" onClick={() => {
                      bridge()?.deleteMemory(memory.id);
                      refreshMemories();
                      refreshStats();
                    }}><Trash2 className="h-3.5 w-3.5" /></Button>
                  </div>
                ))}
              </div>
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

            <Separator />

            <Button variant="outline" className="min-h-12 w-full" onClick={() => {
              if (!activeSessionId || !confirm("Bersihkan seluruh pesan dalam percakapan ini?")) return;
              bridge()?.clearSession(activeSessionId);
              setMessages([]);
              refreshSessions(activeSessionId);
              refreshStats();
            }}><Trash2 className="mr-2 h-4 w-4" />Bersihkan percakapan ini</Button>
          </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
