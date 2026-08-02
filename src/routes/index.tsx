import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Bot,
  Brain,
  Check,
  Cpu,
  Database,
  Download,
  HardDrive,
  History,
  Home,
  Image as ImageIcon,
  LayoutDashboard,
  Menu,
  Moon,
  Plus,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  User,
  WifiOff,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

import furinaDefault from "@/assets/furina.jpg";
import { buildFurinaSystemPrompt } from "@/lib/furina.persona";
import profile from "../../shared/furina-profile.json";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Furina — Offline AI Companion" },
      {
        name: "description",
        content: "Furina companion lokal dengan model GGUF, memori perangkat, dan tanpa layanan AI cloud.",
      },
    ],
  }),
  component: FurinaApp,
});

type Screen = "chat" | "history" | "dashboard" | "models" | "settings";
type ThemeMode = "dark" | "light";
type MessageStatus = "sending" | "sent" | "read" | "failed";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: number;
  status?: MessageStatus;
  imageDataUrl?: string;
  failedPayload?: string;
};

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: number;
  pinned?: boolean;
};

type SharedState = {
  version: number;
  name: string;
  persona: string;
  language: "auto" | "id" | "en" | "ja";
  memories: string[];
};

type NativeStatus = {
  mode: "offline";
  source: "offline";
  activeModelId: string;
  installed: boolean;
  busy: boolean;
  supportsImage: boolean;
  multimodalReady: boolean;
  canUseOffline: boolean;
  imageDisabledReason?: string;
};

type NativeBridge = {
  getStatus: () => string;
  getSharedState: () => string;
  saveSharedState: (json: string) => boolean;
  useOfflineAi: () => boolean;
  deactivateOfflineModel: () => boolean;
  openModelManager: () => void;
  cancelGeneration: () => void;
  generate: (request: string) => void;
  generateWithImage?: (request: string, imageDataUrl: string) => void;
};

declare global {
  interface Window {
    FurinaNative?: NativeBridge;
  }
}

const STORAGE = {
  conversations: "furina:v4:conversations",
  active: "furina:v4:active",
  shared: "furina:shared-state:v1",
  theme: "furina:v4:theme",
  screen: "furina:v4:screen",
};

const DEFAULT_SHARED: SharedState = {
  version: 1,
  name: profile.name,
  persona: "",
  language: "auto",
  memories: [],
};

const DEFAULT_NATIVE: NativeStatus = {
  mode: "offline",
  source: "offline",
  activeModelId: "",
  installed: false,
  busy: false,
  supportsImage: false,
  multimodalReady: false,
  canUseOffline: false,
};

