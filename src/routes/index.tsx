import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Bot,
  Cpu,
  Database,
  HardDrive,
  History,
  Home,
  Image as ImageIcon,
  LayoutDashboard,
  LogIn,
  LogOut,
  Menu,
  Moon,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  Sun,
  Trash2,
  User,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

import furinaDefault from "@/assets/furina.jpg";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable";
import { chatWithFurina } from "@/lib/furina.functions";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Furina — AI Companion" },
      {
        name: "description",
        content:
          "Furina companion dengan chat hangat, riwayat percakapan, dashboard cerdas, dan tampilan offline-first modern.",
      },
    ],
  }),
  component: FurinaApp,
});

type MsgStatus = "sending" | "sent" | "read" | "failed";
type Msg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: number;
  status?: MsgStatus;
  imageDataUrl?: string;
  failedPayload?: string;
};

type Conversation = {
  id: string;
  title: string;
  messages: Msg[];
  updatedAt: number;
  pinned?: boolean;
};

type ThemeMode = "dark" | "light";
type Screen = "chat" | "history" | "dashboard" | "models" | "settings";
type HistoryFilter = "all" | "chat" | "gambar" | "pinned";

type ModelCard = {
  id: string;
  name: string;
  size: string;
  badge: string;
  description: string;
  recommended: string;
  status: "installed" | "available" | "coming-soon";
};

const STORAGE = {
  convos: "furina:v2:conversations",
  activeId: "furina:v2:activeConvoId",
  name: "furina:v2:name",
  persona: "furina:v2:persona",
  bg: "furina:v2:bg",
  theme: "furina:v2:theme",
  screen: "furina:v2:screen",
  selectedModel: "furina:v2:selectedModel",
  guestId: "furina:v2:guestId",
};

const MODEL_CATALOG: ModelCard[] = [
  {
    id: "lovable-online",
    name: "Lovable AI",
    size: "Cloud",
    badge: "Online opsional",
    description: "Mode cloud untuk kualitas balasan penuh dan fitur server-side.",
    recommended: "Dipakai saat user memang ingin mode online.",
    status: "available",
  },
  {
    id: "qwen35-4b",
    name: "Qwen3.5-4B",
    size: "±3.3 GB",
    badge: "Teks + gambar",
    description: "Model utama untuk chat offline dan analisis gambar langsung di perangkat.",
    recommended: "Paling cocok untuk Snapdragon 8 Gen 1 / 8s Gen 3 / Dimensity 8200 ke atas.",
    status: "installed",
  },
  {
    id: "josie-4b",
    name: "JOSIE 4B Instruct",
    size: "±2.5 GB",
    badge: "Percakapan natural",
    description: "Alternatif dialog yang terasa ekspresif dan ringan untuk chatting biasa.",
    recommended: "Cocok untuk 8 GB RAM ke atas.",
    status: "available",
  },
  {
    id: "basically-human-4b",
    name: "Basically-Human-4B",
    size: "±2.4 GB",
    badge: "Dialog manusiawi",
    description: "Fokus ke percakapan santai yang terasa lebih natural.",
    recommended: "Pilihan ringan untuk percakapan teks offline.",
    status: "available",
  },
  {
    id: "arityflow-4b",
    name: "ArityFlow 4B",
    size: "±2.3 GB",
    badge: "Cepat & efisien",
    description: "Mode cadangan untuk perangkat yang butuh performa lebih stabil.",
    recommended: "Bagus untuk penggunaan hemat daya.",
    status: "coming-soon",
  },
];

function newConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "Percakapan baru",
    messages: [],
    updatedAt: Date.now(),
  };
}

function getOrCreateGuestId() {
  if (typeof window === "undefined") return "guest-ssr";
  const existing = localStorage.getItem(STORAGE.guestId);
  if (existing) return existing;
  const next = crypto.randomUUID();
  localStorage.setItem(STORAGE.guestId, next);
  return next;
}

function relTime(ts: number, now: number) {
  const diff = now - ts;
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < minute) return "baru saja";
  if (diff < hour) return `${Math.max(1, Math.round(diff / minute))} m lalu`;
  if (diff < day) return `${Math.max(1, Math.round(diff / hour))} j lalu`;
  if (diff < 7 * day) return `${Math.max(1, Math.round(diff / day))} h lalu`;
  return new Date(ts).toLocaleDateString("id-ID");
}

