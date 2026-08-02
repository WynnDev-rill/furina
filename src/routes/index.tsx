import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Bot,
  Brain,
  Check,
  Cloud,
  Cpu,
  Database,
  Download,
  HardDrive,
  History,
  Home,
  Image as ImageIcon,
  LayoutDashboard,
  LogIn,
  Loader2,
  Menu,
  Moon,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  User,
  Volume2,
  VolumeX,
  WifiOff,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

import furinaDefault from "@/assets/furina.jpg";
import { lovable } from "@/integrations/lovable";
import { chatWithFurina } from "@/lib/furina.chat";
import { buildFurinaSystemPrompt } from "@/lib/furina.persona";
import { speakWithVoicevox, VOICEVOX_SPEAKERS } from "@/lib/furina.voice";
import profile from "../../shared/furina-profile.json";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Furina — AI Companion" },
      {
        name: "description",
        content: "Furina companion pribadi dengan Lovable AI, model offline, dan memori bersama.",
      },
    ],
  }),
  component: FurinaApp,
});

type Screen = "chat" | "history" | "dashboard" | "models" | "settings";
type ThemeMode = "dark" | "light";
type MessageStatus = "sending" | "sent" | "read" | "failed";
type AiMode = "online" | "offline";

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
  mode: AiMode;
  source: "lovable" | "offline";
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
  useOnlineAi: () => boolean;
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
  conversations: "furina:v3:conversations",
  active: "furina:v3:active",
  shared: "furina:shared-state:v1",
  theme: "furina:v3:theme",
  screen: "furina:v3:screen",
  clientKey: "furina:v3:client-key",
  voice: "furina:v3:voice",
};

const DEFAULT_SHARED: SharedState = {
  version: 1,
  name: profile.name,
  persona: "",
  language: "auto",
  memories: [],
};

const DEFAULT_NATIVE: NativeStatus = {
  mode: "online",
  source: "lovable",
  activeModelId: "",
  installed: false,
  busy: false,
  supportsImage: false,
  multimodalReady: false,
  canUseOffline: false,
};

