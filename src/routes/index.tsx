import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send, Settings, Trash2, Plus, Volume2, Image as ImageIcon, RotateCcw,
  Play, Pause, Square, Loader2, MessageSquarePlus, MessagesSquare, Check,
  CheckCheck, Pencil, AlertCircle, LogIn, LogOut, Sparkles, Sun, Moon, X,
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
      { name: "description", content: "Personal AI companion dengan suara Jepang natural, memori RAG, dan kepribadian Furina." },
      { property: "og:title", content: "Furina — AI Companion" },
      { property: "og:description", content: "Personal AI companion with voice, memory, vision, and Furina personality." },
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
  status?: MsgStatus;
  audioUrl?: string;
  audioEmotion?: string;
  failedPayload?: string;
  imageDataUrl?: string;
};
type TTSProvider = "voicevox" | "clone";
type Conversation = { id: string; title: string; messages: Msg[]; updatedAt: number };
type ThemeMode = "dark" | "light";

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
  cloneSample: "furina:cloneSample",
  cloneSampleMime: "furina:cloneSampleMime",
  cloneSampleName: "furina:cloneSampleName",
  migratedFlag: "furina:migratedTo",
  theme: "furina:theme",
  preGen: "furina:preGenAudio",
};

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "Percakapan baru", messages: [], updatedAt: Date.now() };
}
function getOrCreateGuestId(): string {
  if (typeof window === "undefined") return "guest-ssr";
  let id = localStorage.getItem(STORAGE.guestId);
  if (!id) { id = crypto.randomUUID(); localStorage.setItem(STORAGE.guestId, id); }
  return id;
}