function fmtTime(ts: number) {
  return new Date(ts).toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function deriveTitle(text: string) {
  const compact = text.replace(/\s+/g, " ").trim();
  return compact.slice(0, 40) || "Percakapan baru";
}

function FurinaApp() {
  const chat = useServerFn(chatWithFurina);
  const [authUser, setAuthUser] = useState<{ id: string; email?: string } | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [screen, setScreen] = useState<Screen>("chat");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [name, setName] = useState("Furina");
  const [persona, setPersona] = useState("");
  const [bg, setBg] = useState(furinaDefault);
  const [historySearch, setHistorySearch] = useState("");
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>("all");
  const [pendingImage, setPendingImage] = useState<{ dataUrl: string; name: string } | null>(null);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("qwen35-4b");
  const [menuOpen, setMenuOpen] = useState(false);

  const guestIdRef = useRef(getOrCreateGuestId());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);

  const userId = authUser?.id ?? guestIdRef.current;
  const activeConvo = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId),
    [conversations, activeId],
  );
  const messages = activeConvo?.messages ?? [];
  const now = Date.now();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.user) {
        setAuthUser({ id: data.session.user.id, email: data.session.user.email ?? undefined });
      }
      setAuthReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthUser(
        session?.user
          ? { id: session.user.id, email: session.user.email ?? undefined }
          : null,
      );
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const rawConversations = localStorage.getItem(STORAGE.convos);
      const loadedConversations = rawConversations
        ? (JSON.parse(rawConversations) as Conversation[])
        : [newConversation()];
      const fallbackConversations = loadedConversations.length ? loadedConversations : [newConversation()];
      setConversations(fallbackConversations);

      const savedActiveId = localStorage.getItem(STORAGE.activeId);
      const chosenId =
        savedActiveId && fallbackConversations.some((conversation) => conversation.id === savedActiveId)
          ? savedActiveId
          : fallbackConversations[0]?.id ?? "";
      setActiveId(chosenId || fallbackConversations[0]?.id || "");

      const savedName = localStorage.getItem(STORAGE.name);
      if (savedName) setName(savedName);
      const savedPersona = localStorage.getItem(STORAGE.persona);
      if (savedPersona) setPersona(savedPersona);
      const savedBackground = localStorage.getItem(STORAGE.bg);
      if (savedBackground) setBg(savedBackground);
      const savedTheme = localStorage.getItem(STORAGE.theme);
      if (savedTheme === "light" || savedTheme === "dark") setTheme(savedTheme);
      const savedScreen = localStorage.getItem(STORAGE.screen);
      if (savedScreen === "chat" || savedScreen === "history" || savedScreen === "dashboard" || savedScreen === "models" || savedScreen === "settings") {
        setScreen(savedScreen);
      }
      const savedModel = localStorage.getItem(STORAGE.selectedModel);
      if (savedModel) setSelectedModel(savedModel);
    } catch {
      setConversations([newConversation()]);
    }
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  useEffect(() => {
    if (!conversations.length) return;
    try {
      localStorage.setItem(STORAGE.convos, JSON.stringify(conversations));
    } catch {}
  }, [conversations]);

  useEffect(() => {
    if (activeId) {
      try {
        localStorage.setItem(STORAGE.activeId, activeId);
      } catch {}
    }
  }, [activeId]);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE.theme, theme);
      localStorage.setItem(STORAGE.name, name);
      localStorage.setItem(STORAGE.persona, persona);
      localStorage.setItem(STORAGE.bg, bg);
      localStorage.setItem(STORAGE.screen, screen);
      localStorage.setItem(STORAGE.selectedModel, selectedModel);
    } catch {}
  }, [theme, name, persona, bg, screen, selectedModel]);

  useEffect(() => {
    if (!scrollRef.current || screen !== "chat") return;
    scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending, screen]);

  function updateActiveMessages(updater: (previous: Msg[]) => Msg[]) {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === activeId
          ? {
              ...conversation,
              messages: updater(conversation.messages),
              updatedAt: Date.now(),
            }
          : conversation,
      ),
    );
  }

  function updateMessageById(messageId: string, patch: Partial<Msg>) {
    updateActiveMessages((previous) =>
      previous.map((message) => (message.id === messageId ? { ...message, ...patch } : message)),
    );
  }

  function startNewConversation() {
    const created = newConversation();
    setConversations((previous) => [created, ...previous]);
    setActiveId(created.id);
    setScreen("chat");
    setMenuOpen(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function selectConversation(conversationId: string) {
    setActiveId(conversationId);
    setScreen("chat");
    setMenuOpen(false);
  }

  function deleteConversation(conversationId: string) {
    setConversations((previous) => {
      const next = previous.filter((conversation) => conversation.id !== conversationId);
      if (!next.length) {
        const fresh = newConversation();
        setActiveId(fresh.id);
        return [fresh];
      }
      if (conversationId === activeId) setActiveId(next[0].id);
      return next;
    });
  }

  function renameConversation(conversationId: string, title: string) {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, title: title.trim() || conversation.title, updatedAt: Date.now() }
          : conversation,
      ),
    );
  }

  function togglePinned(conversationId: string) {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, pinned: !conversation.pinned, updatedAt: Date.now() }
          : conversation,
      ),
    );
  }

  function clearCurrentConversation() {
    updateActiveMessages(() => []);
  }

  async function loginGoogle() {
    try {
      const result = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
      if (result.error) {
        toast.error(result.error.message ?? "Login Google gagal.");
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login Google gagal.");
    }
  }

  async function logout() {
    await supabase.auth.signOut();
    setAuthUser(null);
    toast.success("Berhasil keluar dari akun.");
  }

  function toggleTheme() {
    setTheme((previous) => (previous === "dark" ? "light" : "dark"));
  }

  async function handleImagePick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("File harus berupa gambar.");
      return;
    }
    try {
      const dataUrl = await compressImage(file, 1280, 0.85);
      setPendingImage({ dataUrl, name: file.name });
    } catch {
      toast.error("Gagal memproses gambar.");
    } finally {
      if (imageInputRef.current) imageInputRef.current.value = "";
    }
  }

  async function sendMessage(text: string, retryMessageId?: string) {
    const trimmed = text.trim();
    if (!trimmed && !pendingImage) return;
    if (sending) return;

    const imageDataUrl = pendingImage?.dataUrl;
    const content = trimmed || (imageDataUrl ? "(gambar)" : "");

    const userMessageId = retryMessageId ?? crypto.randomUUID();
    if (retryMessageId) {
      updateMessageById(retryMessageId, { status: "sending", failedPayload: undefined });
    } else {
      const nextMessage: Msg = {
        id: userMessageId,
        role: "user",
        content,
        at: Date.now(),
        status: "sending",
        imageDataUrl,
      };
      updateActiveMessages((previous) => [...previous, nextMessage]);
      if (activeConvo && (activeConvo.title === "Percakapan baru" || !activeConvo.title)) {
        renameConversation(activeConvo.id, deriveTitle(trimmed || "Gambar baru"));
      }
      setInput("");
      setPendingImage(null);
    }

    setSending(true);

    try {
      const currentMessages = (conversations.find((conversation) => conversation.id === activeId)?.messages ?? []).filter(
        (message) => message.status !== "failed",
      );
      const contextMessages = currentMessages
        .slice(-12)
        .map((message) => ({ role: message.role, content: message.content }));
      if (!contextMessages.length || contextMessages[contextMessages.length - 1]?.content !== content) {
        contextMessages.push({ role: "user", content });
      }

      const result = (await chat({
        data: {
          messages: contextMessages,
          characterName: name,
          systemPersona: persona,
          language: "id",
          userId,
          imageDataUrl,
          conversationId: activeId,
          clientNow: Date.now(),
          tz: (() => {
            try {
              return Intl.DateTimeFormat().resolvedOptions().timeZone;
            } catch {
              return undefined;
            }
          })(),
        },
      })) as { reply: string; bubbles?: string[] };

      const bubbles = result.bubbles?.length ? result.bubbles : [result.reply];
      updateMessageById(userMessageId, { status: "read" });

      for (const bubble of bubbles) {
        const assistantMessage: Msg = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: bubble,
          at: Date.now(),
          status: "sent",
        };
        updateActiveMessages((previous) => [...previous, assistantMessage]);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Gagal mengirim pesan.");
      updateMessageById(userMessageId, { status: "failed", failedPayload: trimmed });
    } finally {
      setSending(false);
    }
  }

  function retrySend(message: Msg) {
    sendMessage(message.failedPayload ?? message.content, message.id);
  }

  const filteredConversations = useMemo(() => {
    const keyword = historySearch.trim().toLowerCase();
    const sorted = [...conversations].sort((left, right) => {
      if (left.pinned && !right.pinned) return -1;
      if (!left.pinned && right.pinned) return 1;
      return right.updatedAt - left.updatedAt;
    });

    return sorted.filter((conversation) => {
      if (historyFilter === "gambar") {
        const hasImage = conversation.messages.some((message) => !!message.imageDataUrl);
        if (!hasImage) return false;
      }
      if (historyFilter === "pinned" && !conversation.pinned) return false;
      const haystack = `${conversation.title} ${conversation.messages
        .map((message) => message.content)
        .join(" ")}`.toLowerCase();
      if (keyword && !haystack.includes(keyword)) return false;
      return true;
    });
  }, [conversations, historyFilter, historySearch]);

  const modelStats = useMemo(() => {
    const installedCount = MODEL_CATALOG.filter((model) => model.status === "installed").length;
    return {
      totalChats: conversations.length,
      totalMessages: conversations.reduce((sum, conversation) => sum + conversation.messages.length, 0),
      imageChats: conversations.filter((conversation) =>
        conversation.messages.some((message) => !!message.imageDataUrl),
      ).length,
      installedCount,
    };
  }, [conversations]);

  const selectedModelInfo = MODEL_CATALOG.find((model) => model.id === selectedModel) ?? MODEL_CATALOG[0];

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-slate-950 text-white">
      <img
        src={bg}
        alt={`${name} background`}
        className="absolute inset-0 h-full w-full object-cover"
        draggable={false}
      />
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(4,10,26,0.32)_0%,rgba(4,10,26,0.58)_25%,rgba(4,10,26,0.72)_55%,rgba(4,10,26,0.9)_100%)]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(96,165,250,0.18),transparent_28%)]" />

      <aside
        className={`absolute inset-y-0 left-0 z-40 w-[86%] max-w-xs border-r border-white/10 bg-slate-950/92 p-4 backdrop-blur-xl transition-transform duration-300 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-sky-200/80">Furina</p>
            <h2 className="mt-1 text-xl font-semibold">Asisten AI Pribadimu</h2>
          </div>
          <Button variant="ghost" size="icon" className="rounded-full" onClick={() => setMenuOpen(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-2">
          {[
            { id: "chat", icon: Home, label: "Chat" },
            { id: "history", icon: History, label: "Riwayat" },
            { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
            { id: "models", icon: Cpu, label: "Kelola Model" },
            { id: "settings", icon: Settings, label: "Pengaturan" },
          ].map((item) => {
            const Icon = item.icon;
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setScreen(item.id as Screen);
                  setMenuOpen(false);
                }}
                className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition ${
                  active ? "bg-sky-500/20 text-white ring-1 ring-sky-300/40" : "text-slate-200/80 hover:bg-white/5"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span className="text-sm font-medium">{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-6 rounded-3xl border border-white/10 bg-white/5 p-4">
          <p className="text-xs uppercase tracking-[0.25em] text-sky-200/70">AI aktif</p>
          <p className="mt-2 text-lg font-semibold">{selectedModelInfo.name}</p>
          <p className="mt-1 text-sm text-slate-300/80">{selectedModelInfo.badge}</p>
          <Button className="mt-4 w-full rounded-2xl bg-sky-500 text-white hover:bg-sky-400" onClick={() => { setScreen("models"); setMenuOpen(false); }}>
            Kelola model
          </Button>
        </div>
      </aside>
      {menuOpen && (
        <button
          className="absolute inset-0 z-30 bg-black/50"
          onClick={() => setMenuOpen(false)}
          aria-label="Tutup menu"
        />
      )}

      <header className="absolute inset-x-0 top-0 z-20 px-4 pt-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 rounded-3xl border border-white/10 bg-slate-950/35 px-3 py-3 backdrop-blur-xl">
          <div className="flex min-w-0 items-center gap-3">
            <Button variant="ghost" size="icon" className="rounded-full text-white" onClick={() => setMenuOpen(true)}>
              <Menu className="h-4 w-4" />
            </Button>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.95)]" />
                <p className="truncate text-sm font-semibold">{name}</p>
              </div>
              <p className="truncate text-xs text-slate-300/75">
                {screen === "chat"
                  ? activeConvo?.title || "Percakapan baru"
                  : screen === "history"
                    ? "Riwayat percakapan"
                    : screen === "dashboard"
                      ? "Dashboard ringkas"
                      : screen === "models"
                        ? "Kelola model AI"
                        : "Pengaturan pribadi"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {screen === "chat" && (
              <Button
                variant="ghost"
                size="icon"
                className="rounded-full text-white"
                onClick={startNewConversation}
                title="Percakapan baru"
              >
                <Plus className="h-4 w-4" />
              </Button>
            )}
            <Button variant="ghost" size="icon" className="rounded-full text-white" onClick={toggleTheme}>
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </header>

      {screen === "chat" && (
        <main ref={scrollRef} className="absolute inset-x-0 top-0 bottom-0 z-10 overflow-y-auto px-4 pb-44 pt-24">
          <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-3">
            {messages.length === 0 && (
              <div className="mt-auto max-w-[88%] self-start rounded-[28px] border border-white/10 bg-slate-950/50 px-4 py-4 shadow-[0_20px_60px_rgba(0,0,0,0.25)] backdrop-blur-xl">
                <p className="text-sm leading-relaxed text-slate-50">
                  Halo… akhirnya kamu datang juga ✦ Aku {name}. Ceritakan apa saja.
                </p>
                <p className="mt-2 text-[11px] text-slate-300/70">baru saja</p>
              </div>
            )}

            <div className="mt-auto" />

            {messages.map((message) => {
              const isUser = message.role === "user";
              return (
                <div key={message.id} className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}>
                  <div
                    className={`w-fit max-w-[88%] rounded-[28px] px-4 py-3 text-sm shadow-[0_14px_40px_rgba(0,0,0,0.22)] backdrop-blur-xl ${
                      isUser
                        ? "bg-sky-500/70 text-white"
                        : "border border-white/10 bg-slate-950/52 text-slate-50"
                    }`}
                  >
                    {message.imageDataUrl && (
                      <button
                        type="button"
                        onClick={() => setLightboxUrl(message.imageDataUrl ?? null)}
                        className="mb-3 block overflow-hidden rounded-2xl"
                      >
                        <img src={message.imageDataUrl} alt="Lampiran" className="max-h-72 rounded-2xl object-cover" />
                      </button>
                    )}
                    <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
                  </div>
                  <div className="mt-1 flex items-center gap-2 px-2 text-[11px] text-slate-300/75">
                    <span>{fmtTime(message.at)}</span>
                    {message.status === "failed" && (
                      <button
                        onClick={() => retrySend(message)}
                        className="rounded-full bg-red-500/90 px-2 py-0.5 text-[10px] text-white"
                      >
                        Kirim ulang
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {sending && (
              <div className="max-w-[80%] self-start rounded-[28px] border border-white/10 bg-slate-950/50 px-4 py-3 backdrop-blur-xl">
                <div className="flex gap-1">
                  <span className="h-2 w-2 animate-bounce rounded-full bg-white/70 [animation-delay:-0.3s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-white/70 [animation-delay:-0.15s]" />
                  <span className="h-2 w-2 animate-bounce rounded-full bg-white/70" />
                </div>
              </div>
            )}
          </div>
        </main>
      )}

      {screen === "history" && (
        <main className="absolute inset-x-0 top-0 bottom-0 z-10 overflow-y-auto px-4 pb-28 pt-24">
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-3 backdrop-blur-xl">
              <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
                <Search className="h-4 w-4 text-slate-300/70" />
                <input
                  value={historySearch}
                  onChange={(event) => setHistorySearch(event.target.value)}
                  placeholder="Cari percakapan..."
                  className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-400"
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {[
                  { id: "all", label: "Semua" },
                  { id: "chat", label: "Chat" },
                  { id: "gambar", label: "Gambar" },
                  { id: "pinned", label: "Pinned" },
                ].map((item) => (
                  <button
                    key={item.id}
                    onClick={() => setHistoryFilter(item.id as HistoryFilter)}
                    className={`rounded-full px-3 py-1.5 text-xs transition ${
                      historyFilter === item.id
                        ? "bg-sky-500 text-white"
                        : "border border-white/10 bg-white/5 text-slate-200/75"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-3">
              {filteredConversations.map((conversation) => {
                const lastMessage = conversation.messages[conversation.messages.length - 1];
                return (
                  <div
                    key={conversation.id}
                    className={`rounded-3xl border p-4 backdrop-blur-xl transition ${
                      conversation.id === activeId
                        ? "border-sky-300/40 bg-sky-500/12"
                        : "border-white/10 bg-slate-950/45"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button className="min-w-0 flex-1 text-left" onClick={() => selectConversation(conversation.id)}>
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-semibold text-white">{conversation.title}</p>
                          {conversation.pinned && (
                            <span className="rounded-full bg-sky-500/20 px-2 py-0.5 text-[10px] text-sky-100">Pinned</span>
                          )}
                        </div>
                        <p className="mt-1 line-clamp-2 text-sm text-slate-300/80">
                          {lastMessage?.content || "Belum ada isi percakapan."}
                        </p>
                        <div className="mt-2 flex items-center gap-3 text-[11px] text-slate-300/65">
                          <span>{relTime(conversation.updatedAt, now)}</span>
                          <span>{conversation.messages.length} pesan</span>
                        </div>
                      </button>
                      <div className="flex shrink-0 items-center gap-2">
                        <Button variant="ghost" size="sm" className="rounded-full" onClick={() => togglePinned(conversation.id)}>
                          {conversation.pinned ? "Lepas" : "Pin"}
                        </Button>
                        <Button variant="ghost" size="sm" className="rounded-full text-red-200 hover:text-red-100" onClick={() => deleteConversation(conversation.id)}>
                          <Trash2 className="mr-1 h-4 w-4" /> Hapus
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
              {filteredConversations.length === 0 && (
                <div className="rounded-3xl border border-white/10 bg-slate-950/45 p-6 text-center text-sm text-slate-300/80 backdrop-blur-xl">
                  Tidak ada percakapan yang cocok.
                </div>
              )}
            </div>
          </div>
        </main>
      )}

      {screen === "dashboard" && (
        <main className="absolute inset-x-0 top-0 bottom-0 z-10 overflow-y-auto px-4 pb-28 pt-24">
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="rounded-[32px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Dashboard</p>
              <h2 className="mt-2 text-2xl font-semibold">Masuk langsung ke chat, kendali tetap di tanganmu.</h2>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300/80">
                Desain sesi ini dipusatkan pada pengalaman percakapan, dengan riwayat yang lebih jelas, dashboard ringkas, dan ruang terpisah untuk model offline.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <DashboardCard icon={Sparkles} title="Mode AI aktif" value={selectedModelInfo.name} subtitle={selectedModelInfo.badge} />
              <DashboardCard icon={History} title="Total percakapan" value={String(modelStats.totalChats)} subtitle="Riwayat tersimpan lokal" />
              <DashboardCard icon={ImageIcon} title="Chat bergambar" value={String(modelStats.imageChats)} subtitle="Gambar yang pernah dikirim" />
              <DashboardCard icon={Cpu} title="Model tersedia" value={String(modelStats.installedCount)} subtitle="Siap dipakai saat offline" />
            </div>

            <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-[32px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl">
                <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Aktivitas terbaru</p>
                <div className="mt-4 space-y-3">
                  {filteredConversations.slice(0, 4).map((conversation) => (
                    <button
                      key={conversation.id}
                      onClick={() => selectConversation(conversation.id)}
                      className="flex w-full items-start justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/8"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white">{conversation.title}</p>
                        <p className="mt-1 truncate text-xs text-slate-300/70">
                          {conversation.messages[conversation.messages.length - 1]?.content || "Belum ada isi."}
                        </p>
                      </div>
                      <span className="shrink-0 text-[11px] text-slate-300/60">{relTime(conversation.updatedAt, now)}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-[32px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl">
                <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Aksi cepat</p>
                <div className="mt-4 grid gap-3">
                  <QuickActionButton icon={Plus} title="Chat baru" description="Buka percakapan kosong dan langsung mengetik." onClick={startNewConversation} />
                  <QuickActionButton icon={Cpu} title="Kelola model" description="Lihat model offline yang akan dipakai di sesi berikutnya." onClick={() => setScreen("models")} />
                  <QuickActionButton icon={Settings} title="Buka pengaturan" description="Atur persona, tampilan, dan akun tanpa mengganggu chat." onClick={() => setScreen("settings")} />
                </div>
              </div>
            </div>
          </div>
        </main>
      )}

      {screen === "models" && (
        <main className="absolute inset-x-0 top-0 bottom-0 z-10 overflow-y-auto px-4 pb-28 pt-24">
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="rounded-[32px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Kelola model</p>
              <h2 className="mt-2 text-2xl font-semibold">Model offline ditempatkan terpisah dari layar chat.</h2>
              <p className="mt-2 text-sm leading-relaxed text-slate-300/80">
                Di sesi ini, area model dibuat rapi dan mudah dipahami. Integrasi runtime Android dan pembeda mode online/offline akan dipoles lanjut setelah UI stabil.
              </p>
            </div>

            <div className="grid gap-3">
              {MODEL_CATALOG.map((model) => {
                const isActive = selectedModel === model.id;
                return (
                  <div key={model.id} className={`rounded-[30px] border p-4 backdrop-blur-xl ${isActive ? "border-sky-300/40 bg-sky-500/12" : "border-white/10 bg-slate-950/45"}`}>
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-lg font-semibold text-white">{model.name}</h3>
                          <span className="rounded-full bg-white/8 px-2.5 py-1 text-[11px] text-sky-100">{model.badge}</span>
                          <span className="rounded-full bg-white/8 px-2.5 py-1 text-[11px] text-slate-200/80">{model.size}</span>
                        </div>
                        <p className="mt-2 text-sm leading-relaxed text-slate-300/80">{model.description}</p>
                        <p className="mt-3 text-xs text-sky-100/85">{model.recommended}</p>
                      </div>
                      <div className="flex shrink-0 flex-col gap-2 md:w-44">
                        <span className={`rounded-2xl px-3 py-2 text-center text-xs font-medium ${
                          model.status === "installed"
                            ? "bg-emerald-500/20 text-emerald-100"
                            : model.status === "available"
                              ? "bg-white/8 text-slate-100"
                              : "bg-amber-500/20 text-amber-100"
                        }`}>
                          {model.status === "installed"
                            ? "Sudah tersedia"
                            : model.status === "available"
                              ? "Tersedia"
                              : "Segera"}
                        </span>
                        <Button
                          onClick={() => setSelectedModel(model.id)}
                          className="rounded-2xl bg-sky-500 text-white hover:bg-sky-400"
                        >
                          {isActive ? "Sedang dipilih" : "Jadikan utama"}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </main>
      )}

      {screen === "settings" && (
        <main className="absolute inset-x-0 top-0 bottom-0 z-10 overflow-y-auto px-4 pb-28 pt-24">
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="rounded-[32px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl">
              <p className="text-xs uppercase tracking-[0.3em] text-sky-200/70">Pengaturan</p>
              <h2 className="mt-2 text-2xl font-semibold">Personalisasi karakter, akun, dan tampilan.</h2>
              <p className="mt-2 text-sm text-slate-300/80">
                Menu model offline tidak lagi muncul di layar chat. Semua pengaturan dipusatkan di area ini agar pengalaman ngobrol lebih bersih.
              </p>
            </div>

            <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
              <SettingCard title="Persona" icon={User}>
                <label className="text-sm text-slate-200/90">Nama karakter</label>
                <Input value={name} onChange={(event) => setName(event.target.value)} className="mt-2 border-white/10 bg-white/5 text-white" />
                <label className="mt-4 block text-sm text-slate-200/90">Kepribadian tambahan</label>
                <Textarea
                  rows={5}
                  value={persona}
                  onChange={(event) => setPersona(event.target.value)}
                  placeholder="Kosongkan untuk memakai persona Furina default."
                  className="mt-2 border-white/10 bg-white/5 text-white placeholder:text-slate-400"
                />
              </SettingCard>

              <SettingCard title="Tampilan" icon={Sparkles}>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200/90">
                  Background karakter dikunci memakai visual Furina resmi sesi ini agar konsisten dan menghindari bug visual.
                </div>
                <div className="mt-4 flex gap-3">
                  <Button className="rounded-2xl bg-sky-500 text-white hover:bg-sky-400" onClick={toggleTheme}>
                    {theme === "dark" ? "Pakai mode terang" : "Pakai mode gelap"}
                  </Button>
                  <Button variant="outline" className="rounded-2xl border-white/10 bg-white/5 text-white hover:bg-white/10" onClick={() => setScreen("chat")}>
                    Kembali ke chat
                  </Button>
                </div>
              </SettingCard>

              <SettingCard title="Akun & sinkronisasi" icon={Database}>
                {authReady ? (
                  authUser ? (
                    <div className="space-y-3">
                      <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                        <p className="text-sm font-medium text-white">Masuk sebagai</p>
                        <p className="mt-1 text-sm text-slate-300/80">{authUser.email ?? authUser.id}</p>
                      </div>
                      <Button className="w-full rounded-2xl bg-white/10 text-white hover:bg-white/15" onClick={logout}>
                        <LogOut className="mr-2 h-4 w-4" /> Keluar dari akun
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm leading-relaxed text-slate-300/80">
                        Login Google tetap disiapkan untuk backup chat dan preferensi. Di sesi UI ini, alurnya belum diubah secara teknis.
                      </p>
                      <Button className="w-full rounded-2xl bg-sky-500 text-white hover:bg-sky-400" onClick={loginGoogle}>
                        <LogIn className="mr-2 h-4 w-4" /> Masuk dengan Google
                      </Button>
                    </div>
                  )
                ) : (
                  <p className="text-sm text-slate-300/80">Menyiapkan status akun...</p>
                )}
              </SettingCard>

              <SettingCard title="Data chat" icon={HardDrive}>
                <div className="space-y-3 text-sm text-slate-300/80">
                  <p>Total pesan tersimpan: {modelStats.totalMessages}</p>
                  <p>Percakapan aktif: {activeConvo?.title || "Belum ada"}</p>
                </div>
                <Button variant="outline" className="mt-4 w-full rounded-2xl border-red-400/30 bg-red-500/10 text-red-100 hover:bg-red-500/20" onClick={clearCurrentConversation}>
                  <Trash2 className="mr-2 h-4 w-4" /> Bersihkan percakapan aktif
                </Button>
              </SettingCard>
            </div>
          </div>
        </main>
      )}

      {screen === "chat" && (
        <div className="absolute inset-x-0 bottom-20 z-20 px-4">
          <div className="mx-auto max-w-3xl rounded-[30px] border border-white/10 bg-slate-950/58 p-3 shadow-[0_-8px_40px_rgba(0,0,0,0.16)] backdrop-blur-xl">
            {pendingImage && (
              <div className="mb-3 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-2">
                <img src={pendingImage.dataUrl} alt="Preview" className="h-14 w-14 rounded-2xl object-cover" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">{pendingImage.name}</p>
                  <p className="text-xs text-slate-300/75">Akan dikirim bersama pesan.</p>
                </div>
                <Button variant="ghost" size="icon" className="rounded-full text-white" onClick={() => setPendingImage(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}
            <div className="flex items-end gap-2 rounded-[26px] border border-white/10 bg-white/5 px-2 py-2">
              <input ref={imageInputRef} type="file" accept="image/*" onChange={handleImagePick} className="hidden" />
              <Button variant="ghost" size="icon" className="rounded-full text-white" onClick={() => imageInputRef.current?.click()}>
                <ImageIcon className="h-4 w-4" />
              </Button>
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage(input);
                  }
                }}
                rows={1}
                placeholder="Ketik pesan..."
                className="min-h-[44px] max-h-32 flex-1 resize-none border-0 bg-transparent px-1 text-white shadow-none focus-visible:ring-0 placeholder:text-slate-400"
              />
              <Button className="rounded-full bg-sky-500 text-white hover:bg-sky-400" size="icon" onClick={() => sendMessage(input)} disabled={sending || (!input.trim() && !pendingImage)}>
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}

      <nav className="absolute inset-x-0 bottom-0 z-20 px-3 pb-3">
        <div className="mx-auto grid max-w-5xl grid-cols-5 rounded-[28px] border border-white/10 bg-slate-950/72 p-2 backdrop-blur-xl">
          {[
            { id: "chat", icon: Home, label: "Chat" },
            { id: "history", icon: History, label: "Riwayat" },
            { id: "dashboard", icon: LayoutDashboard, label: "Dashboard" },
            { id: "models", icon: Bot, label: "Model" },
            { id: "settings", icon: Settings, label: "Setting" },
          ].map((item) => {
            const Icon = item.icon;
            const active = screen === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setScreen(item.id as Screen)}
                className={`flex flex-col items-center justify-center rounded-[20px] px-1 py-2 text-[11px] transition ${
                  active ? "bg-sky-500/18 text-white" : "text-slate-300/75"
                }`}
              >
                <Icon className="mb-1 h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </div>
      </nav>

      <Dialog open={!!lightboxUrl} onOpenChange={(open) => !open && setLightboxUrl(null)}>
        <DialogContent className="max-w-[95vw] border-0 bg-black/90 p-2">
          {lightboxUrl && <img src={lightboxUrl} alt="Lampiran" className="max-h-[85vh] w-full rounded-2xl object-contain" />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DashboardCard({
  icon: Icon,
  title,
  value,
  subtitle,
}: {
  icon: typeof Sparkles;
  title: string;
  value: string;
  subtitle: string;
}) {
  return (
    <div className="rounded-[28px] border border-white/10 bg-slate-950/45 p-4 backdrop-blur-xl">
      <div className="flex items-center gap-2 text-sky-200/80">
        <Icon className="h-4 w-4" />
        <p className="text-xs uppercase tracking-[0.25em]">{title}</p>
      </div>
      <p className="mt-4 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-sm text-slate-300/75">{subtitle}</p>
    </div>
  );
}

function QuickActionButton({
  icon: Icon,
  title,
  description,
  onClick,
}: {
  icon: typeof Plus;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start gap-3 rounded-[24px] border border-white/10 bg-white/5 px-4 py-4 text-left transition hover:bg-white/8"
    >
      <div className="rounded-2xl bg-sky-500/18 p-2 text-sky-100">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="mt-1 text-sm text-slate-300/75">{description}</p>
      </div>
    </button>
  );
}

function SettingCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof User;
  children: ReactNode;
}) {
  return (
    <div className="rounded-[32px] border border-white/10 bg-slate-950/45 p-5 backdrop-blur-xl">
      <div className="mb-4 flex items-center gap-2 text-sky-200/80">
        <Icon className="h-4 w-4" />
        <p className="text-sm font-semibold text-white">{title}</p>
      </div>
      {children}
    </div>
  );
}

async function compressImage(file: File, maxDim: number, quality: number): Promise<string> {
  const dataUrl: string = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });

  const image: HTMLImageElement = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Gagal memuat gambar."));
    img.src = dataUrl;
  });

  const ratio = Math.min(1, maxDim / Math.max(image.width, image.height));
  const width = Math.round(image.width * ratio);
  const height = Math.round(image.height * ratio);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) return dataUrl;
  context.drawImage(image, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", quality);
}