const navigation: Array<{ id: Screen; icon: typeof Home; label: string }> = [
  { id: "chat", icon: Home, label: "Chat" },
  { id: "history", icon: History, label: "Riwayat" },
  { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { id: "models", icon: Cpu, label: "Model lokal" },
  { id: "settings", icon: Settings, label: "Pengaturan" },
];

function uid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `furina-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function newConversation(): Conversation {
  return { id: uid(), title: "Percakapan baru", messages: [], updatedAt: Date.now() };
}

function safeParse<T>(value: string | null | undefined, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function clip(value: string, max: number) {
  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized.length > max ? `${normalized.slice(0, max - 1).trimEnd()}…` : normalized;
}

function normalizeShared(raw: Partial<SharedState> | null | undefined): SharedState {
  const language = ["auto", "id", "en", "ja"].includes(String(raw?.language))
    ? (raw?.language as SharedState["language"])
    : "auto";
  const memories = Array.isArray(raw?.memories)
    ? Array.from(new Set(raw.memories.filter((item): item is string => typeof item === "string").map((item) => clip(item, 240)).filter((item) => item.length >= 3))).slice(-80)
    : [];
  return {
    version: 1,
    name: clip(typeof raw?.name === "string" ? raw.name : profile.name, 40) || profile.name,
    persona: typeof raw?.persona === "string" ? raw.persona.slice(0, 6000) : "",
    language,
    memories,
  };
}

function normalizeConversations(raw: unknown): Conversation[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Conversation => Boolean(item) && typeof item === "object")
    .map((item) => ({
      id: typeof item.id === "string" && item.id ? item.id : uid(),
      title: typeof item.title === "string" && item.title ? item.title.slice(0, 70) : "Percakapan baru",
      updatedAt: Number(item.updatedAt) || Date.now(),
      pinned: Boolean(item.pinned),
      messages: Array.isArray(item.messages)
        ? item.messages.slice(-1000).map((message): Message => ({
            id: typeof message.id === "string" && message.id ? message.id : uid(),
            role: message.role === "assistant" ? "assistant" : "user",
            content: typeof message.content === "string" ? message.content.slice(0, 32_000) : "",
            at: Number(message.at) || Date.now(),
            status: message.status,
            imageDataUrl: typeof message.imageDataUrl === "string" ? message.imageDataUrl : undefined,
            failedPayload: typeof message.failedPayload === "string" ? message.failedPayload : undefined,
          }))
        : [],
    }))
    .sort((left, right) => Number(right.pinned) - Number(left.pinned) || right.updatedAt - left.updatedAt)
    .slice(0, 120);
}

function relativeTime(timestamp: number, clock: number) {
  const difference = Math.max(0, clock - timestamp);
  if (difference < 60_000) return "baru saja";
  if (difference < 3_600_000) return `${Math.floor(difference / 60_000)} m`;
  if (difference < 86_400_000) return `${Math.floor(difference / 3_600_000)} j`;
  if (difference < 604_800_000) return `${Math.floor(difference / 86_400_000)} h`;
  return new Date(timestamp).toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
}

function formatTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
}

function extractMemoryCandidates(text: string) {
  const cleaned = clip(text, 240);
  if (cleaned.length < 8) return [];
  const patterns = [
    /\b(?:aku|saya)\s+(?:suka|menyukai|lebih suka|tidak suka|benci|tinggal|punya|memiliki|biasanya|sedang membangun|sedang mengerjakan|ingin|berencana|menargetkan)\b/i,
    /\b(?:nama(?:ku| saya)|aku bernama|saya bernama|targetku|tujuanku|proyekku|pekerjaanku|hobiku)\b/i,
  ];
  return patterns.some((pattern) => pattern.test(cleaned)) ? [cleaned] : [];
}

function relevantMemories(query: string, memories: string[]) {
  const terms = new Set(query.toLowerCase().split(/[^a-z0-9À-ÿ]+/i).filter((term) => term.length >= 3));
  return memories
    .map((memory, index) => ({
      memory,
      index,
      score: memory.toLowerCase().split(/[^a-z0-9À-ÿ]+/i).reduce((score, term) => score + (terms.has(term) ? 1 : 0), 0),
    }))
    .sort((left, right) => right.score - left.score || right.index - left.index)
    .slice(0, 20)
    .map((entry) => entry.memory);
}

function nativeBridge() {
  return typeof window !== "undefined" ? window.FurinaNative : undefined;
}

function FurinaApp() {
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [screen, setScreen] = useState<Screen>("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [shared, setShared] = useState<SharedState>(DEFAULT_SHARED);
  const [nativeStatus, setNativeStatus] = useState<NativeStatus>(DEFAULT_NATIVE);
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<{ dataUrl: string; name: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [historyFilter, setHistoryFilter] = useState<"all" | "image" | "pinned">("all");
  const [clock, setClock] = useState(Date.now());
  const [memoryDraft, setMemoryDraft] = useState("");

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const activeNativeRequest = useRef<{ requestId: string; conversationId: string; assistantMessageId: string } | null>(null);

  const activeConversation = useMemo(() => conversations.find((conversation) => conversation.id === activeId), [conversations, activeId]);
  const messages = activeConversation?.messages ?? [];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = normalizeConversations(safeParse(localStorage.getItem(STORAGE.conversations), []));
    const initial = stored.length ? stored : [newConversation()];
    const savedActive = localStorage.getItem(STORAGE.active);
    setConversations(initial);
    setActiveId(savedActive && initial.some((item) => item.id === savedActive) ? savedActive : initial[0].id);
    const localShared = normalizeShared(safeParse(localStorage.getItem(STORAGE.shared), DEFAULT_SHARED));
    try {
      setShared(normalizeShared(safeParse(nativeBridge()?.getSharedState(), localShared)));
    } catch {
      setShared(localShared);
    }
    setTheme(localStorage.getItem(STORAGE.theme) === "light" ? "light" : "dark");
    const savedScreen = localStorage.getItem(STORAGE.screen);
    if (navigation.some((item) => item.id === savedScreen)) setScreen(savedScreen as Screen);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(STORAGE.theme, theme);
  }, [theme]);

  useEffect(() => {
    if (!conversations.length) return;
    try {
      localStorage.setItem(STORAGE.conversations, JSON.stringify(conversations));
      localStorage.setItem(STORAGE.active, activeId);
    } catch {
      toast.error("Penyimpanan chat penuh. Hapus beberapa chat bergambar atau ekspor data.");
    }
  }, [conversations, activeId]);

  useEffect(() => {
    localStorage.setItem(STORAGE.screen, screen);
  }, [screen]);

  useEffect(() => {
    const normalized = normalizeShared(shared);
    localStorage.setItem(STORAGE.shared, JSON.stringify(normalized));
    try { nativeBridge()?.saveSharedState(JSON.stringify(normalized)); } catch {}
  }, [shared]);

  useEffect(() => {
    const update = () => {
      const bridge = nativeBridge();
      if (!bridge) return setNativeStatus(DEFAULT_NATIVE);
      try {
        const status = { ...DEFAULT_NATIVE, ...safeParse<Partial<NativeStatus>>(bridge.getStatus(), {}) } as NativeStatus;
        setNativeStatus(status);
        if (status.installed) bridge.useOfflineAi();
      } catch {
        setNativeStatus(DEFAULT_NATIVE);
      }
    };
    update();
    const timer = window.setInterval(() => !document.hidden && update(), 2500);
    window.addEventListener("furina-ai-mode-changed", update as EventListener);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("furina-ai-mode-changed", update as EventListener);
    };
  }, []);

  useEffect(() => {
    const sharedListener = (event: Event) => {
      const detail = (event as CustomEvent).detail as Partial<SharedState> | undefined;
      if (detail) setShared(normalizeShared(detail));
    };
    window.addEventListener("furina-shared-state-changed", sharedListener);
    return () => window.removeEventListener("furina-shared-state-changed", sharedListener);
  }, []);

  useEffect(() => {
    const tokenListener = (event: Event) => {
      const detail = (event as CustomEvent).detail as { requestId?: string; token?: string };
      const request = activeNativeRequest.current;
      if (!request || detail.requestId !== request.requestId) return;
      setConversations((previous) => previous.map((conversation) => conversation.id === request.conversationId ? {
        ...conversation,
        updatedAt: Date.now(),
        messages: conversation.messages.map((message) => message.id === request.assistantMessageId ? { ...message, content: `${message.content}${String(detail.token || "")}`, status: "sent" } : message),
      } : conversation));
    };
    const completeListener = (event: Event) => {
      const detail = (event as CustomEvent).detail as { requestId?: string };
      const request = activeNativeRequest.current;
      if (!request || detail.requestId !== request.requestId) return;
      setConversations((previous) => previous.map((conversation) => conversation.id === request.conversationId ? {
        ...conversation,
        updatedAt: Date.now(),
        messages: conversation.messages.map((message) => message.id === request.assistantMessageId ? { ...message, content: message.content.trim() || "Model selesai tanpa menghasilkan teks.", status: "sent" } : message),
      } : conversation));
      activeNativeRequest.current = null;
      setSending(false);
    };
    const errorListener = (event: Event) => {
      const detail = (event as CustomEvent).detail as { requestId?: string; error?: string };
      const request = activeNativeRequest.current;
      if (!request || detail.requestId !== request.requestId) return;
      setConversations((previous) => previous.map((conversation) => conversation.id === request.conversationId ? {
        ...conversation,
        updatedAt: Date.now(),
        messages: conversation.messages.map((message) => message.id === request.assistantMessageId ? { ...message, content: message.content || detail.error || "Model lokal gagal merespons.", status: "failed" } : message),
      } : conversation));
      activeNativeRequest.current = null;
      setSending(false);
    };
    window.addEventListener("furina-native-token", tokenListener);
    window.addEventListener("furina-native-complete", completeListener);
    window.addEventListener("furina-native-error", errorListener);
    return () => {
      window.removeEventListener("furina-native-token", tokenListener);
      window.removeEventListener("furina-native-complete", completeListener);
      window.removeEventListener("furina-native-error", errorListener);
    };
  }, []);

  useEffect(() => {
    if (screen === "chat") scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending, screen]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  function updateConversation(conversationId: string, updater: (items: Message[]) => Message[]) {
    setConversations((previous) => previous.map((conversation) => conversation.id === conversationId ? { ...conversation, messages: updater(conversation.messages), updatedAt: Date.now() } : conversation));
  }

  function startNewConversation() {
    if (sending) return toast.info("Hentikan atau tunggu jawaban yang sedang dibuat.");
    const created = newConversation();
    setConversations((previous) => [created, ...previous]);
    setActiveId(created.id);
    setScreen("chat");
    setMenuOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function selectConversation(conversationId: string) {
    if (sending) return toast.info("Tunggu jawaban selesai sebelum berpindah chat.");
    setActiveId(conversationId);
    setScreen("chat");
    setMenuOpen(false);
  }

  function deleteConversation(conversationId: string) {
    if (!confirm("Hapus percakapan ini?")) return;
    setConversations((previous) => {
      const remaining = previous.filter((conversation) => conversation.id !== conversationId);
      if (!remaining.length) {
        const fresh = newConversation();
        setActiveId(fresh.id);
        return [fresh];
      }
      if (conversationId === activeId) setActiveId(remaining[0].id);
      return remaining;
    });
  }

  function togglePinned(conversationId: string) {
    setConversations((previous) => previous.map((conversation) => conversation.id === conversationId ? { ...conversation, pinned: !conversation.pinned, updatedAt: Date.now() } : conversation));
  }

  function mergeMemories(text: string) {
    const candidates = extractMemoryCandidates(text);
    if (!candidates.length) return shared.memories;
    const next = normalizeShared({ ...shared, memories: [...shared.memories, ...candidates] }).memories;
    setShared((previous) => ({ ...previous, memories: next }));
    return next;
  }

  async function sendMessage(explicitText?: string, explicitImage?: string) {
    const conversation = activeConversation;
    if (!conversation || sending) return;
    const text = (explicitText ?? input).trim();
    const imageDataUrl = explicitImage ?? pendingImage?.dataUrl;
    if (!text && !imageDataUrl) return;

    const bridge = nativeBridge();
    if (!bridge) return toast.error("AI lokal hanya tersedia di APK Android.");
    if (!nativeStatus.installed) {
      toast.info("Impor dan aktifkan model GGUF lokal terlebih dahulu.");
      bridge.openModelManager();
      return;
    }
    if (imageDataUrl && !nativeStatus.multimodalReady) return toast.error(nativeStatus.imageDisabledReason || "Model aktif belum mendukung gambar.");

    const userMessage: Message = {
      id: uid(),
      role: "user",
      content: text || "Jelaskan gambar ini.",
      at: Date.now(),
      status: "sending",
      imageDataUrl,
      failedPayload: text || "Jelaskan gambar ini.",
    };
    const conversationId = conversation.id;
    const contextMessages = [...conversation.messages.filter((message) => message.status !== "failed"), userMessage];
    const memories = mergeMemories(userMessage.content);

    setConversations((previous) => previous.map((item) => item.id === conversationId ? {
      ...item,
      title: item.title === "Percakapan baru" ? clip(userMessage.content, 42) || "Percakapan baru" : item.title,
      messages: [...item.messages, userMessage],
      updatedAt: Date.now(),
    } : item));
    setInput("");
    setPendingImage(null);
    setSending(true);

    const assistantMessageId = uid();
    updateConversation(conversationId, (items) => [
      ...items.map((message) => message.id === userMessage.id ? { ...message, status: "read" as const } : message),
      { id: assistantMessageId, role: "assistant", content: "", at: Date.now(), status: "sending" },
    ]);
    const requestId = uid();
    activeNativeRequest.current = { requestId, conversationId, assistantMessageId };
    const systemPrompt = buildFurinaSystemPrompt({
      characterName: shared.name,
      persona: shared.persona,
      language: shared.language,
      memories: relevantMemories(userMessage.content, memories),
      clientNow: Date.now(),
      timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    });
    const request = JSON.stringify({
      requestId,
      messages: contextMessages.slice(-18).map((message) => ({ role: message.role, content: message.content })),
      systemPrompt,
      maxTokens: imageDataUrl ? 640 : 512,
      contextSize: imageDataUrl ? 6144 : 4096,
      temperature: 0.8,
    });
    try {
      if (imageDataUrl && bridge.generateWithImage) bridge.generateWithImage(request, imageDataUrl);
      else bridge.generate(request);
    } catch (error) {
      activeNativeRequest.current = null;
      setSending(false);
      toast.error(error instanceof Error ? error.message : "Model lokal gagal dimulai.");
    }
  }

  function stopGeneration() {
    if (!sending) return;
    try { nativeBridge()?.cancelGeneration(); } catch {}
  }

  async function handleImagePick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) return toast.error("Pilih file gambar.");
    if (file.size > 12 * 1024 * 1024) return toast.error("Gambar maksimal 12 MB.");
    try {
      setPendingImage({ dataUrl: await compressImage(file, 1280, 0.82), name: file.name || "Gambar" });
    } catch {
      toast.error("Gambar gagal diproses.");
    }
  }

  function addMemory() {
    const memory = clip(memoryDraft, 240);
    if (memory.length < 3) return;
    setShared((previous) => normalizeShared({ ...previous, memories: [...previous.memories, memory] }));
    setMemoryDraft("");
  }

  function exportData() {
    const blob = new Blob([JSON.stringify({ app: "Furina", version: 4, exportedAt: new Date().toISOString(), shared, conversations, activeId }, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = `furina-backup-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  async function importData(file?: File) {
    if (!file) return;
    try {
      const backup = JSON.parse(await file.text()) as { app?: string; shared?: Partial<SharedState>; conversations?: unknown; activeId?: string };
      if (backup.app !== "Furina") throw new Error("File bukan backup Furina.");
      const imported = normalizeConversations(backup.conversations);
      if (!imported.length) throw new Error("Backup tidak berisi percakapan.");
      if (!confirm("Impor akan mengganti data lokal saat ini. Lanjutkan?")) return;
      setConversations(imported);
      setActiveId(imported.some((item) => item.id === backup.activeId) ? String(backup.activeId) : imported[0].id);
      setShared(normalizeShared(backup.shared));
      toast.success("Backup berhasil dipulihkan.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Backup gagal diimpor.");
    } finally {
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }

  const filteredConversations = useMemo(() => {
    const keyword = historySearch.trim().toLowerCase();
    return [...conversations]
      .sort((left, right) => Number(right.pinned) - Number(left.pinned) || right.updatedAt - left.updatedAt)
      .filter((conversation) => {
        if (historyFilter === "image" && !conversation.messages.some((message) => message.imageDataUrl)) return false;
        if (historyFilter === "pinned" && !conversation.pinned) return false;
        if (!keyword) return true;
        return `${conversation.title} ${conversation.messages.map((message) => message.content).join(" ")}`.toLowerCase().includes(keyword);
      });
  }, [conversations, historySearch, historyFilter]);

  const stats = useMemo(() => ({
    conversations: conversations.filter((conversation) => conversation.messages.length).length,
    messages: conversations.reduce((total, conversation) => total + conversation.messages.length, 0),
    images: conversations.reduce((total, conversation) => total + conversation.messages.filter((message) => message.imageDataUrl).length, 0),
    memories: shared.memories.length,
  }), [conversations, shared.memories.length]);

  return (
    <div className="fx-shell relative h-[100dvh] w-full overflow-hidden">
      <img src={furinaDefault} alt="Furina background" className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <div className={`absolute inset-0 transition-opacity duration-500 ${theme === "dark" ? "fx-veil-dark" : "fx-veil-light"}`} />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_85%_8%,rgba(82,184,255,.18),transparent_30%)]" />

      <aside className={`absolute inset-y-0 left-0 z-50 w-[82%] max-w-xs fx-card rounded-r-[28px] border-y-0 border-l-0 p-4 transition-transform duration-300 ease-out ${menuOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center justify-between"><div><p className="text-xs uppercase tracking-[.28em] text-sky-200/70">Furina</p><h2 className="mt-1 text-xl font-semibold">Companion Lokalmu</h2></div><Button variant="ghost" size="icon" className="rounded-full" onClick={() => setMenuOpen(false)}><X className="h-4 w-4" /></Button></div>
        <div className="mt-6 space-y-2">{navigation.map(({ id, icon: Icon, label }) => <button key={id} onClick={() => { setScreen(id); setMenuOpen(false); }} className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm ${screen === id ? "bg-sky-500/20 ring-1 ring-sky-300/30" : "fx-soft hover:bg-foreground/5"}`}><Icon className="h-4 w-4" /><span>{label}</span></button>)}</div>
        <div className="mt-6 rounded-3xl fx-subtle p-4"><p className="text-xs uppercase tracking-[.22em] text-sky-200/70">AI aktif</p><p className="mt-2 font-semibold">{nativeStatus.installed ? nativeStatus.activeModelId || "Model lokal" : "Belum ada model"}</p><p className="mt-1 text-xs fx-soft">100% lokal · tanpa cloud</p></div>
      </aside>
      {menuOpen && <button aria-label="Tutup menu" className="absolute inset-0 z-40 bg-black/45 backdrop-blur-sm" onClick={() => setMenuOpen(false)} />}

      <header className="absolute inset-x-0 top-0 z-30 px-4 pt-3"><div className="mx-auto flex max-w-5xl items-center justify-between rounded-[28px] fx-card px-3 py-3 shadow-2xl"><div className="flex min-w-0 items-center gap-3"><Button variant="ghost" size="icon" className="fx-press rounded-full" onClick={() => setMenuOpen(true)}><Menu className="h-5 w-5" /></Button><div className="min-w-0"><div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${nativeStatus.installed ? "bg-violet-400" : "bg-amber-400"}`} /><p className="truncate text-sm font-semibold">{shared.name}</p></div><p className="truncate text-xs fx-soft">{nativeStatus.installed ? "AI lokal" : "Model lokal belum dipasang"}</p></div></div><div className="flex items-center gap-1">{screen === "chat" && <Button variant="ghost" size="icon" className="fx-press rounded-full" onClick={startNewConversation}><Plus className="h-5 w-5" /></Button>}<Button variant="ghost" size="icon" className="fx-press rounded-full" onClick={() => setTheme((value) => value === "dark" ? "light" : "dark")}>{theme === "dark" ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}</Button></div></div></header>

      {screen === "chat" && <main ref={scrollRef} className="furina-page absolute inset-x-0 bottom-0 top-0 z-10 overflow-y-auto px-4 pb-40 pt-24"><div className="mx-auto flex min-h-full max-w-3xl flex-col justify-end gap-3">{!messages.length && <div className="max-w-[88%] self-start rounded-[26px] fx-card px-4 py-4 shadow-2xl"><p className="text-sm leading-relaxed">{profile.defaultGreeting}</p><p className="mt-2 text-[11px] fx-soft">{nativeStatus.installed ? "Model lokal siap" : "Impor model GGUF untuk mulai"}</p></div>}{messages.map((message, index) => <div key={message.id} className={`fx-rise flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`} style={{ animationDelay: `${Math.min(index, 6) * 35}ms` }}><div className={`w-fit max-w-[88%] rounded-[25px] px-4 py-3 text-sm shadow-xl ${message.role === "user" ? "fx-bubble-user" : "fx-bubble-ai"}`}>{message.imageDataUrl && <img src={message.imageDataUrl} alt="Lampiran" className="mb-3 max-h-72 rounded-2xl object-cover" />}<p className="whitespace-pre-wrap leading-relaxed">{message.content || (message.role === "assistant" ? "…" : "")}</p></div><div className="mt-1 flex items-center gap-2 px-2 text-[11px] fx-soft"><span>{formatTime(message.at)}</span>{message.status === "failed" && message.role === "user" && <button className="fx-press rounded-full bg-red-500/90 px-2 py-0.5 text-[10px] text-white" onClick={() => sendMessage(message.failedPayload || message.content, message.imageDataUrl)}>Kirim ulang</button>}</div></div>)}</div></main>}

      {screen === "history" && <PageShell><PageTitle eyebrow="Tersimpan lokal" title="Riwayat Percakapan" description="Semua chat berada di perangkat ini." /><div className="rounded-3xl fx-card p-3"><div className="flex items-center gap-2 rounded-2xl fx-subtle px-3 py-2"><Search className="h-4 w-4 fx-soft" /><input value={historySearch} onChange={(event) => setHistorySearch(event.target.value)} placeholder="Cari percakapan…" className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400" /></div><div className="mt-3 flex gap-2">{[["all", "Semua"], ["image", "Gambar"], ["pinned", "Pinned"]].map(([id, label]) => <button key={id} onClick={() => setHistoryFilter(id as typeof historyFilter)} className={`rounded-full px-3 py-1.5 text-xs ${historyFilter === id ? "bg-sky-500" : "fx-subtle text-slate-200/70"}`}>{label}</button>)}</div></div><div className="mt-4 grid gap-3">{filteredConversations.map((conversation) => { const last = conversation.messages[conversation.messages.length - 1]; return <article key={conversation.id} className="rounded-3xl fx-card p-4"><div className="flex items-start justify-between gap-3"><button className="min-w-0 flex-1 text-left" onClick={() => selectConversation(conversation.id)}><div className="flex items-center gap-2"><p className="truncate text-sm font-semibold">{conversation.title}</p>{conversation.pinned && <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px]">Pinned</span>}</div><p className="mt-1 line-clamp-2 text-sm fx-soft">{last?.content || "Belum ada pesan."}</p><p className="mt-2 text-[11px] fx-soft">{relativeTime(conversation.updatedAt, clock)} · {conversation.messages.length} pesan</p></button><div className="flex gap-1"><Button variant="ghost" size="sm" className="rounded-full" onClick={() => togglePinned(conversation.id)}>{conversation.pinned ? "Lepas" : "Pin"}</Button><Button variant="ghost" size="icon" className="rounded-full text-red-200" onClick={() => deleteConversation(conversation.id)}><Trash2 className="h-4 w-4" /></Button></div></div></article>; })}</div></PageShell>}

      {screen === "dashboard" && <PageShell><PageTitle eyebrow="Ringkasan lokal" title="Dashboard" description="Status model, memori, dan data perangkat." /><div className="grid grid-cols-2 gap-3"><Metric icon={Cpu} label="Mode aktif" value="Offline" /><Metric icon={History} label="Percakapan" value={String(stats.conversations)} /><Metric icon={ImageIcon} label="Gambar" value={String(stats.images)} /><Metric icon={Brain} label="Memori" value={String(stats.memories)} /></div><Card><h3 className="font-semibold">Privasi perangkat</h3><p className="mt-2 text-sm fx-soft">Tidak ada provider cloud, login, sinkronisasi, ataupun fallback jaringan. Prompt dan data diproses oleh model GGUF lokal.</p><div className="mt-4 flex items-center gap-2 rounded-2xl bg-emerald-500/10 px-3 py-3 text-sm text-emerald-100"><ShieldCheck className="h-4 w-4" />Tidak mengirim data keluar</div></Card><Card><h3 className="font-semibold">Aksi cepat</h3><div className="mt-3 grid gap-2"><QuickButton icon={Plus} title="Chat baru" onClick={startNewConversation} /><QuickButton icon={Bot} title="Kelola model lokal" onClick={() => nativeBridge()?.openModelManager()} /><QuickButton icon={Download} title="Ekspor backup" onClick={exportData} /></div></Card></PageShell>}

      {screen === "models" && <PageShell><PageTitle eyebrow="AI di perangkat" title="Model Lokal" description="Impor model GGUF dari penyimpanan perangkat. Aplikasi tidak mengunduh model sendiri." /><Card><div className="flex items-start gap-3"><div className="rounded-2xl bg-violet-500/20 p-3"><Cpu className="h-5 w-5" /></div><div className="flex-1"><div className="flex items-center justify-between"><h3 className="font-semibold">{nativeStatus.activeModelId || "Belum ada model aktif"}</h3>{nativeStatus.installed && <span className="rounded-full bg-violet-500/20 px-2 py-1 text-[10px] text-violet-100">Aktif lokal</span>}</div><p className="mt-1 text-sm fx-soft">{nativeBridge() ? nativeStatus.installed ? `Terpasang${nativeStatus.multimodalReady ? " · teks + gambar" : " · teks"}` : "Impor model GGUF untuk mulai." : "Pengelola model tersedia melalui APK Android."}</p><div className="mt-3 flex flex-wrap gap-2"><Button className="rounded-2xl bg-violet-500" onClick={() => nativeBridge()?.openModelManager()} disabled={!nativeBridge()}><HardDrive className="mr-2 h-4 w-4" />Impor / ganti model</Button>{nativeStatus.installed && <Button variant="outline" className="fx-subtle fx-press rounded-2xl" onClick={() => { nativeBridge()?.deactivateOfflineModel(); setNativeStatus(DEFAULT_NATIVE); }}>Lepas model</Button>}</div></div></div></Card><Card><h3 className="font-semibold">Cara kerja</h3><div className="mt-3 space-y-3 text-sm fx-soft"><p className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-emerald-300" />File model tersimpan di ruang aplikasi dan tidak hilang saat APK diperbarui.</p><p className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-emerald-300" />Persona dan memori lokal dimasukkan ke prompt model aktif.</p><p className="flex gap-2"><WifiOff className="mt-0.5 h-4 w-4 text-sky-300" />Inferensi tetap berjalan tanpa Wi-Fi maupun data seluler.</p></div></Card></PageShell>}

      {screen === "settings" && <PageShell><PageTitle eyebrow="Personalisasi lokal" title="Pengaturan" description="Persona dan memori hanya digunakan di perangkat." /><Card><SettingTitle icon={User} title="Persona lokal" /><label className="text-xs fx-soft">Nama karakter</label><Input value={shared.name} onChange={(event) => setShared((previous) => ({ ...previous, name: event.target.value.slice(0, 40) }))} className="fx-subtle mt-2" /><label className="mt-4 block text-xs fx-soft">Kepribadian tambahan</label><Textarea rows={5} value={shared.persona} onChange={(event) => setShared((previous) => ({ ...previous, persona: event.target.value.slice(0, 6000) }))} placeholder="Kosongkan untuk memakai persona Furina bawaan." className="fx-subtle mt-2" /><label className="mt-4 block text-xs fx-soft">Bahasa balasan</label><select value={shared.language} onChange={(event) => setShared((previous) => ({ ...previous, language: event.target.value as SharedState["language"] }))} className="fx-subtle mt-2 h-11 w-full rounded-xl px-3 text-sm"><option value="auto">Ikuti bahasa pengguna</option><option value="id">Indonesia</option><option value="en">English</option><option value="ja">日本語</option></select></Card><Card><SettingTitle icon={Brain} title="Memori lokal" /><p className="text-sm fx-soft">Memori disimpan di perangkat dan diberikan hanya kepada model lokal ketika relevan.</p><div className="mt-3 flex gap-2"><Input value={memoryDraft} onChange={(event) => setMemoryDraft(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addMemory()} placeholder="Contoh: Wynn menyukai jawaban yang langsung." className="fx-subtle" /><Button size="icon" className="shrink-0 rounded-xl bg-sky-500" onClick={addMemory}><Plus className="h-4 w-4" /></Button></div><div className="mt-3 max-h-60 space-y-2 overflow-y-auto">{shared.memories.slice().reverse().map((memory) => <div key={memory} className="flex items-start gap-2 rounded-2xl fx-subtle px-3 py-2 text-sm"><p className="flex-1 fx-text">{memory}</p><button onClick={() => setShared((previous) => ({ ...previous, memories: previous.memories.filter((item) => item !== memory) }))}><X className="h-4 w-4 text-slate-400" /></button></div>)}{!shared.memories.length && <p className="rounded-2xl border border-dashed border-white/10 p-4 text-center text-sm text-slate-400">Belum ada memori lokal.</p>}</div></Card><Card><SettingTitle icon={Database} title="Backup lokal" /><p className="text-sm fx-soft">Ekspor dan impor chat, persona, serta memori melalui file JSON. Tidak ada sinkronisasi akun.</p><div className="mt-3 grid grid-cols-2 gap-2"><Button variant="outline" className="fx-subtle fx-press rounded-2xl" onClick={exportData}><Download className="mr-2 h-4 w-4" />Ekspor</Button><Button variant="outline" className="fx-subtle fx-press rounded-2xl" onClick={() => importInputRef.current?.click()}><Upload className="mr-2 h-4 w-4" />Impor</Button></div><input ref={importInputRef} type="file" accept="application/json" className="hidden" onChange={(event) => importData(event.target.files?.[0])} /></Card></PageShell>}

      {screen === "chat" && <div className="furina-composer-dock absolute inset-x-0 bottom-0 z-30 px-4 pb-[max(.8rem,env(safe-area-inset-bottom))]"><div className="mx-auto max-w-3xl rounded-[28px] fx-card p-3 shadow-2xl">{pendingImage && <div className="mb-3 flex items-center gap-3 rounded-2xl fx-subtle p-2"><img src={pendingImage.dataUrl} alt="Preview" className="h-14 w-14 rounded-2xl object-cover" /><p className="min-w-0 flex-1 truncate text-sm">{pendingImage.name}</p><Button variant="ghost" size="icon" className="rounded-full" onClick={() => setPendingImage(null)}><X className="h-4 w-4" /></Button></div>}<div className="flex items-end gap-2 rounded-[24px] fx-subtle p-2"><input ref={imageInputRef} type="file" accept="image/*" className="hidden" onChange={handleImagePick} /><Button variant="ghost" size="icon" className="rounded-full" onClick={() => imageInputRef.current?.click()}><ImageIcon className="h-5 w-5" /></Button><Textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} rows={1} placeholder="Ketik pesan…" className="min-h-11 max-h-32 flex-1 resize-none border-0 bg-transparent text-white shadow-none focus-visible:ring-0" /><Button size="icon" className={`rounded-full ${sending ? "bg-red-500" : "bg-sky-500"}`} onClick={() => sending ? stopGeneration() : sendMessage()}>{sending ? <X className="h-4 w-4" /> : <Send className="h-4 w-4" />}</Button></div></div></div>}
    </div>
  );
}

function PageShell({ children }: { children: ReactNode }) {
  return <main className="furina-page absolute inset-x-0 bottom-0 top-0 z-10 overflow-y-auto px-4 pb-8 pt-24"><div className="mx-auto max-w-5xl space-y-4">{children}</div></main>;
}

function PageTitle({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="rounded-[30px] fx-card p-5"><p className="text-xs uppercase tracking-[.28em] text-sky-200/70">{eyebrow}</p><h2 className="mt-2 text-2xl font-semibold">{title}</h2><p className="mt-2 text-sm fx-soft">{description}</p></div>;
}

function Card({ children }: { children: ReactNode }) {
  return <section className="rounded-[28px] fx-card p-5 shadow-xl">{children}</section>;
}

function Metric({ icon: Icon, label, value }: { icon: typeof Sparkles; label: string; value: string }) {
  return <div className="rounded-[26px] fx-card p-4"><Icon className="h-4 w-4 text-sky-200/80" /><p className="mt-4 text-2xl font-semibold">{value}</p><p className="mt-1 text-xs fx-soft">{label}</p></div>;
}

function QuickButton({ icon: Icon, title, onClick }: { icon: typeof Plus; title: string; onClick: () => void }) {
  return <button onClick={onClick} className="flex w-full items-center gap-3 rounded-2xl fx-subtle px-4 py-3 text-left text-sm"><Icon className="h-4 w-4 text-sky-200" />{title}</button>;
}

function SettingTitle({ icon: Icon, title }: { icon: typeof User; title: string }) {
  return <div className="mb-4 flex items-center gap-2"><Icon className="h-4 w-4 text-sky-200" /><h3 className="font-semibold">{title}</h3></div>;
}

async function compressImage(file: File, maxDimension: number, quality: number): Promise<string> {
  const source = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
  const image = await new Promise<HTMLImageElement>((resolve, reject) => {
    const element = new Image();
    element.onload = () => resolve(element);
    element.onerror = () => reject(new Error("Gambar tidak dapat dibuka."));
    element.src = source;
  });
  const ratio = Math.min(1, maxDimension / Math.max(image.naturalWidth, image.naturalHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(image.naturalWidth * ratio));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * ratio));
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) return source;
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", quality);
}