// VOICEVOX — speakers + style IDs yang sudah diverifikasi via tts.quest (VOICEVOX core).
// Sumber: VOICEVOX official speaker list. Style id = "speaker" param.
const VV_SPEAKERS = [
  { id: 14, label: "★ Rekomendasi Furina — 冥鳴ひまり (ノーマル, anggun)" },
  { id: 8,  label: "春日部つむぎ — ノーマル (cerah, energik)" },
  { id: 20, label: "もち子さん — ノーマル (hangat lembut)" },
  { id: 2,  label: "四国めたん — ノーマル (manis muda)" },
  { id: 0,  label: "四国めたん — あまあま (manja)" },
  { id: 6,  label: "四国めたん — ツンツン (tsundere)" },
  { id: 9,  label: "波音リツ — ノーマル (dewasa kalem)" },
  { id: 10, label: "雨晴はう — ノーマル (lembut tenang)" },
  { id: 3,  label: "ずんだもん — ノーマル (imut ceria)" },
  { id: 7,  label: "ずんだもん — ツンツン" },
  { id: 23, label: "WhiteCUL — ノーマル (manis polos)" },
  { id: 27, label: "九州そら — ノーマル (anggun dewasa)" },
  { id: 29, label: "九州そら — あまあま" },
  { id: 42, label: "ろさ — ノーマル" },
  { id: 43, label: "ろさ — クール" },
  { id: 52, label: "雀松朱司 — ノーマル" },
];

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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

  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<{ dataUrl: string; name: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [bg, setBg] = useState<string>(furinaDefault);
  const [name, setName] = useState("Furina");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState<"auto" | "ja" | "en" | "id">("auto");
  const [speed, setSpeed] = useState(1.0);
  const [provider, setProvider] = useState<TTSProvider>("voicevox");
  const [vvSpeaker, setVvSpeaker] = useState<number>(VV_SPEAKERS[0].id);
  const [vvTranslate, setVvTranslate] = useState(true);
  const [preGenAudio, setPreGenAudio] = useState(true);
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
  const imageInputRef = useRef<HTMLInputElement | null>(null);

  const activeConvo = conversations.find((c) => c.id === activeId);
  const messages = activeConvo?.messages ?? [];

  // ===== Apply theme to <html> =====
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // ===== Auth =====
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.user) setAuthUser({ id: data.session.user.id, email: data.session.user.email ?? undefined });
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      setAuthUser(session?.user ? { id: session.user.id, email: session.user.email ?? undefined } : null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!authUser) return;
    const migratedTo = localStorage.getItem(STORAGE.migratedFlag);
    if (migratedTo === authUser.id) return;
    migrateMemFn({ data: { fromGuestId: guestId, toUserId: authUser.id } })
      .then(() => {
        localStorage.setItem(STORAGE.migratedFlag, authUser.id);
        toast.success("Data guest dipindahkan ke akunmu.");
      })
      .catch((e) => console.warn("migrate failed:", e));
  }, [authUser, guestId, migrateMemFn]);

  // ===== Persisted load =====
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const th = localStorage.getItem(STORAGE.theme);
      if (th === "light" || th === "dark") setTheme(th);
      else if (window.matchMedia?.("(prefers-color-scheme: light)").matches) setTheme("light");

      const rawConvos = localStorage.getItem(STORAGE.convos);
      let loaded: Conversation[] = [];
      if (rawConvos) loaded = JSON.parse(rawConvos);
      else {
        const legacy = localStorage.getItem(STORAGE.legacyMsgs);
        if (legacy) {
          const msgs: Msg[] = JSON.parse(legacy);
          if (msgs.length) loaded = [{ id: crypto.randomUUID(), title: "Percakapan lama", messages: msgs, updatedAt: Date.now() }];
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
      const vt = localStorage.getItem(STORAGE.vvTranslate); if (vt) setVvTranslate(vt === "1");
      const pg = localStorage.getItem(STORAGE.preGen); if (pg) setPreGenAudio(pg === "1");

      const cs = localStorage.getItem(STORAGE.cloneSample);
      const csn = localStorage.getItem(STORAGE.cloneSampleName);
      setHasCloneSample(!!cs);
      if (csn) setCloneSampleName(csn);
    } catch {}
  }, []);

  useEffect(() => {
    if (!conversations.length) return;
    try {
      // Strip large image dataUrls before persisting to localStorage (quota safe).
      const slim = conversations.map((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.imageDataUrl && m.imageDataUrl.length > 200_000 ? { ...m, imageDataUrl: undefined } : m,
        ),
      }));
      localStorage.setItem(STORAGE.convos, JSON.stringify(slim));
    } catch {}
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [conversations, activeId]);

  useEffect(() => {
    if (activeId) try { localStorage.setItem(STORAGE.activeId, activeId); } catch {}
  }, [activeId]);

  useEffect(() => { inputRef.current?.focus(); }, []);

  function toggleTheme() {
    const next: ThemeMode = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem(STORAGE.theme, next); } catch {}
  }

  const updateActiveMessages = useCallback((updater: (prev: Msg[]) => Msg[]) => {
    setConversations((convos) =>
      convos.map((c) => c.id === activeId
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
  function selectConversation(id: string) { stopTTS(); setActiveId(id); setOpenConvos(false); }
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

  // ===== Pre-generate TTS in background for instant playback =====
  async function preGenerateAudio(msg: Msg) {
    if (!preGenAudio) return;
    if (provider !== "voicevox") return;
    if (msg.audioUrl) return;
    const clean = msg.content.replace(/\*[^*]+\*/g, "").trim();
    if (!clean) return;
    try {
      const { mp3Url, emotion } = await ttsVV({
        data: { text: clean.slice(0, 1200), speaker: vvSpeaker, speed, translateToJa: vvTranslate },
      });
      updateMessageById(msg.id, { audioUrl: mp3Url, audioEmotion: emotion });
    } catch (e) {
      // silent — user can still trigger manually
      console.warn("pre-gen tts failed:", e);
    }
  }

  // ===== Send message =====
  async function sendMessage(text: string, retryMsgId?: string) {
    const trimmed = text.trim();
    if ((!trimmed && !pendingImage) || sending) return;

    const imageDataUrl = pendingImage?.dataUrl;

    let userMsgId: string;
    if (retryMsgId) {
      userMsgId = retryMsgId;
      updateMessageById(retryMsgId, { status: "sending", failedPayload: undefined });
    } else {
      userMsgId = crypto.randomUUID();
      const userMsg: Msg = {
        id: userMsgId, role: "user",
        content: trimmed || (imageDataUrl ? "(gambar)" : ""),
        at: Date.now(), status: "sending",
        imageDataUrl,
      };
      updateActiveMessages((prev) => [...prev, userMsg]);
      if (activeConvo && (activeConvo.title === "Percakapan baru" || !activeConvo.title)) {
        const t = (trimmed || "Gambar baru").slice(0, 40).replace(/\s+/g, " ").trim();
        renameConversation(activeConvo.id, t || "Percakapan baru");
      }
      setInput("");
      setPendingImage(null);
    }

    setSending(true);
    setTimeout(() => updateMessageById(userMsgId, { status: "sent" }), 120);
    setTimeout(() => updateMessageById(userMsgId, { status: "delivered" }), 380);

    try {
      const currentMsgs = (conversations.find((c) => c.id === activeId)?.messages ?? []);
      const ctxMsgs = currentMsgs
        .filter((m) => m.status !== "failed")
        .slice(-12)
        .map((m) => ({ role: m.role, content: m.content || "" }));
      if (!ctxMsgs.length || ctxMsgs[ctxMsgs.length - 1]?.content !== (trimmed || (imageDataUrl ? "(gambar)" : ""))) {
        ctxMsgs.push({ role: "user", content: trimmed || (imageDataUrl ? "(gambar)" : "") });
      }

      // Time delta sejak balasan AI terakhir
      const lastAssistant = [...currentMsgs].reverse().find((m) => m.role === "assistant");
      const millisSinceLastAssistant = lastAssistant ? Math.max(0, Date.now() - lastAssistant.at) : undefined;

      const { reply } = await chat({
        data: {
          messages: ctxMsgs,
          characterName: name,
          systemPersona: persona,
          language,
          userId,
          imageDataUrl,
          millisSinceLastAssistant,
        },
      });

      updateMessageById(userMsgId, { status: "read" });

      const aiMsg: Msg = {
        id: crypto.randomUUID(), role: "assistant", content: reply, at: Date.now(),
      };
      updateActiveMessages((prev) => [...prev, aiMsg]);

      // Background pre-gen TTS untuk instant play
      preGenerateAudio(aiMsg);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Gagal kirim";
      toast.error(msg);
      updateMessageById(userMsgId, { status: "failed", failedPayload: trimmed });
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function retrySend(m: Msg) { sendMessage(m.failedPayload ?? m.content, m.id); }

  // ===== TTS =====
  function stopTTS() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPlayingId(null); setPaused(false);
  }
  function pauseTTS() {
    if (audioRef.current && !audioRef.current.paused) { audioRef.current.pause(); setPaused(true); }
  }
  async function resumeTTS() {
    if (audioRef.current && audioRef.current.paused) { await audioRef.current.play(); setPaused(false); }
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
              data: { text: clean.slice(0, 1200), speaker: vvSpeaker, speed, translateToJa: vvTranslate },
            });
            src = mp3Url;
            updateMessageById(msg.id, { audioUrl: mp3Url, audioEmotion: emotion });
          } else {
            const sampleB64 = localStorage.getItem(STORAGE.cloneSample);
            const sampleMime = localStorage.getItem(STORAGE.cloneSampleMime) ?? "audio/wav";
            if (!sampleB64) throw new Error("Belum ada sampel suara. Upload sampel di Pengaturan dulu.");
            const { audio, mime } = await ttsClone({
              data: { text: clean.slice(0, 600), sampleBase64: sampleB64, sampleMime, language: "ja", translateToJa: vvTranslate },
            });
            src = `data:${mime};base64,${audio}`;
            updateMessageById(msg.id, { audioUrl: src });
          }
        } finally { setLoadingId(null); }
      }

      const a = new Audio(src);
      audioRef.current = a;
      setPlayingId(msg.id); setPaused(false);
      a.onended = () => { setPlayingId(null); setPaused(false); audioRef.current = null; };
      a.onerror = () => {
        setPlayingId(null); setPaused(false); audioRef.current = null;
        toast.error("Audio gagal dimuat. URL kedaluwarsa — coba putar ulang.");
        updateMessageById(msg.id, { audioUrl: undefined });
      };
      await a.play();
    } catch (e) {
      setLoadingId(null); setPlayingId(null); setPaused(false);
      toast.error(e instanceof Error ? e.message : "Voice failed");
    }
  }

  // ===== Background image =====
  function handleBgUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result);
      setBg(url);
      try { localStorage.setItem(STORAGE.bg, url); } catch { toast.error("Gambar terlalu besar untuk disimpan."); }
    };
    reader.readAsDataURL(file);
  }

  // ===== Memories =====
  async function refreshMemories() {
    try {
      const { memories } = await listMemFn({ data: { userId } });
      setMemories(memories);
    } catch (e) { toast.error(e instanceof Error ? e.message : "Gagal memuat memori"); }
  }

  // ===== Clone sample upload =====
  function handleSampleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error("Sampel terlalu besar. Maks 5MB."); return; }
    const reader = new FileReader();
    reader.onload = () => {
      const data = String(reader.result);
      const idx = data.indexOf(",");
      const b64 = idx >= 0 ? data.slice(idx + 1) : data;
      try {
        localStorage.setItem(STORAGE.cloneSample, b64);
        localStorage.setItem(STORAGE.cloneSampleMime, file.type || "audio/wav");
        localStorage.setItem(STORAGE.cloneSampleName, file.name);
        setCloneSampleName(file.name); setHasCloneSample(true);
        toast.success(`Sampel "${file.name}" tersimpan.`);
      } catch { toast.error("Gagal menyimpan sampel."); }
    };
    reader.readAsDataURL(file);
  }
  function clearSample() {
    localStorage.removeItem(STORAGE.cloneSample);
    localStorage.removeItem(STORAGE.cloneSampleMime);
    localStorage.removeItem(STORAGE.cloneSampleName);
    setHasCloneSample(false); setCloneSampleName("");
  }

  // ===== Chat image attach (multimodal vision) =====
  async function handleImagePick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { toast.error("File harus berupa gambar."); return; }
    if (file.size > 8 * 1024 * 1024) { toast.error("Gambar terlalu besar. Maks 8MB."); return; }
    try {
      const dataUrl = await compressImage(file, 1280, 0.85);
      setPendingImage({ dataUrl, name: file.name });
    } catch {
      toast.error("Gagal memproses gambar.");
    } finally {
      if (imageInputRef.current) imageInputRef.current.value = "";
    }
  }

  // ===== Auth =====
  async function loginGoogle() {
    try {
      const result = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
      if (result.error) toast.error("Login gagal: " + (result.error.message ?? "unknown"));
    } catch (e) { toast.error(e instanceof Error ? e.message : "Login gagal"); }
  }
  async function logout() {
    await supabase.auth.signOut();
    toast.success("Sudah logout. Kembali ke mode guest.");
  }

  function savePref(key: string, value: string) { try { localStorage.setItem(key, value); } catch {} }
  function clearChat() { updateActiveMessages(() => []); }

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-background text-foreground">
      <img src={bg} alt={`${name} background`} className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <div className={`pointer-events-none absolute inset-0 ${
        theme === "dark"
          ? "bg-gradient-to-b from-black/40 via-black/10 to-black/70"
          : "bg-gradient-to-b from-white/30 via-white/10 to-white/60"
      }`} />

      {/* Top bar */}
      <header className="absolute left-0 right-0 top-0 z-20 flex items-center justify-between p-3 sm:p-4">
        <div className="flex items-center gap-2 min-w-0">
          <div className="glass-chip rounded-full px-3 py-1.5 text-sm font-medium max-w-[55vw] truncate flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            <span className="truncate">{name}</span>
            {activeConvo && <span className="text-xs opacity-60 truncate">· {activeConvo.title}</span>}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Button size="icon" variant="ghost" onClick={toggleTheme}
            className="glass-chip rounded-full h-9 w-9" aria-label="Ganti tema">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>

          <Button size="icon" variant="ghost" onClick={startNewConversation}
            className="glass-chip rounded-full h-9 w-9" aria-label="Percakapan baru" title="Percakapan baru">
            <MessageSquarePlus className="h-4 w-4" />
          </Button>

          <Sheet open={openConvos} onOpenChange={setOpenConvos}>
            <SheetTrigger asChild>
              <Button size="icon" variant="ghost" className="glass-chip rounded-full h-9 w-9" aria-label="Riwayat percakapan">
                <MessagesSquare className="h-4 w-4" />
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
              <Button size="icon" variant="ghost" className="glass-chip rounded-full h-9 w-9" aria-label="Pengaturan">
                <Settings className="h-4 w-4" />
              </Button>
            </SheetTrigger>

            <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
              <SheetHeader>
                <SheetTitle>Pengaturan</SheetTitle>
                <SheetDescription>Personalisasi karakter, suara, akun, dan memori.</SheetDescription>
              </SheetHeader>

              <div className="mt-6 space-y-6">
                <section className="rounded-lg border bg-muted/30 p-3 space-y-2">
                  <Label className="text-xs font-semibold uppercase tracking-wider">Tampilan</Label>
                  <div className="flex items-center justify-between">
                    <span className="text-sm">Tema</span>
                    <Button size="sm" variant="outline" onClick={toggleTheme}>
                      {theme === "dark" ? <><Sun className="mr-2 h-4 w-4" />Terang</> : <><Moon className="mr-2 h-4 w-4" />Gelap</>}
                    </Button>
                  </div>
                </section>

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
                        Mode guest. Login opsional — saat login pertama, memori guest otomatis dipindahkan.
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

                <section className="space-y-3">
                  <Label>Mesin suara (TTS)</Label>
                  <Select value={provider} onValueChange={(v) => { setProvider(v as TTSProvider); savePref(STORAGE.provider, v); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="voicevox">VOICEVOX — anime Jepang (gratis, stabil)</SelectItem>
                      <SelectItem value="clone">Voice Clone — suara asli (HF, beta)</SelectItem>
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
                      <div className="flex items-center justify-between">
                        <Label className="text-xs">Pre-generate audio (instant play)</Label>
                        <Switch checked={preGenAudio}
                          onCheckedChange={(c) => { setPreGenAudio(c); savePref(STORAGE.preGen, c ? "1" : "0"); }} />
                      </div>
                      <p className="text-[11px] leading-relaxed text-muted-foreground">
                        Teks tetap bahasamu, suara dibacakan Jepang ala anime. Saat aktif, audio disiapkan otomatis di latar agar tombol ▶ langsung berbunyi tanpa delay.
                      </p>
                    </div>
                  ) : (
                    <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                      <Label className="text-xs font-semibold flex items-center gap-1">
                        <Sparkles className="h-3 w-3" /> Sampel suara karakter
                      </Label>
                      <p className="text-[10px] leading-relaxed text-muted-foreground">
                        Upload 1 file audio (mp3/wav, 10–30 detik, jernih, tanpa musik). Clone via Hugging Face XTTS-v2 (kadang antri).
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
                    </div>
                  )}

                  <p className="pt-2 text-[11px] leading-relaxed text-muted-foreground">
                    <Volume2 className="mr-1 inline h-3 w-3" />
                    Tombol ▶ di tiap balon AI untuk memutar suara.
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
                        setNewMem(""); refreshMemories();
                      } catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
                    }}><Plus className="h-4 w-4" /></Button>
                  </div>
                  <div className="max-h-64 space-y-1 overflow-y-auto rounded-md border p-2 text-sm">
                    {memories.length === 0 && <p className="text-muted-foreground">Belum ada memori.</p>}
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
      <main ref={scrollRef} className="absolute inset-0 z-10 flex flex-col gap-3 overflow-y-auto px-3 pt-20 pb-36 sm:px-4">
        {messages.length === 0 && (
          <div className="mt-auto mb-4 max-w-[85%] self-start animate-fade-in">
            <div className="bubble-ai rounded-2xl px-4 py-3 text-sm shadow-lg">
              Halo… akhirnya kamu datang juga~ ✦ Aku {name}. Ceritakan apa saja.
            </div>
            <div className="mt-1 px-1 text-[10px] opacity-70">{fmtTime(Date.now())}</div>
          </div>
        )}
        <div className="mt-auto" />
        {messages.map((m) => {
          const isUser = m.role === "user";
          const isPlaying = playingId === m.id;
          const isLoading = loadingId === m.id;
          return (
            <div key={m.id} className={`flex max-w-[85%] flex-col animate-fade-in ${isUser ? "self-end items-end" : "self-start items-start"}`}>
              <div className={`${isUser ? "bubble-user" : "bubble-ai"} rounded-2xl px-4 py-2.5 text-sm shadow-lg`}>
                {m.imageDataUrl && (
                  <img src={m.imageDataUrl} alt="lampiran" className="mb-2 max-h-64 w-full rounded-lg object-cover" />
                )}
                {m.content && <div className="whitespace-pre-wrap break-words">{m.content}</div>}
              </div>

              <div className="mt-1 flex items-center gap-1.5 px-1">
                <span className="text-[10px] opacity-70 tabular-nums">{fmtTime(m.at)}</span>

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
                      <span className="glass-chip inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px]">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        Menyiapkan suara…
                      </span>
                    )}
                    {!isLoading && !isPlaying && (
                      <button onClick={() => playTTS(m)}
                        className="glass-chip rounded-full p-1.5 transition hover:scale-105"
                        aria-label="Putar" title={m.audioUrl ? "Putar (siap)" : "Putar (akan disiapkan)"}>
                        <Play className="h-3 w-3" />
                      </button>
                    )}
                    {!isLoading && isPlaying && !paused && (
                      <button onClick={pauseTTS} className="glass-chip rounded-full p-1.5" aria-label="Jeda">
                        <Pause className="h-3 w-3" />
                      </button>
                    )}
                    {!isLoading && isPlaying && paused && (
                      <button onClick={resumeTTS} className="glass-chip rounded-full p-1.5" aria-label="Lanjutkan">
                        <Play className="h-3 w-3" />
                      </button>
                    )}
                    {!isLoading && isPlaying && (
                      <button onClick={stopTTS} className="glass-chip rounded-full p-1.5" aria-label="Berhenti">
                        <Square className="h-3 w-3" />
                      </button>
                    )}
                    {m.audioUrl && !isPlaying && !isLoading && (
                      <span className="text-[10px] opacity-60">●</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {sending && (
          <div className="max-w-[85%] self-start bubble-ai rounded-2xl px-4 py-2.5 text-sm shadow-lg">
            <span className="inline-flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.3s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.15s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50" />
            </span>
          </div>
        )}
      </main>

      {/* Composer */}
      <div className="composer-glass absolute bottom-0 left-0 right-0 z-20 p-3">
        <div className="mx-auto max-w-2xl">
          {pendingImage && (
            <div className="mb-2 flex items-center gap-2 rounded-lg border bg-card/70 p-2">
              <img src={pendingImage.dataUrl} alt="preview" className="h-14 w-14 rounded object-cover" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">{pendingImage.name}</p>
                <p className="text-[10px] text-muted-foreground">Akan dikirim bersama pesan</p>
              </div>
              <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setPendingImage(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
          <div className="flex items-end gap-2 rounded-2xl border bg-background/60 px-2 py-1.5 backdrop-blur">
            <input ref={imageInputRef} type="file" accept="image/*" onChange={handleImagePick} className="hidden" />
            <Button size="icon" variant="ghost" className="h-9 w-9 rounded-full"
              onClick={() => imageInputRef.current?.click()} aria-label="Kirim gambar" title="Kirim gambar">
              <ImageIcon className="h-4 w-4" />
            </Button>
            <Textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
              placeholder="Ketik pesan..." rows={1}
              className="max-h-32 min-h-[40px] flex-1 resize-none border-0 bg-transparent focus-visible:ring-0 shadow-none" />
            <Button onClick={() => sendMessage(input)} disabled={sending || (!input.trim() && !pendingImage)}
              size="icon" className="h-10 w-10 rounded-full">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MsgStatusIcon({ status }: { status?: MsgStatus }) {
  if (!status) return null;
  if (status === "sending") return <Loader2 className="h-3 w-3 animate-spin opacity-70" />;
  if (status === "sent") return <Check className="h-3 w-3 opacity-70" />;
  if (status === "delivered") return <CheckCheck className="h-3 w-3 opacity-70" />;
  if (status === "read") return (
    <span className="inline-flex animate-[pop_0.4s_ease-out]">
      <CheckCheck className="h-3 w-3 text-sky-400" />
    </span>
  );
  if (status === "failed") return <AlertCircle className="h-3 w-3 text-red-400" />;
  return null;
}

// Compress an uploaded image to a downscaled JPEG dataURL.
async function compressImage(file: File, maxDim: number, quality: number): Promise<string> {
  const dataUrl: string = await new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result));
    r.onerror = () => rej(r.error);
    r.readAsDataURL(file);
  });
  const img: HTMLImageElement = await new Promise((res, rej) => {
    const i = new Image();
    i.onload = () => res(i);
    i.onerror = () => rej(new Error("img load"));
    i.src = dataUrl;
  });
  const ratio = Math.min(1, maxDim / Math.max(img.width, img.height));
  const w = Math.round(img.width * ratio);
  const h = Math.round(img.height * ratio);
  const canvas = document.createElement("canvas");
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return dataUrl;
  ctx.drawImage(img, 0, 0, w, h);
  return canvas.toDataURL("image/jpeg", quality);
}