function uid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `furina-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function newConversation(): Conversation {
  const timestamp = Date.now();
  return { id: uid(), title: "Percakapan baru", messages: [], updatedAt: timestamp };
}

function safeParse<T>(value: string | null, fallback: T): T {
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
    ? Array.from(
        new Set(
          raw.memories
            .filter((memory): memory is string => typeof memory === "string")
            .map((memory) => clip(memory, 240))
            .filter((memory) => memory.length >= 3),
        ),
      ).slice(-80)
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
    .filter((item): item is Conversation => !!item && typeof item === "object")
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

function deriveTitle(text: string, hasImage: boolean) {
  return clip(text, 42) || (hasImage ? "Percakapan gambar" : "Percakapan baru");
}

function relativeTime(timestamp: number, clock: number) {
  if (!clock) return "";
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
  const durable = [
    /\b(?:aku|saya)\s+(?:suka|menyukai|lebih suka|tidak suka|benci|tinggal|punya|memiliki|biasanya|sedang membangun|sedang mengerjakan|ingin|berencana|menargetkan)\b/i,
    /\b(?:nama(?:ku| saya)|aku bernama|saya bernama|targetku|tujuanku|proyekku|pekerjaanku|hobiku)\b/i,
    /\b(?:ibu|ayah|kakak|adik|pasangan|teman dekat|peliharaan)\b.{0,90}\b(?:bernama|tinggal|suka|sedang)\b/i,
  ];
  return durable.some((pattern) => pattern.test(cleaned)) ? [cleaned] : [];
}

function relevantMemories(query: string, memories: string[]) {
  const terms = new Set(query.toLowerCase().split(/[^a-z0-9À-ÿ]+/i).filter((term) => term.length >= 3));
  return memories
    .map((memory, index) => ({
      memory,
      index,
      score: memory
        .toLowerCase()
        .split(/[^a-z0-9À-ÿ]+/i)
        .reduce((score, term) => score + (terms.has(term) ? 1 : 0), 0),
    }))
    .sort((left, right) => right.score - left.score || right.index - left.index)
    .slice(0, 20)
    .map((entry) => entry.memory);
}

function nativeBridge() {
  return typeof window !== "undefined" ? window.FurinaNative : undefined;
}

function FurinaApp() {
  const chat = useServerFn(chatWithFurina);
  const speak = useServerFn(speakWithVoicevox);
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
  const [clock, setClock] = useState(0);
  const [memoryDraft, setMemoryDraft] = useState("");
  const [online, setOnline] = useState(true);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceSpeaker, setVoiceSpeaker] = useState(2);
  const [voiceBusyId, setVoiceBusyId] = useState("");
  const [voicePlayingId, setVoicePlayingId] = useState("");

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const importInputRef = useRef<HTMLInputElement | null>(null);
  const activeNativeRequest = useRef<{
    requestId: string;
    conversationId: string;
    assistantMessageId: string;
  } | null>(null);
  const clientKeyRef = useRef("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const voiceCacheRef = useRef(new Map<string, string>());

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId),
    [conversations, activeId],
  );
  const messages = activeConversation?.messages ?? [];
  const activeMode: AiMode = nativeBridge() ? nativeStatus.mode : "online";

  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedConversations = normalizeConversations(safeParse(localStorage.getItem(STORAGE.conversations), []));
    const initialConversations = storedConversations.length ? storedConversations : [newConversation()];
    const savedActive = localStorage.getItem(STORAGE.active);
    const chosenActive = savedActive && initialConversations.some((item) => item.id === savedActive)
      ? savedActive
      : initialConversations[0].id;

    const locallyStoredShared = normalizeShared(safeParse(localStorage.getItem(STORAGE.shared), DEFAULT_SHARED));
    let initialShared = locallyStoredShared;
    const bridge = nativeBridge();
    if (bridge) {
      try {
        initialShared = normalizeShared(safeParse(bridge.getSharedState(), locallyStoredShared));
      } catch {
        initialShared = locallyStoredShared;
      }
    }

    setConversations(initialConversations);
    setActiveId(chosenActive);
    setShared(initialShared);
    setTheme(localStorage.getItem(STORAGE.theme) === "light" ? "light" : "dark");
    const savedScreen = localStorage.getItem(STORAGE.screen);
    if (["chat", "history", "dashboard", "models", "settings"].includes(savedScreen || "")) {
      setScreen(savedScreen as Screen);
    }
    const existingClientKey = localStorage.getItem(STORAGE.clientKey) || uid();
    localStorage.setItem(STORAGE.clientKey, existingClientKey);
    clientKeyRef.current = existingClientKey;
    setClock(Date.now());

    const storedVoice = safeParse<{ enabled?: boolean; speaker?: number }>(localStorage.getItem(STORAGE.voice), {});
    setVoiceEnabled(Boolean(storedVoice.enabled));
    if (typeof storedVoice.speaker === "number") setVoiceSpeaker(storedVoice.speaker);
  }, []);

  useEffect(() => {
    const sync = () => setOnline(navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE.voice, JSON.stringify({ enabled: voiceEnabled, speaker: voiceSpeaker }));
    voiceCacheRef.current.clear();
  }, [voiceEnabled, voiceSpeaker]);

  useEffect(() => {
    if (typeof document === "undefined") return;
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
    if (typeof window === "undefined") return;
    localStorage.setItem(STORAGE.screen, screen);
  }, [screen]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const normalized = normalizeShared(shared);
    localStorage.setItem(STORAGE.shared, JSON.stringify(normalized));
    const bridge = nativeBridge();
    if (bridge) {
      try {
        bridge.saveSharedState(JSON.stringify(normalized));
      } catch {
        // Browser mode still keeps the local copy.
      }
    }
  }, [shared]);

  useEffect(() => {
    const updateNative = () => {
      const bridge = nativeBridge();
      if (!bridge) {
        setNativeStatus(DEFAULT_NATIVE);
        return;
      }
      try {
        setNativeStatus((previous) => ({ ...previous, ...safeParse(bridge.getStatus(), DEFAULT_NATIVE) }));
      } catch {
        setNativeStatus(DEFAULT_NATIVE);
      }
    };
    updateNative();
    const timer = window.setInterval(() => {
      if (!document.hidden) updateNative();
    }, 2500);
    const visibility = () => !document.hidden && updateNative();
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("furina-ai-mode-changed", updateNative as EventListener);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("furina-ai-mode-changed", updateNative as EventListener);
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
      setConversations((previous) => previous.map((conversation) =>
        conversation.id === request.conversationId
          ? {
              ...conversation,
              updatedAt: Date.now(),
              messages: conversation.messages.map((message) =>
                message.id === request.assistantMessageId
                  ? { ...message, content: `${message.content}${String(detail.token || "")}`, status: "sent" }
                  : message,
              ),
            }
          : conversation,
      ));
    };
    const completeListener = (event: Event) => {
      const detail = (event as CustomEvent).detail as { requestId?: string };
      const request = activeNativeRequest.current;
      if (!request || detail.requestId !== request.requestId) return;
      setConversations((previous) => previous.map((conversation) =>
        conversation.id === request.conversationId
          ? {
              ...conversation,
              updatedAt: Date.now(),
              messages: conversation.messages.map((message) =>
                message.id === request.assistantMessageId
                  ? {
                      ...message,
                      content: message.content.trim() || "Model selesai tanpa menghasilkan teks. Coba pesan yang lebih singkat.",
                      status: "sent",
                    }
                  : message,
              ),
            }
          : conversation,
      ));
      activeNativeRequest.current = null;
      setSending(false);
    };
    const errorListener = (event: Event) => {
      const detail = (event as CustomEvent).detail as { requestId?: string; error?: string };
      const request = activeNativeRequest.current;
      if (!request || detail.requestId !== request.requestId) return;
      setConversations((previous) => previous.map((conversation) =>
        conversation.id === request.conversationId
          ? {
              ...conversation,
              updatedAt: Date.now(),
              messages: conversation.messages.map((message) =>
                message.id === request.assistantMessageId
                  ? { ...message, content: message.content || detail.error || "Model offline gagal merespons.", status: "failed" }
                  : message,
              ),
            }
          : conversation,
      ));
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
    if (!scrollRef.current || screen !== "chat") return;
    scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending, screen]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);

  function updateConversation(conversationId: string, updater: (messages: Message[]) => Message[]) {
    setConversations((previous) => previous.map((conversation) =>
      conversation.id === conversationId
        ? { ...conversation, messages: updater(conversation.messages), updatedAt: Date.now() }
        : conversation,
    ));
  }

  function startNewConversation() {
    if (sending) {
      toast.info("Hentikan atau tunggu jawaban yang sedang dibuat.");
      return;
    }
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
    setConversations((previous) => previous.map((conversation) =>
      conversation.id === conversationId
        ? { ...conversation, pinned: !conversation.pinned, updatedAt: Date.now() }
        : conversation,
    ));
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

    setConversations((previous) => previous.map((item) =>
      item.id === conversationId
        ? {
            ...item,
            title: item.title === "Percakapan baru" ? deriveTitle(userMessage.content, Boolean(imageDataUrl)) : item.title,
            messages: [...item.messages, userMessage],
            updatedAt: Date.now(),
          }
        : item,
    ));
    setInput("");
    setPendingImage(null);
    setSending(true);

    const bridgeReady = Boolean(nativeBridge()) && nativeStatus.canUseOffline;
    const useOffline = activeMode === "offline" && bridgeReady;
    if (activeMode === "offline" && !bridgeReady) {
      if (!navigator.onLine) {
        updateConversation(conversationId, (items) => items.map((message) =>
          message.id === userMessage.id ? { ...message, status: "failed" } : message,
        ));
        setSending(false);
        toast.error("Model offline belum aktif dan tidak ada jaringan. Unduh model dulu di menu Model AI.");
        return;
      }
      toast.info("Model offline belum aktif — sementara memakai Lovable AI.");
    }

    if (useOffline) {
      const bridge = nativeBridge()!;
      if (imageDataUrl && !nativeStatus.multimodalReady) {
        updateConversation(conversationId, (items) => items.map((message) =>
          message.id === userMessage.id ? { ...message, status: "failed" } : message,
        ));
        setSending(false);
        toast.error(nativeStatus.imageDisabledReason || "Model aktif belum mendukung gambar.");
        return;
      }

      const assistantMessageId = uid();
      updateConversation(conversationId, (items) => [
        ...items.map((message) => message.id === userMessage.id ? { ...message, status: "read" as const } : message),
        { id: assistantMessageId, role: "assistant", content: "", at: Date.now(), status: "sending" },
      ]);
      const requestId = uid();
      activeNativeRequest.current = { requestId, conversationId, assistantMessageId };
      const selectedMemories = relevantMemories(userMessage.content, memories);
      const systemPrompt = buildFurinaSystemPrompt({
        characterName: shared.name,
        persona: shared.persona,
        language: shared.language,
        memories: selectedMemories,
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
        toast.error(error instanceof Error ? error.message : "Model offline gagal dimulai.");
      }
      return;
    }

    if (!navigator.onLine) {
      updateConversation(conversationId, (items) => items.map((message) =>
        message.id === userMessage.id ? { ...message, status: "failed" } : message,
      ));
      setSending(false);
      toast.error("Tidak ada jaringan. Aktifkan model offline agar tetap bisa mengobrol.");
      return;
    }

    try {
      const result = await chat({
        data: {
          messages: contextMessages.slice(-20).map((message) => ({ role: message.role, content: message.content })),
          characterName: shared.name,
          persona: shared.persona,
          language: shared.language,
          sharedMemories: relevantMemories(userMessage.content, memories),
          imageDataUrl,
          clientNow: Date.now(),
          timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
          clientKey: clientKeyRef.current,
        },
      }) as { reply: string; bubbles?: string[] };
      const bubbles = result.bubbles?.length ? result.bubbles : [result.reply];
      const assistantMessages: Message[] = bubbles.map((bubble) => ({
        id: uid(),
        role: "assistant" as const,
        content: bubble,
        at: Date.now(),
        status: "sent" as const,
      }));
      updateConversation(conversationId, (items) => [
        ...items.map((message) => message.id === userMessage.id ? { ...message, status: "read" as const } : message),
        ...assistantMessages,
      ]);
      if (voiceEnabled && assistantMessages[0]) void prefetchVoice(assistantMessages[0]);
    } catch (error) {
      updateConversation(conversationId, (items) => items.map((message) =>
        message.id === userMessage.id ? { ...message, status: "failed" } : message,
      ));
      toast.error(error instanceof Error ? error.message : "Lovable AI gagal merespons.");
    } finally {
      setSending(false);
    }
  }

  async function resolveVoiceUrl(message: Message) {
    const cached = voiceCacheRef.current.get(message.id);
    if (cached) return cached;
    const result = (await speak({ data: { text: message.content, speaker: voiceSpeaker } })) as { audioUrl: string };
    voiceCacheRef.current.set(message.id, result.audioUrl);
    return result.audioUrl;
  }

  /** Menyiapkan audio di latar belakang supaya tombol putar terasa instan. */
  async function prefetchVoice(message: Message) {
    try {
      const url = await resolveVoiceUrl(message);
      void fetch(url, { mode: "no-cors" }).catch(() => undefined);
    } catch {
      // Diamkan; pengguna tetap bisa memutar manual.
    }
  }

  function stopVoice() {
    audioRef.current?.pause();
    audioRef.current = null;
    setVoicePlayingId("");
  }

  async function toggleVoice(message: Message) {
    if (voicePlayingId === message.id) return stopVoice();
    if (!message.content.trim()) return;
    stopVoice();
    setVoiceBusyId(message.id);
    try {
      const url = await resolveVoiceUrl(message);
      const audio = new Audio(url);
      audio.onended = () => setVoicePlayingId("");
      audio.onerror = () => {
        voiceCacheRef.current.delete(message.id);
        setVoicePlayingId("");
        toast.error("Audio suara gagal diputar. Coba lagi.");
      };
      audioRef.current = audio;
      await audio.play();
      setVoicePlayingId(message.id);
    } catch (error) {
      voiceCacheRef.current.delete(message.id);
      toast.error(error instanceof Error ? error.message : "Suara VOICEVOX gagal dibuat.");
    } finally {
      setVoiceBusyId("");
    }
  }

  function stopGeneration() {
    if (!sending || activeMode !== "offline") return;
    try {
      nativeBridge()?.cancelGeneration();
    } catch {}
  }

  async function handleImagePick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.type.startsWith("image/")) return toast.error("Pilih file gambar.");
    if (file.size > 12 * 1024 * 1024) return toast.error("Gambar maksimal 12 MB.");
    try {
      const dataUrl = await compressImage(file, 1280, 0.82);
      setPendingImage({ dataUrl, name: file.name || "Gambar" });
    } catch {
      toast.error("Gambar gagal diproses.");
    }
  }

  function useOnlineMode() {
    try {
      nativeBridge()?.useOnlineAi();
      setNativeStatus((previous) => ({ ...previous, mode: "online", source: "lovable" }));
      toast.success("Lovable AI aktif.");
    } catch {
      toast.error("Mode online tidak dapat diaktifkan.");
    }
  }

  function useOfflineMode() {
    const bridge = nativeBridge();
    if (!bridge) return toast.info("AI offline hanya tersedia di APK Android.");
    try {
      if (!bridge.useOfflineAi()) {
        bridge.openModelManager();
        toast.info("Unduh dan pilih model offline terlebih dahulu.");
        return;
      }
      setNativeStatus((previous) => ({ ...previous, mode: "offline", source: "offline" }));
      toast.success("AI offline aktif.");
    } catch {
      toast.error("Mode offline tidak dapat diaktifkan.");
    }
  }

  async function loginGoogle() {
    try {
      const result = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
      if (result.error) toast.error(result.error.message || "Login Google gagal.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login Google gagal.");
    }
  }

  function addMemory() {
    const memory = clip(memoryDraft, 240);
    if (memory.length < 3) return;
    setShared((previous) => normalizeShared({ ...previous, memories: [...previous.memories, memory] }));
    setMemoryDraft("");
  }

  function exportData() {
    const blob = new Blob([
      JSON.stringify({ app: "Furina", version: 3, exportedAt: new Date().toISOString(), shared, conversations, activeId }, null, 2),
    ], { type: "application/json" });
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
      const backup = JSON.parse(await file.text()) as {
        app?: string;
        shared?: Partial<SharedState>;
        conversations?: unknown;
        activeId?: string;
      };
      if (backup.app !== "Furina") throw new Error("File bukan backup Furina.");
      const importedConversations = normalizeConversations(backup.conversations);
      if (!importedConversations.length) throw new Error("Backup tidak berisi percakapan.");
      if (!confirm("Impor akan mengganti data lokal saat ini. Lanjutkan?")) return;
      setConversations(importedConversations);
      setActiveId(importedConversations.some((item) => item.id === backup.activeId) ? String(backup.activeId) : importedConversations[0].id);
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
        return `${conversation.title} ${conversation.messages.map((message) => message.content).join(" ")}`
          .toLowerCase()
          .includes(keyword);
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
        <div className="flex items-center justify-between">
          <div><p className="text-xs uppercase tracking-[.28em] text-sky-200/70">Furina</p><h2 className="mt-1 text-xl font-semibold">Companion Pribadimu</h2></div>
          <Button variant="ghost" size="icon" className="rounded-full" onClick={() => setMenuOpen(false)}><X className="h-4 w-4" /></Button>
        </div>
        <div className="mt-6 space-y-2">
          {[
            ["chat", Home, "Chat"], ["history", History, "Riwayat"], ["dashboard", LayoutDashboard, "Dashboard"], ["models", Cpu, "Model AI"], ["settings", Settings, "Pengaturan"],
          ].map(([id, Icon, label]) => (
            <button key={String(id)} onClick={() => { setScreen(id as Screen); setMenuOpen(false); }} className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm ${screen === id ? "bg-sky-500/20 ring-1 ring-sky-300/30" : "fx-soft hover:bg-foreground/5"}`}>
              <Icon className="h-4 w-4" /><span>{String(label)}</span>
            </button>
          ))}
        </div>
        <div className="mt-6 rounded-3xl fx-subtle p-4">
          <p className="text-xs uppercase tracking-[.22em] text-sky-200/70">AI aktif</p>
          <p className="mt-2 font-semibold">{activeMode === "offline" ? (nativeStatus.activeModelId || "Model offline") : "Lovable AI"}</p>
          <p className="mt-1 text-xs fx-soft">{activeMode === "offline" ? "Privat, berjalan di perangkat" : "Online, persona dan memori sama"}</p>
        </div>
      </aside>
      {menuOpen && <button aria-label="Tutup menu" className="absolute inset-0 z-40 bg-black/45 backdrop-blur-sm" onClick={() => setMenuOpen(false)} />}

      <header className="absolute inset-x-0 top-0 z-30 px-4 pt-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between rounded-[28px] fx-card px-3 py-3 shadow-2xl ">
          <div className="flex min-w-0 items-center gap-3">
            <Button variant="ghost" size="icon" className="fx-press rounded-full" onClick={() => setMenuOpen(true)}><Menu className="h-5 w-5" /></Button>
            <div className="min-w-0">
              <div className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${activeMode === "offline" ? "bg-violet-400" : online ? "bg-emerald-400" : "bg-amber-400"}`} /><p className="truncate text-sm font-semibold">{shared.name}</p></div>
              <p className="truncate text-xs fx-soft">{activeMode === "offline" ? "AI offline" : online ? "Lovable AI" : "Tidak ada jaringan"}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {screen === "chat" && <Button variant="ghost" size="icon" className="fx-press rounded-full" onClick={startNewConversation}><Plus className="h-5 w-5" /></Button>}
            <Button variant="ghost" size="icon" className="fx-press rounded-full" onClick={() => setTheme((value) => value === "dark" ? "light" : "dark")}>{theme === "dark" ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}</Button>
          </div>
        </div>
      </header>

      {screen === "chat" && (
        <main ref={scrollRef} className="absolute inset-x-0 bottom-0 top-0 z-10 overflow-y-auto px-4 pb-48 pt-24">
          <div className="mx-auto flex min-h-full max-w-3xl flex-col justify-end gap-3">
            {!messages.length && (
              <div className="max-w-[88%] self-start rounded-[26px] fx-card px-4 py-4 shadow-2xl ">
                <p className="text-sm leading-relaxed">{profile.defaultGreeting}</p>
                <p className="mt-2 text-[11px] fx-soft">{activeMode === "offline" ? "Mode offline siap" : "Lovable AI siap"}</p>
              </div>
            )}
            {messages.map((message, index) => {
              const user = message.role === "user";
              const speaking = voicePlayingId === message.id;
              return (
                <div
                  key={message.id}
                  className={`fx-rise flex flex-col ${user ? "items-end" : "items-start"}`}
                  style={{ animationDelay: `${Math.min(index, 6) * 35}ms` }}
                >
                  <div className={`w-fit max-w-[88%] rounded-[25px] px-4 py-3 text-sm shadow-xl ${user ? "fx-bubble-user" : "fx-bubble-ai"}`}>
                    {message.imageDataUrl && <img src={message.imageDataUrl} alt="Lampiran" className="mb-3 max-h-72 rounded-2xl object-cover" />}
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content || (message.role === "assistant" ? "…" : "")}</p>
                  </div>
                  <div className="mt-1 flex items-center gap-2 px-2 text-[11px] fx-soft">
                    <span>{formatTime(message.at)}</span>
                    {!user && message.content.trim() && (
                      <button
                        aria-label={speaking ? "Hentikan suara" : "Dengarkan suara Furina"}
                        className="fx-press flex items-center gap-1 rounded-full fx-subtle px-2 py-0.5 text-[10px]"
                        onClick={() => toggleVoice(message)}
                        disabled={voiceBusyId === message.id}
                      >
                        {voiceBusyId === message.id
                          ? <Loader2 className="h-3 w-3 animate-spin" />
                          : speaking
                            ? <VolumeX className="h-3 w-3" />
                            : <Volume2 className="h-3 w-3" />}
                        {speaking ? "Berhenti" : "Suara"}
                      </button>
                    )}
                    {message.status === "failed" && user && <button className="fx-press rounded-full bg-red-500/90 px-2 py-0.5 text-[10px] text-white" onClick={() => sendMessage(message.failedPayload || message.content, message.imageDataUrl)}>Kirim ulang</button>}
                  </div>
                </div>
              );
            })}
            {sending && activeMode === "online" && <div className="fx-rise self-start rounded-[25px] fx-card px-4 py-3"><div className="flex gap-1"><span className="h-2 w-2 animate-bounce rounded-full bg-current opacity-60" /><span className="h-2 w-2 animate-bounce rounded-full bg-current opacity-60 [animation-delay:120ms]" /><span className="h-2 w-2 animate-bounce rounded-full bg-current opacity-60 [animation-delay:240ms]" /></div></div>}
          </div>
        </main>
      )}

      {screen === "history" && <PageShell><PageTitle eyebrow="Tersimpan lokal" title="Riwayat Percakapan" description="Chat online dan offline pada tampilan ini tersimpan di perangkat." /><div className="rounded-3xl fx-card p-3 "><div className="flex items-center gap-2 rounded-2xl fx-subtle px-3 py-2"><Search className="h-4 w-4 fx-soft" /><input value={historySearch} onChange={(event) => setHistorySearch(event.target.value)} placeholder="Cari percakapan…" className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400" /></div><div className="mt-3 flex gap-2">{[["all","Semua"],["image","Gambar"],["pinned","Pinned"]].map(([id,label]) => <button key={id} onClick={() => setHistoryFilter(id as typeof historyFilter)} className={`rounded-full px-3 py-1.5 text-xs ${historyFilter === id ? "bg-sky-500" : "fx-subtle text-slate-200/70"}`}>{label}</button>)}</div></div><div className="mt-4 grid gap-3">{filteredConversations.map((conversation) => { const last = conversation.messages[conversation.messages.length - 1]; return <article key={conversation.id} className="rounded-3xl fx-card p-4 "><div className="flex items-start justify-between gap-3"><button className="min-w-0 flex-1 text-left" onClick={() => selectConversation(conversation.id)}><div className="flex items-center gap-2"><p className="truncate text-sm font-semibold">{conversation.title}</p>{conversation.pinned && <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px]">Pinned</span>}</div><p className="mt-1 line-clamp-2 text-sm fx-soft">{last?.content || "Belum ada pesan."}</p><p className="mt-2 text-[11px] fx-soft">{relativeTime(conversation.updatedAt, clock)} · {conversation.messages.length} pesan</p></button><div className="flex gap-1"><Button variant="ghost" size="sm" className="rounded-full" onClick={() => togglePinned(conversation.id)}>{conversation.pinned ? "Lepas" : "Pin"}</Button><Button variant="ghost" size="icon" className="rounded-full text-red-200" onClick={() => deleteConversation(conversation.id)}><Trash2 className="h-4 w-4" /></Button></div></div></article>; })}</div></PageShell>}

      {screen === "dashboard" && <PageShell><PageTitle eyebrow="Ringkasan" title="Dashboard" description="Status AI, memori, dan data lokal dalam satu tempat." /><div className="grid grid-cols-2 gap-3"><Metric icon={activeMode === "offline" ? Cpu : Cloud} label="Mode aktif" value={activeMode === "offline" ? "Offline" : "Lovable"} /><Metric icon={History} label="Percakapan" value={String(stats.conversations)} /><Metric icon={ImageIcon} label="Gambar" value={String(stats.images)} /><Metric icon={Brain} label="Memori" value={String(stats.memories)} /></div><Card><h3 className="font-semibold">Sumber AI</h3><p className="mt-2 text-sm fx-soft">Persona dan memori bersama dikirim ke Lovable AI maupun model offline, sehingga karakter tidak berubah ketika mode diganti.</p><div className="mt-4 grid grid-cols-2 gap-2"><Button onClick={useOnlineMode} className={`rounded-2xl ${activeMode === "online" ? "bg-sky-500" : "bg-white/10"}`}><Cloud className="mr-2 h-4 w-4" />Online</Button><Button onClick={useOfflineMode} className={`rounded-2xl ${activeMode === "offline" ? "bg-violet-500" : "bg-white/10"}`}><Cpu className="mr-2 h-4 w-4" />Offline</Button></div></Card><Card><h3 className="font-semibold">Aksi cepat</h3><div className="mt-3 grid gap-2"><QuickButton icon={Plus} title="Chat baru" onClick={startNewConversation} /><QuickButton icon={Bot} title="Kelola model" onClick={() => setScreen("models")} /><QuickButton icon={Download} title="Ekspor backup" onClick={exportData} /></div></Card></PageShell>}

      {screen === "models" && <PageShell><PageTitle eyebrow="AI di perangkat" title="Kelola Model" description="Lovable AI untuk kualitas online; model lokal untuk privasi dan penggunaan tanpa jaringan." /><Card><div className="flex items-start gap-3"><div className="rounded-2xl bg-sky-500/20 p-3"><Cloud className="h-5 w-5" /></div><div className="flex-1"><div className="flex items-center justify-between"><h3 className="font-semibold">Lovable AI</h3>{activeMode === "online" && <span className="rounded-full bg-emerald-500/20 px-2 py-1 text-[10px] text-emerald-100">Aktif</span>}</div><p className="mt-1 text-sm fx-soft">Mode online dengan persona dan memori bersama.</p><Button onClick={useOnlineMode} className="mt-3 rounded-2xl bg-sky-500">Gunakan online</Button></div></div></Card><Card><div className="flex items-start gap-3"><div className="rounded-2xl bg-violet-500/20 p-3"><Cpu className="h-5 w-5" /></div><div className="flex-1"><div className="flex items-center justify-between"><h3 className="font-semibold">{nativeStatus.activeModelId || "Model Offline"}</h3>{activeMode === "offline" && <span className="rounded-full bg-violet-500/20 px-2 py-1 text-[10px] text-violet-100">Aktif</span>}</div><p className="mt-1 text-sm fx-soft">{nativeBridge() ? nativeStatus.installed ? `Terpasang${nativeStatus.multimodalReady ? " · teks + gambar" : " · teks"}` : "Belum ada model aktif." : "Tersedia melalui APK Android."}</p><div className="mt-3 flex flex-wrap gap-2"><Button onClick={useOfflineMode} className="rounded-2xl bg-violet-500">Gunakan offline</Button><Button variant="outline" className="fx-subtle fx-press rounded-2xl" onClick={() => nativeBridge()?.openModelManager()} disabled={!nativeBridge()}>Unduh / ganti model</Button></div></div></div></Card><Card><h3 className="font-semibold">Cara kerja</h3><div className="mt-3 space-y-3 text-sm fx-soft"><p className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-emerald-300" />Model offline tetap tersimpan ketika APK diperbarui.</p><p className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-emerald-300" />Memori bersama digunakan oleh semua model.</p><p className="flex gap-2"><WifiOff className="mt-0.5 h-4 w-4 text-sky-300" />Saat jaringan tidak ada, APK dapat dibuka melalui antarmuka lokal.</p></div></Card></PageShell>}

      {screen === "settings" && <PageShell><PageTitle eyebrow="Personalisasi" title="Pengaturan" description="Satu persona dan satu memori untuk seluruh mode AI." /><Card><SettingTitle icon={User} title="Persona bersama" /><label className="text-xs fx-soft">Nama karakter</label><Input value={shared.name} onChange={(event) => setShared((previous) => ({ ...previous, name: event.target.value.slice(0, 40) }))} className="fx-subtle mt-2" /><label className="mt-4 block text-xs fx-soft">Kepribadian tambahan</label><Textarea rows={5} value={shared.persona} onChange={(event) => setShared((previous) => ({ ...previous, persona: event.target.value.slice(0, 6000) }))} placeholder="Kosongkan untuk memakai persona Furina bawaan." className="fx-subtle mt-2" /><label className="mt-4 block text-xs fx-soft">Bahasa balasan</label><select value={shared.language} onChange={(event) => setShared((previous) => ({ ...previous, language: event.target.value as SharedState["language"] }))} className="fx-subtle mt-2 h-11 w-full rounded-xl px-3 text-sm"><option value="auto">Ikuti bahasa pengguna</option><option value="id">Indonesia</option><option value="en">English</option><option value="ja">日本語</option></select></Card><Card><SettingTitle icon={Brain} title="Memori bersama" /><p className="text-sm fx-soft">Memori ini disimpan di perangkat dan diberikan kepada Lovable AI serta model offline ketika relevan.</p><div className="mt-3 flex gap-2"><Input value={memoryDraft} onChange={(event) => setMemoryDraft(event.target.value)} onKeyDown={(event) => event.key === "Enter" && addMemory()} placeholder="Contoh: Wynn menyukai jawaban yang langsung." className="fx-subtle" /><Button size="icon" className="shrink-0 rounded-xl bg-sky-500" onClick={addMemory}><Plus className="h-4 w-4" /></Button></div><div className="mt-3 max-h-60 space-y-2 overflow-y-auto">{shared.memories.slice().reverse().map((memory) => <div key={memory} className="flex items-start gap-2 rounded-2xl fx-subtle px-3 py-2 text-sm"><p className="flex-1 fx-text">{memory}</p><button onClick={() => setShared((previous) => ({ ...previous, memories: previous.memories.filter((item) => item !== memory) }))}><X className="h-4 w-4 text-slate-400" /></button></div>)}{!shared.memories.length && <p className="rounded-2xl border border-dashed border-white/10 p-4 text-center text-sm text-slate-400">Belum ada memori bersama.</p>}</div></Card><Card><SettingTitle icon={Volume2} title="Suara VOICEVOX" /><p className="text-sm fx-soft">Suara Furina memakai VOICEVOX gratis. Teks non-Jepang diterjemahkan otomatis sebelum dibacakan, dan balasan terakhir disiapkan di latar belakang agar tombol putar terasa instan.</p><div className="mt-3 flex items-center justify-between rounded-2xl fx-subtle px-3 py-2"><span className="text-sm">Siapkan suara otomatis</span><button onClick={() => setVoiceEnabled((value) => !value)} className={`fx-press h-7 w-12 rounded-full transition-colors ${voiceEnabled ? "bg-sky-500" : "bg-foreground/20"}`}><span className={`block h-6 w-6 rounded-full bg-white transition-transform ${voiceEnabled ? "translate-x-6" : "translate-x-0.5"}`} /></button></div><label className="mt-4 block text-xs fx-soft">Karakter suara</label><select value={voiceSpeaker} onChange={(event) => { stopVoice(); setVoiceSpeaker(Number(event.target.value)); }} className="fx-subtle mt-2 h-11 w-full rounded-xl px-3 text-sm">{VOICEVOX_SPEAKERS.map((speaker) => <option key={speaker.id} value={speaker.id}>{speaker.label}</option>)}</select><Button className="fx-press mt-3 w-full rounded-2xl bg-sky-500" onClick={() => toggleVoice({ id: "preview-voice", role: "assistant", content: "Halo, aku Furina. Beginilah suaraku terdengar.", at: Date.now() })}>{voiceBusyId === "preview-voice" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Volume2 className="mr-2 h-4 w-4" />}Coba suara</Button></Card><Card><SettingTitle icon={Database} title="Akun dan backup" /><Button className="fx-subtle fx-press w-full rounded-2xl" onClick={loginGoogle}><LogIn className="mr-2 h-4 w-4" />Masuk dengan Google</Button><div className="mt-3 grid grid-cols-2 gap-2"><Button variant="outline" className="fx-subtle fx-press rounded-2xl" onClick={exportData}><Download className="mr-2 h-4 w-4" />Ekspor</Button><Button variant="outline" className="fx-subtle fx-press rounded-2xl" onClick={() => importInputRef.current?.click()}><Upload className="mr-2 h-4 w-4" />Impor</Button></div><input ref={importInputRef} type="file" accept="application/json" className="hidden" onChange={(event) => importData(event.target.files?.[0])} /></Card></PageShell>}

      {screen === "chat" && <div className="absolute inset-x-0 bottom-[82px] z-30 px-4"><div className="mx-auto max-w-3xl rounded-[28px] fx-card p-3 shadow-2xl ">{pendingImage && <div className="mb-3 flex items-center gap-3 rounded-2xl fx-subtle p-2"><img src={pendingImage.dataUrl} alt="Preview" className="h-14 w-14 rounded-2xl object-cover" /><p className="min-w-0 flex-1 truncate text-sm">{pendingImage.name}</p><Button variant="ghost" size="icon" className="rounded-full" onClick={() => setPendingImage(null)}><X className="h-4 w-4" /></Button></div>}<div className="flex items-end gap-2 rounded-[24px] fx-subtle p-2"><input ref={imageInputRef} type="file" accept="image/*" className="hidden" onChange={handleImagePick} /><Button variant="ghost" size="icon" className="rounded-full" onClick={() => imageInputRef.current?.click()}><ImageIcon className="h-5 w-5" /></Button><Textarea ref={inputRef} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} rows={1} placeholder="Ketik pesan…" className="min-h-11 max-h-32 flex-1 resize-none border-0 bg-transparent text-white shadow-none focus-visible:ring-0" /><Button size="icon" className={`rounded-full ${sending && activeMode === "offline" ? "bg-red-500" : "bg-sky-500"}`} onClick={() => sending && activeMode === "offline" ? stopGeneration() : sendMessage()} disabled={sending && activeMode === "online"}>{sending && activeMode === "offline" ? <X className="h-4 w-4" /> : <Send className="h-4 w-4" />}</Button></div></div></div>}

      <nav className="absolute inset-x-0 bottom-0 z-30 px-3 pb-3"><div className="mx-auto grid max-w-5xl grid-cols-5 rounded-[26px] fx-card p-2 shadow-2xl ">{[["chat",Home,"Chat"],["history",History,"Riwayat"],["dashboard",LayoutDashboard,"Dashboard"],["models",Bot,"Model"],["settings",Settings,"Pengaturan"]].map(([id,Icon,label]) => <button key={String(id)} onClick={() => setScreen(id as Screen)} className={`flex flex-col items-center rounded-[18px] px-1 py-2 text-[10px] ${screen === id ? "bg-sky-500/18 text-sky-100" : "fx-soft"}`}><Icon className="mb-1 h-4 w-4" />{String(label)}</button>)}</div></nav>
    </div>
  );
}

function PageShell({ children }: { children: ReactNode }) {
  return <main className="absolute inset-x-0 bottom-0 top-0 z-10 overflow-y-auto px-4 pb-28 pt-24"><div className="mx-auto max-w-5xl space-y-4">{children}</div></main>;
}

function PageTitle({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="rounded-[30px] fx-card p-5 "><p className="text-xs uppercase tracking-[.28em] text-sky-200/70">{eyebrow}</p><h2 className="mt-2 text-2xl font-semibold">{title}</h2><p className="mt-2 text-sm fx-soft">{description}</p></div>;
}

function Card({ children }: { children: ReactNode }) {
  return <section className="rounded-[28px] fx-card p-5 shadow-xl ">{children}</section>;
}

function Metric({ icon: Icon, label, value }: { icon: typeof Sparkles; label: string; value: string }) {
  return <div className="rounded-[26px] fx-card p-4 "><Icon className="h-4 w-4 text-sky-200/80" /><p className="mt-4 text-2xl font-semibold">{value}</p><p className="mt-1 text-xs fx-soft">{label}</p></div>;
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
