import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send, Settings, Trash2, Plus, Volume2, Image as ImageIcon, RotateCcw,
  Play, Pause, Square, Loader2, MessageSquarePlus, MessagesSquare, Check,
  CheckCheck, Pencil, AlertCircle, LogIn, LogOut, Upload, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetDescription } from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { toast } from "sonner";

import furinaDefault from "@/assets/furina.jpg";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable";
import {
  chatWithFurina,
  speakVoicevoxUrl,
  speakClone,
  listMemories,
  deleteMemory,
  addMemory,
  clearAllMemories,
  migrateGuestMemories,
} from "@/lib/furina.functions";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Furina — AI Companion" },
      { name: "description", content: "Personal AI companion dengan suara anime Jepang natural, memori RAG, dan kepribadian Furina yang bisa kamu personalisasi." },
      { property: "og:title", content: "Furina — AI Companion" },
      { property: "og:description", content: "Personal AI companion with voice, memory, and Furina personality." },
    ],
  }),
  component: FurinaApp,
});

type MsgStatus = "sending" | "sent" | "delivered" | "read" | "failed";
type Msg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  at: number;
  status?: MsgStatus;        // hanya untuk user message
  audioUrl?: string;          // cache URL TTS (voicevox)
  audioEmotion?: string;
  failedPayload?: string;     // teks asli kalau gagal kirim (untuk retry)
};
type TTSProvider = "voicevox" | "clone";
type Conversation = { id: string; title: string; messages: Msg[]; updatedAt: number };

const STORAGE = {
  convos: "furina:conversations",
  activeId: "furina:activeConvoId",
  bg: "furina:bg",
  name: "furina:name",
  persona: "furina:persona",
  lang: "furina:lang",
  speed: "furina:ttsSpeed",
  provider: "furina:ttsProvider",
  vvSpeaker: "furina:vvSpeaker",
  vvTranslate: "furina:vvTranslate",
  legacyMsgs: "furina:messages",
  guestId: "furina:guestId",
  cloneSample: "furina:cloneSample",       // base64
  cloneSampleMime: "furina:cloneSampleMime",
  cloneSampleName: "furina:cloneSampleName",
  migratedFlag: "furina:migratedTo",       // user_id yang sudah dimigrasi
};

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "Percakapan baru", messages: [], updatedAt: Date.now() };
}

function getOrCreateGuestId(): string {
  if (typeof window === "undefined") return "guest-ssr";
  let id = localStorage.getItem(STORAGE.guestId);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(STORAGE.guestId, id);
  }
  return id;
}

// VOICEVOX speakers — preset + rekomendasi Furina
const VV_SPEAKERS = [
  { id: 14, label: "★ Rekomendasi Furina — 冥鳴ひまり (anggun, dramatis)", recommended: true },
  { id: 20, label: "もち子さん (Mochiko) — hangat, lembut" },
  { id: 8,  label: "春日部つむぎ (Tsumugi) — cerah, energik" },
  { id: 2,  label: "四国めたん (Metan) — gadis muda manis" },
  { id: 3,  label: "ずんだもん (Zundamon) — imut, ceria" },
  { id: 10, label: "雨晴はう (Hau) — lembut, tenang" },
  { id: 9,  label: "波音リツ (Ritsu) — dewasa, kalem" },
  { id: 23, label: "WhiteCUL — manis, polos" },
];

function fmtTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function FurinaApp() {
  const chat = useServerFn(chatWithFurina);
  const ttsVV = useServerFn(speakVoicevoxUrl);
  const ttsClone = useServerFn(speakClone);
  const listMemFn = useServerFn(listMemories);
  const delMemFn = useServerFn(deleteMemory);
  const addMemFn = useServerFn(addMemory);
  const clearMemFn = useServerFn(clearAllMemories);
  const migrateMemFn = useServerFn(migrateGuestMemories);

  const [authUser, setAuthUser] = useState<{ id: string; email?: string } | null>(null);
  const [guestId] = useState<string>(() => getOrCreateGuestId());
  const userId = authUser?.id ?? guestId;

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [bg, setBg] = useState<string>(furinaDefault);
  const [name, setName] = useState("Furina");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState<"auto" | "ja" | "en" | "id">("auto");
  const [speed, setSpeed] = useState(1.0);
  const [provider, setProvider] = useState<TTSProvider>("voicevox");
  const [vvSpeaker, setVvSpeaker] = useState<number>(VV_SPEAKERS[0].id);
  const [vvTranslate, setVvTranslate] = useState(true);
  const [openSettings, setOpenSettings] = useState(false);
  const [openConvos, setOpenConvos] = useState(false);
  const [memories, setMemories] = useState<{ id: string; content: string }[]>([]);
  const [newMem, setNewMem] = useState("");
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [editingTitleId, setEditingTitleId] = useState<string | null>(null);
  const [editingTitleVal, setEditingTitleVal] = useState("");
  const [cloneSampleName, setCloneSampleName] = useState<string>("");
  const [hasCloneSample, setHasCloneSample] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const activeConvo = conversations.find((c) => c.id === activeId);
  const messages = activeConvo?.messages ?? [];

  // ===== Auth state =====
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.user) {
        setAuthUser({ id: data.session.user.id, email: data.session.user.email ?? undefined });
      }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      if (session?.user) {
        setAuthUser({ id: session.user.id, email: session.user.email ?? undefined });
      } else {
        setAuthUser(null);
      }
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  // ===== Migrasi memori guest → akun (sekali saja per akun) =====
  useEffect(() => {
    if (!authUser) return;
    const flagKey = STORAGE.migratedFlag;
    const migratedTo = localStorage.getItem(flagKey);
    if (migratedTo === authUser.id) return;
    migrateMemFn({ data: { fromGuestId: guestId, toUserId: authUser.id } })
      .then(() => {
        localStorage.setItem(flagKey, authUser.id);
        toast.success("Data guest berhasil dipindahkan ke akun ini.");
      })
      .catch((e) => console.warn("migrate failed:", e));
  }, [authUser, guestId, migrateMemFn]);

  // ===== Load persisted state =====
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const rawConvos = localStorage.getItem(STORAGE.convos);
      let loaded: Conversation[] = [];
      if (rawConvos) {
        loaded = JSON.parse(rawConvos);
      } else {
        const legacy = localStorage.getItem(STORAGE.legacyMsgs);
        if (legacy) {
          const msgs: Msg[] = JSON.parse(legacy);
          if (msgs.length) {
            loaded = [{ id: crypto.randomUUID(), title: "Percakapan lama", messages: msgs, updatedAt: Date.now() }];
          }
          localStorage.removeItem(STORAGE.legacyMsgs);
        }
      }
      if (!loaded.length) loaded = [newConversation()];
      setConversations(loaded);
      const savedActive = localStorage.getItem(STORAGE.activeId);
      setActiveId(savedActive && loaded.some((c) => c.id === savedActive) ? savedActive : loaded[0].id);

      const b = localStorage.getItem(STORAGE.bg); if (b) setBg(b);
      const n = localStorage.getItem(STORAGE.name); if (n) setName(n);
      const p = localStorage.getItem(STORAGE.persona); if (p) setPersona(p);
      const l = localStorage.getItem(STORAGE.lang); if (l) setLanguage(l as typeof language);
      const sp = localStorage.getItem(STORAGE.speed);
      if (sp) setSpeed(Math.min(1.5, Math.max(0.7, parseFloat(sp) || 1.0)));
      const pr = localStorage.getItem(STORAGE.provider);
      if (pr === "voicevox" || pr === "clone") setProvider(pr);
      const vs = localStorage.getItem(STORAGE.vvSpeaker);
      if (vs) setVvSpeaker(parseInt(vs, 10) || VV_SPEAKERS[0].id);
      const vt = localStorage.getItem(STORAGE.vvTranslate);
      if (vt) setVvTranslate(vt === "1");

      const cs = localStorage.getItem(STORAGE.cloneSample);
      const csn = localStorage.getItem(STORAGE.cloneSampleName);
      setHasCloneSample(!!cs);
      if (csn) setCloneSampleName(csn);
    } catch {}
  }, []);

  useEffect(() => {
    if (!conversations.length) return;
    try { localStorage.setItem(STORAGE.convos, JSON.stringify(conversations)); } catch {}
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [conversations, activeId]);

  useEffect(() => {
    if (activeId) try { localStorage.setItem(STORAGE.activeId, activeId); } catch {}
  }, [activeId]);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const updateActiveMessages = useCallback((updater: (prev: Msg[]) => Msg[]) => {
    setConversations((convos) =>
      convos.map((c) =>
        c.id === activeId
          ? { ...c, messages: updater(c.messages), updatedAt: Date.now() }
          : c,
      ),
    );
  }, [activeId]);

  function updateMessageById(msgId: string, patch: Partial<Msg>) {
    updateActiveMessages((prev) => prev.map((m) => (m.id === msgId ? { ...m, ...patch } : m)));
  }

  function startNewConversation() {
    stopTTS();
    const c = newConversation();
    setConversations((prev) => [c, ...prev]);
    setActiveId(c.id);
    setOpenConvos(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function selectConversation(id: string) {
    stopTTS();
    setActiveId(id);
    setOpenConvos(false);
  }

  function deleteConversation(id: string) {
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id);
      const next = filtered.length ? filtered : [newConversation()];
      if (id === activeId) setActiveId(next[0].id);
      return next;
    });
  }

  function renameConversation(id: string, title: string) {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title: title.trim() || c.title } : c)));
  }

  // ===== Kirim pesan =====
  async function sendMessage(text: string, retryMsgId?: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    let userMsgId: string;
    if (retryMsgId) {
      userMsgId = retryMsgId;
      updateMessageById(retryMsgId, { status: "sending", failedPayload: undefined });
    } else {
      userMsgId = crypto.randomUUID();
      const userMsg: Msg = {
        id: userMsgId, role: "user", content: trimmed,
        at: Date.now(), status: "sending",
      };
      updateActiveMessages((prev) => [...prev, userMsg]);
      if (activeConvo && (activeConvo.title === "Percakapan baru" || !activeConvo.title)) {
        const t = trimmed.slice(0, 40).replace(/\s+/g, " ").trim();
        renameConversation(activeConvo.id, t || "Percakapan baru");
      }
      setInput("");
    }

    setSending(true);
    // Animasi cepat: sending → sent → delivered
    setTimeout(() => updateMessageById(userMsgId, { status: "sent" }), 120);
    setTimeout(() => updateMessageById(userMsgId, { status: "delivered" }), 380);

    try {
      const currentMsgs = (conversations.find((c) => c.id === activeId)?.messages ?? []);
      const ctxMsgs = currentMsgs
        .filter((m) => m.status !== "failed")
        .slice(-12)
        .map((m) => ({ role: m.role, content: m.content }));
      // Pastikan pesan user terakhir ada (kalau retry, sudah ada di state)
      if (!ctxMsgs.length || ctxMsgs[ctxMsgs.length - 1]?.content !== trimmed) {
        ctxMsgs.push({ role: "user", content: trimmed });
      }

      const { reply } = await chat({
        data: {
          messages: ctxMsgs,
          characterName: name,
          systemPersona: persona,
          language,
          userId,
        },
      });

      // Tandai user msg "read" (centang biru) + animasi
      updateMessageById(userMsgId, { status: "read" });

      const aiMsg: Msg = {
        id: crypto.randomUUID(), role: "assistant", content: reply, at: Date.now(),
      };
      updateActiveMessages((prev) => [...prev, aiMsg]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Gagal kirim";
      toast.error(msg);
      updateMessageById(userMsgId, { status: "failed", failedPayload: trimmed });
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function retrySend(m: Msg) {
    const text = m.failedPayload ?? m.content;
    sendMessage(text, m.id);
  }

  // ===== TTS =====
  function stopTTS() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPlayingId(null);
    setPaused(false);
  }
  function pauseTTS() {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
      setPaused(true);
    }
  }
  async function resumeTTS() {
    if (audioRef.current && audioRef.current.paused) {
      await audioRef.current.play();
      setPaused(false);
    }
  }

  async function playTTS(msg: Msg) {
    try {
      const clean = msg.content.replace(/\*[^*]+\*/g, "").trim();
      if (!clean) return;
      stopTTS();

      let src = msg.audioUrl;
      if (!src) {
        setLoadingId(msg.id);
        try {
          if (provider === "voicevox") {
            const { mp3Url, emotion } = await ttsVV({
              data: {
                text: clean.slice(0, 1200),
                speaker: vvSpeaker,
                speed,
                translateToJa: vvTranslate,
              },
            });
            src = mp3Url;
            updateMessageById(msg.id, { audioUrl: mp3Url, audioEmotion: emotion });
          } else {
            // clone
            const sampleB64 = localStorage.getItem(STORAGE.cloneSample);
            const sampleMime = localStorage.getItem(STORAGE.cloneSampleMime) ?? "audio/wav";
            if (!sampleB64) {
              throw new Error("Belum ada sampel suara. Upload sampel di Pengaturan dulu.");
            }
            const { audio, mime } = await ttsClone({
              data: {
                text: clean.slice(0, 600),
                sampleBase64: sampleB64,
                sampleMime,
                language: "ja",
                translateToJa: vvTranslate,
              },
            });
            src = `data:${mime};base64,${audio}`;
            // Cache di message juga (bisa replay tanpa regenerate)
            updateMessageById(msg.id, { audioUrl: src });
          }
        } finally {
          setLoadingId(null);
        }
      }

      const a = new Audio(src);
      audioRef.current = a;
      setPlayingId(msg.id);
      setPaused(false);
      a.onended = () => { setPlayingId(null); setPaused(false); audioRef.current = null; };
      a.onerror = () => {
        setPlayingId(null); setPaused(false); audioRef.current = null;
        toast.error("Audio gagal dimuat. URL mungkin sudah kedaluwarsa — coba putar ulang.");
        // Bersihkan cache supaya re-generate
        updateMessageById(msg.id, { audioUrl: undefined });
      };
      await a.play();
    } catch (e) {
      setLoadingId(null);
      setPlayingId(null);
      setPaused(false);
      toast.error(e instanceof Error ? e.message : "Voice failed");
    }
  }

  // ===== Background upload =====
  function handleBgUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result);
      setBg(url);
      try { localStorage.setItem(STORAGE.bg, url); } catch {
        toast.error("Gambar terlalu besar untuk disimpan.");
      }
    };
    reader.readAsDataURL(file);
  }

  // ===== Memories =====
  async function refreshMemories() {
    try {
      const { memories } = await listMemFn({ data: { userId } });
      setMemories(memories);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Gagal memuat memori");
    }
  }

  // ===== Voice clone sample upload =====
  function handleSampleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Sampel terlalu besar. Maks 5MB (idealnya 10–30 detik audio jernih).");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const data = String(reader.result);
      const idx = data.indexOf(",");
      const b64 = idx >= 0 ? data.slice(idx + 1) : data;
      try {
        localStorage.setItem(STORAGE.cloneSample, b64);
        localStorage.setItem(STORAGE.cloneSampleMime, file.type || "audio/wav");
        localStorage.setItem(STORAGE.cloneSampleName, file.name);
        setCloneSampleName(file.name);
        setHasCloneSample(true);
        toast.success(`Sampel "${file.name}" tersimpan.`);
      } catch {
        toast.error("Gagal menyimpan sampel (mungkin terlalu besar).");
      }
    };
    reader.readAsDataURL(file);
  }
  function clearSample() {
    localStorage.removeItem(STORAGE.cloneSample);
    localStorage.removeItem(STORAGE.cloneSampleMime);
    localStorage.removeItem(STORAGE.cloneSampleName);
    setHasCloneSample(false);
    setCloneSampleName("");
  }

  // ===== Auth actions =====
  async function loginGoogle() {
    try {
      const result = await lovable.auth.signInWithOAuth("google", {
        redirect_uri: window.location.origin,
      });
      if (result.error) toast.error("Login gagal: " + (result.error.message ?? "unknown"));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Login gagal");
    }
  }
  async function logout() {
    await supabase.auth.signOut();
    toast.success("Sudah logout. Kembali ke mode guest.");
  }

  function savePref(key: string, value: string) {
    try { localStorage.setItem(key, value); } catch {}
  }

  function clearChat() {
    updateActiveMessages(() => []);
  }

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-black">
      <img src={bg} alt={`${name} background`} className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/30 via-transparent to-black/60" />

      {/* Top bar */}
      <header className="absolute left-0 right-0 top-0 z-20 flex items-center justify-between p-4">
        <div className="flex items-center gap-2">
          <div className="rounded-full bg-black/30 px-4 py-1.5 text-sm font-medium text-white backdrop-blur-md max-w-[55vw] truncate">
            {name}
            {activeConvo && <span className="ml-2 text-xs text-white/60 truncate">· {activeConvo.title}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="icon" variant="ghost" onClick={startNewConversation}
            className="rounded-full bg-black/30 text-white backdrop-blur-md hover:bg-black/50"
            aria-label="Percakapan baru" title="Percakapan baru">
            <MessageSquarePlus className="h-5 w-5" />
          </Button>

          <Sheet open={openConvos} onOpenChange={setOpenConvos}>
            <SheetTrigger asChild>
              <Button size="icon" variant="ghost" className="rounded-full bg-black/30 text-white backdrop-blur-md hover:bg-black/50" aria-label="Riwayat percakapan">
                <MessagesSquare className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-full overflow-y-auto sm:max-w-sm">
              <SheetHeader>
                <SheetTitle>Riwayat Percakapan</SheetTitle>
                <SheetDescription>Tersimpan di browser{authUser ? " & akun kamu" : " (mode guest)"}.</SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-2">
                <Button onClick={startNewConversation} className="w-full">
                  <Plus className="mr-2 h-4 w-4" /> Percakapan baru
                </Button>
                <div className="mt-3 space-y-1">
                  {[...conversations].sort((a, b) => b.updatedAt - a.updatedAt).map((c) => {
                    const isActive = c.id === activeId;
                    const preview = c.messages[c.messages.length - 1]?.content?.slice(0, 60) ?? "Belum ada pesan";
                    return (
                      <div key={c.id}
                        className={`group rounded-lg border p-2 transition ${isActive ? "border-primary bg-accent" : "hover:bg-muted"}`}>
                        {editingTitleId === c.id ? (
                          <div className="flex items-center gap-1">
                            <Input autoFocus value={editingTitleVal}
                              onChange={(e) => setEditingTitleVal(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { renameConversation(c.id, editingTitleVal); setEditingTitleId(null); }
                                if (e.key === "Escape") setEditingTitleId(null);
                              }}
                              className="h-7 text-sm" />
                            <Button size="icon" variant="ghost" className="h-7 w-7"
                              onClick={() => { renameConversation(c.id, editingTitleVal); setEditingTitleId(null); }}>
                              <Check className="h-4 w-4" />
                            </Button>
                          </div>
                        ) : (
                          <button onClick={() => selectConversation(c.id)} className="flex w-full flex-col text-left">
                            <span className="truncate text-sm font-medium">{c.title}</span>
                            <span className="truncate text-xs text-muted-foreground">{preview}</span>
                            <span className="text-[10px] text-muted-foreground">{new Date(c.updatedAt).toLocaleString()}</span>
                          </button>
                        )}
                        {editingTitleId !== c.id && (
                          <div className="mt-1 flex items-center gap-1 opacity-0 transition group-hover:opacity-100">
                            <Button size="icon" variant="ghost" className="h-6 w-6"
                              onClick={() => { setEditingTitleId(c.id); setEditingTitleVal(c.title); }}>
                              <Pencil className="h-3 w-3" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-6 w-6 text-destructive"
                              onClick={() => { if (confirm("Hapus percakapan ini?")) deleteConversation(c.id); }}>
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </SheetContent>
          </Sheet>

          <Sheet open={openSettings} onOpenChange={(o) => { setOpenSettings(o); if (o) refreshMemories(); }}>
            <SheetTrigger asChild>
              <Button size="icon" variant="ghost" className="rounded-full bg-black/30 text-white backdrop-blur-md hover:bg-black/50">
                <Settings className="h-5 w-5" />
              </Button>
            </SheetTrigger>

            <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
              <SheetHeader>
                <SheetTitle>Pengaturan</SheetTitle>
                <SheetDescription>Personalisasi karakter, suara, akun, dan memori.</SheetDescription>
              </SheetHeader>

              <div className="mt-6 space-y-6">
                {/* Akun */}
                <section className="rounded-lg border bg-muted/30 p-3 space-y-2">
                  <Label className="text-xs font-semibold uppercase tracking-wider">Akun</Label>
                  {authUser ? (
                    <div className="space-y-2">
                      <p className="text-sm">Login sebagai <span className="font-medium">{authUser.email ?? authUser.id}</span></p>
                      <Button variant="outline" size="sm" className="w-full" onClick={logout}>
                        <LogOut className="mr-2 h-4 w-4" /> Logout
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">
                        Mode guest. Login opsional — saat login pertama, data guest (memori) otomatis dipindahkan ke akunmu. Ganti akun = mulai dari awal.
                      </p>
                      <Button size="sm" className="w-full" onClick={loginGoogle}>
                        <LogIn className="mr-2 h-4 w-4" /> Masuk dengan Google
                      </Button>
                    </div>
                  )}
                </section>

                <section className="space-y-2">
                  <Label>Nama karakter</Label>
                  <Input value={name} onChange={(e) => { setName(e.target.value); savePref(STORAGE.name, e.target.value); }} />
                </section>

                <section className="space-y-2">
                  <Label>Kepribadian / system prompt (opsional)</Label>
                  <Textarea rows={5} placeholder="Kosongkan untuk kepribadian Furina default…"
                    value={persona}
                    onChange={(e) => { setPersona(e.target.value); savePref(STORAGE.persona, e.target.value); }} />
                </section>

                {/* TTS */}
                <section className="space-y-3">
                  <Label>Mesin suara (TTS)</Label>
                  <Select value={provider} onValueChange={(v) => { setProvider(v as TTSProvider); savePref(STORAGE.provider, v); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="voicevox">VOICEVOX — anime Jepang (gratis, stabil)</SelectItem>
                      <SelectItem value="clone">Voice Clone — suara asli karakter (HF, beta)</SelectItem>
                    </SelectContent>
                  </Select>

                  {provider === "voicevox" ? (
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Karakter VOICEVOX</Label>
                      <Select value={String(vvSpeaker)}
                        onValueChange={(v) => { setVvSpeaker(parseInt(v, 10)); savePref(STORAGE.vvSpeaker, v); }}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {VV_SPEAKERS.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.label}</SelectItem>)}
                        </SelectContent>
                      </Select>
                      <div className="flex items-center justify-between pt-1">
                        <Label className="text-xs">Auto-terjemah ke Jepang</Label>
                        <Switch checked={vvTranslate}
                          onCheckedChange={(c) => { setVvTranslate(c); savePref(STORAGE.vvTranslate, c ? "1" : "0"); }} />
                      </div>
                      <p className="text-[11px] leading-relaxed text-muted-foreground">
                        Teks balasan tetap bahasamu, suara otomatis dibacakan dalam Jepang ala anime. Gratis lewat VOICEVOX.
                      </p>
                    </div>
                  ) : (
                    <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                      <Label className="text-xs font-semibold flex items-center gap-1">
                        <Sparkles className="h-3 w-3" /> Sampel suara karakter (untuk clone)
                      </Label>
                      <p className="text-[10px] leading-relaxed text-muted-foreground">
                        Upload 1 file audio (mp3/wav, 10–30 detik, suara jernih satu orang, tanpa musik). Untuk pakai "suara asli Furina", upload sampel dialog JP Furina yang kamu miliki sendiri. Hasil clone via Hugging Face XTTS-v2 (gratis, kadang antri).
                      </p>
                      <input type="file" accept="audio/*" onChange={handleSampleUpload} className="block w-full text-xs" />
                      {hasCloneSample && (
                        <div className="flex items-center justify-between rounded bg-background/60 px-2 py-1 text-xs">
                          <span className="truncate">✓ {cloneSampleName || "Sampel tersimpan"}</span>
                          <button onClick={clearSample} className="text-muted-foreground hover:text-destructive">
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      )}
                      <div className="flex items-center justify-between pt-1">
                        <Label className="text-xs">Auto-terjemah ke Jepang</Label>
                        <Switch checked={vvTranslate}
                          onCheckedChange={(c) => { setVvTranslate(c); savePref(STORAGE.vvTranslate, c ? "1" : "0"); }} />
                      </div>
                      <p className="text-[10px] leading-relaxed text-amber-600 dark:text-amber-400">
                        ⚠️ HF Inference gratis sering antri/timeout. Kalau gagal, model akan kasih pesan untuk coba lagi atau pakai VOICEVOX.
                      </p>
                    </div>
                  )}

                  <p className="pt-2 text-[11px] leading-relaxed text-muted-foreground">
                    <Volume2 className="mr-1 inline h-3 w-3" />
                    Suara hanya berbunyi saat kamu menekan tombol ▶ di balon pesan.
                  </p>

                  <div className="pt-2 space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Kecepatan bicara</Label>
                      <span className="text-xs text-muted-foreground tabular-nums">{speed.toFixed(2)}x</span>
                    </div>
                    <Slider min={0.7} max={1.5} step={0.05} value={[speed]}
                      onValueChange={(v) => { const s = v[0] ?? 1; setSpeed(s); savePref(STORAGE.speed, String(s)); }} />
                  </div>
                </section>

                <section className="space-y-2">
                  <Label>Bahasa balasan</Label>
                  <Select value={language} onValueChange={(v) => { setLanguage(v as typeof language); savePref(STORAGE.lang, v); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto (mengikuti kamu)</SelectItem>
                      <SelectItem value="ja">日本語</SelectItem>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="id">Indonesia</SelectItem>
                    </SelectContent>
                  </Select>
                </section>

                <Separator />

                <section className="space-y-2">
                  <Label className="flex items-center gap-2"><ImageIcon className="h-4 w-4" /> Background karakter</Label>
                  <input type="file" accept="image/*" onChange={handleBgUpload} className="block w-full text-sm" />
                  <Button variant="outline" size="sm" onClick={() => { setBg(furinaDefault); localStorage.removeItem(STORAGE.bg); }}>
                    <RotateCcw className="mr-2 h-4 w-4" /> Kembalikan Furina default
                  </Button>
                </section>

                <Separator />

                <section className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Memori (RAG, lintas-percakapan)</Label>
                    <Button variant="ghost" size="sm" onClick={async () => {
                      if (!confirm("Hapus semua memori?")) return;
                      await clearMemFn({ data: { userId } });
                      refreshMemories();
                      toast.success("Memori dibersihkan");
                    }}>Hapus semua</Button>
                  </div>
                  <div className="flex gap-2">
                    <Input placeholder="Tambah fakta tentang dirimu…" value={newMem} onChange={(e) => setNewMem(e.target.value)} />
                    <Button size="icon" onClick={async () => {
                      if (newMem.trim().length < 3) return;
                      try {
                        await addMemFn({ data: { content: newMem.trim(), userId } });
                        setNewMem("");
                        refreshMemories();
                      } catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
                    }}><Plus className="h-4 w-4" /></Button>
                  </div>
                  <div className="max-h-64 space-y-1 overflow-y-auto rounded-md border p-2 text-sm">
                    {memories.length === 0 && <p className="text-muted-foreground">Belum ada memori. Karakter akan otomatis mengingat fakta dari obrolan.</p>}
                    {memories.map((m) => (
                      <div key={m.id} className="flex items-start gap-2 rounded p-1 hover:bg-muted">
                        <span className="flex-1">{m.content}</span>
                        <button onClick={async () => { await delMemFn({ data: { id: m.id, userId } }); refreshMemories(); }} className="text-muted-foreground hover:text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                </section>

                <Separator />

                <Button variant="outline" className="w-full" onClick={clearChat}>
                  <Trash2 className="mr-2 h-4 w-4" /> Bersihkan percakapan ini
                </Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      {/* Chat messages */}
      <main ref={scrollRef} className="absolute inset-0 z-10 flex flex-col gap-3 overflow-y-auto px-4 pt-20 pb-32">
        {messages.length === 0 && (
          <div className="mt-auto mb-4 max-w-[85%] self-start">
            <div className="rounded-2xl bg-white/95 px-4 py-3 text-sm text-foreground shadow-lg backdrop-blur">
              Halo… ara, akhirnya kamu datang juga~ ✦ Aku {name}. Ceritakan apa saja padaku.
            </div>
            <div className="mt-1 px-1 text-[10px] text-white/70">{fmtTime(Date.now())}</div>
          </div>
        )}
        <div className="mt-auto" />
        {messages.map((m) => {
          const isUser = m.role === "user";
          const isPlaying = playingId === m.id;
          const isLoading = loadingId === m.id;
          return (
            <div key={m.id} className={isUser ? "flex max-w-[85%] self-end flex-col items-end" : "flex max-w-[85%] self-start flex-col items-start"}>
              <div className={
                isUser
                  ? "rounded-2xl bg-[oklch(0.55_0.18_265)] px-4 py-2.5 text-sm text-white shadow-lg"
                  : "rounded-2xl bg-white/95 px-4 py-2.5 text-sm text-foreground shadow-lg backdrop-blur"
              }>
                {m.content}
              </div>

              {/* Footer: timestamp + status (user) / TTS controls (AI) */}
              <div className="mt-1 flex items-center gap-1.5 px-1">
                <span className="text-[10px] text-white/70 tabular-nums">{fmtTime(m.at)}</span>

                {isUser && <MsgStatusIcon status={m.status} />}

                {isUser && m.status === "failed" && (
                  <button onClick={() => retrySend(m)}
                    className="ml-1 inline-flex items-center gap-1 rounded-full bg-red-500/90 px-2 py-0.5 text-[10px] font-medium text-white hover:bg-red-500">
                    <RotateCcw className="h-2.5 w-2.5" /> Kirim ulang
                  </button>
                )}

                {!isUser && (
                  <div className="flex items-center gap-1">
                    {isLoading && (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-black/50 px-2.5 py-1 text-[11px] text-white backdrop-blur-md">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Menyiapkan suara…
                      </span>
                    )}
                    {!isLoading && !isPlaying && (
                      <button onClick={() => playTTS(m)}
                        className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md transition hover:bg-black/60"
                        aria-label="Putar">
                        <Play className="h-3 w-3" />
                      </button>
                    )}
                    {!isLoading && isPlaying && !paused && (
                      <button onClick={pauseTTS}
                        className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md hover:bg-black/60" aria-label="Jeda">
                        <Pause className="h-3 w-3" />
                      </button>
                    )}
                    {!isLoading && isPlaying && paused && (
                      <button onClick={resumeTTS}
                        className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md hover:bg-black/60" aria-label="Lanjutkan">
                        <Play className="h-3 w-3" />
                      </button>
                    )}
                    {!isLoading && isPlaying && (
                      <button onClick={stopTTS}
                        className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md hover:bg-black/60" aria-label="Berhenti">
                        <Square className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {sending && (
          <div className="max-w-[85%] self-start rounded-2xl bg-white/90 px-4 py-2.5 text-sm text-muted-foreground shadow-lg backdrop-blur">
            <span className="inline-flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.3s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.15s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50" />
            </span>
          </div>
        )}
      </main>

      {/* Composer */}
      <div className="absolute bottom-0 left-0 right-0 z-20 border-t border-white/10 bg-background/85 p-3 backdrop-blur-md">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <Textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
            placeholder="Ketik pesan Anda di sini..." rows={1}
            className="max-h-32 min-h-[44px] flex-1 resize-none border-0 bg-transparent focus-visible:ring-0" />
          <Button onClick={() => sendMessage(input)} disabled={sending || !input.trim()} size="icon" className="h-11 w-11 rounded-full">
            <Send className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

// =================== Status icon (WhatsApp-style) ===================
function MsgStatusIcon({ status }: { status?: MsgStatus }) {
  if (!status) return null;
  if (status === "sending") {
    return <span className="text-white/60"><Loader2 className="h-3 w-3 animate-spin" /></span>;
  }
  if (status === "sent") {
    return <Check className="h-3 w-3 text-white/70" />;
  }
  if (status === "delivered") {
    return <CheckCheck className="h-3 w-3 text-white/70" />;
  }
  if (status === "read") {
    return (
      <span className="inline-flex animate-[pop_0.4s_ease-out]">
        <CheckCheck className="h-3 w-3 text-sky-400" />
      </span>
    );
  }
  if (status === "failed") {
    return <AlertCircle className="h-3 w-3 text-red-400" />;
  }
  return null;
}
