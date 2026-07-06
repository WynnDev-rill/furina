import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Send, Settings, Trash2, Plus, Volume2, Image as ImageIcon, RotateCcw,
  Play, Pause, Square, Loader2, MessageSquarePlus, MessagesSquare, Check,
  CheckCheck, Pencil, AlertCircle, LogIn, LogOut, Sparkles, Sun, Moon, X,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger, SheetDescription } from "@/components/ui/sheet";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
  updateMemory,
  clearAllMemories,
  migrateGuestMemories,
  summarizeConversation,
  updateStyleProfile,
  compactMemories,
  proactiveGreeting,
  getMood,
} from "@/lib/furina.functions";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Furina — AI Companion" },
      { name: "description", content: "Personal AI companion dengan suara Jepang natural, memori lintas-percakapan, dan kepribadian Furina." },
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
  stickerId?: string;
};
type TTSProvider = "voicevox" | "clone";
type Conversation = { id: string; title: string; messages: Msg[]; updatedAt: number; lastSummaryCount?: number };
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

const ALL_FURINA_KEYS = [
  STORAGE.convos, STORAGE.activeId, STORAGE.bg, STORAGE.name, STORAGE.persona,
  STORAGE.lang, STORAGE.speed, STORAGE.provider, STORAGE.vvSpeaker, STORAGE.vvTranslate,
  STORAGE.cloneSample, STORAGE.cloneSampleMime, STORAGE.cloneSampleName,
  STORAGE.theme, STORAGE.preGen,
  // guestId and migratedFlag are NOT cleared on logout — they belong to the browser identity
];

function clearAllFurinaLocal() {
  for (const k of ALL_FURINA_KEYS) {
    try { localStorage.removeItem(k); } catch {}
  }
}

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "Percakapan baru", messages: [], updatedAt: Date.now() };
}
function getOrCreateGuestId(): string {
  if (typeof window === "undefined") return "guest-ssr";
  let id = localStorage.getItem(STORAGE.guestId);
  if (!id) { id = crypto.randomUUID(); localStorage.setItem(STORAGE.guestId, id); }
  return id;
}

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

// (Sticker feature removed.)



// Natural relative time (display side — matches server humanizeDelta vibe)
function relTime(ts: number, now: number): string {
  const ms = now - ts;
  const s = Math.round(ms / 1000);
  if (s < 10) return "baru saja";
  if (s < 60) return "beberapa detik lalu";
  const m = Math.round(s / 60);
  if (m < 2) return "barusan";
  if (m < 5) return "beberapa menit lalu";
  if (m < 25) return `${m} menit lalu`;
  if (m < 40) return "setengah jam lalu";
  if (m < 80) return "sekitar sejam lalu";
  const h = Math.round(m / 60);
  if (h < 6) return `${h} jam lalu`;
  const d = new Date(ts);
  const sameDay = new Date(now).toDateString() === d.toDateString();
  if (sameDay) {
    const hh = d.getHours();
    if (hh < 11) return "tadi pagi";
    if (hh < 15) return "tadi siang";
    if (hh < 18) return "tadi sore";
    return "tadi malam";
  }
  const yest = new Date(now); yest.setDate(yest.getDate() - 1);
  if (yest.toDateString() === d.toDateString()) return "kemarin";
  const days = Math.round((now - ts) / 86400000);
  if (days < 7) return `${days} hari lalu`;
  return d.toLocaleDateString();
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ===== Settings snapshot (sync to DB) =====
type SettingsSnapshot = {
  bg?: string;
  name?: string;
  persona?: string;
  lang?: string;
  speed?: number;
  provider?: TTSProvider;
  vvSpeaker?: number;
  vvTranslate?: boolean;
  preGen?: boolean;
  theme?: ThemeMode;
  cloneSampleName?: string;
  cloneSampleMime?: string;
  cloneSampleB64?: string; // small samples only — large ones live in storage bucket
};

function FurinaApp() {
  const chat = useServerFn(chatWithFurina);
  const ttsVV = useServerFn(speakVoicevoxUrl);
  const ttsClone = useServerFn(speakClone);
  const listMemFn = useServerFn(listMemories);
  const delMemFn = useServerFn(deleteMemory);
  const addMemFn = useServerFn(addMemory);
  const updateMemFn = useServerFn(updateMemory);
  const clearMemFn = useServerFn(clearAllMemories);
  const migrateMemFn = useServerFn(migrateGuestMemories);
  const summarizeFn = useServerFn(summarizeConversation);
  const updateStyleFn = useServerFn(updateStyleProfile);
  const compactMemFn = useServerFn(compactMemories);
  const proactiveFn = useServerFn(proactiveGreeting);
  const getMoodFn = useServerFn(getMood);

  const [authUser, setAuthUser] = useState<{ id: string; email?: string } | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [syncing, setSyncing] = useState(false);
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
  const [memories, setMemories] = useState<{ id: string; content: string; kind?: string; importance?: number; occurred_at?: string | null; emotion?: string | null; compressed?: boolean }[]>([]);
  const [newMem, setNewMem] = useState("");
  const [editingMemId, setEditingMemId] = useState<string | null>(null);
  const [editingMemContent, setEditingMemContent] = useState("");
  const [editingMemImportance, setEditingMemImportance] = useState(5);
  const [editingMemOccurred, setEditingMemOccurred] = useState<string>("");
  const [memFilter, setMemFilter] = useState<string>("all");
  const [memSearch, setMemSearch] = useState<string>("");

  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [editingTitleId, setEditingTitleId] = useState<string | null>(null);
  const [editingTitleVal, setEditingTitleVal] = useState("");
  const [cloneSampleName, setCloneSampleName] = useState<string>("");
  const [hasCloneSample, setHasCloneSample] = useState(false);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [mood, setMood] = useState<{ score: number; label: string }>({ score: 0, label: "adem" });
  const [proactiveEnabled, setProactiveEnabled] = useState(true);
  const [proactiveIdleHours, setProactiveIdleHours] = useState(6);
  const proactiveFiredRef = useRef(false);
  const lastActivityKey = "furina:lastActivityAt";

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const lastSyncedAuthIdRef = useRef<string | null>(null);
  const initialLoadDoneRef = useRef(false);
  const cloudHydratedRef = useRef(false);
  const settingsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const conversationsDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userMsgCountRef = useRef(0);

  const activeConvo = conversations.find((c) => c.id === activeId);
  const messages = useMemo(() => activeConvo?.messages ?? [], [activeConvo]);

  // ===== Apply theme to <html> =====
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  // ===== Auth listener =====
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.user) setAuthUser({ id: data.session.user.id, email: data.session.user.email ?? undefined });
      setAuthReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) => {
      setAuthUser(session?.user ? { id: session.user.id, email: session.user.email ?? undefined } : null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  // ===== Fetch mood on user change =====
  useEffect(() => {
    if (!userId) return;
    getMoodFn({ data: { userId } }).then((r) => {
      if (r?.mood) setMood({ score: r.mood.score, label: r.label });
    }).catch(() => {});
  }, [userId, getMoodFn]);

  // ===== Proactive greeting on idle-return =====
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!proactiveEnabled) return;

    const tryGreet = async () => {
      if (proactiveFiredRef.current) return;
      if (document.visibilityState !== "visible") return;
      const last = parseInt(localStorage.getItem(lastActivityKey) ?? "0", 10);
      if (!last) { proactiveFiredRef.current = true; return; }
      const hoursIdle = (Date.now() - last) / (1000 * 60 * 60);
      if (hoursIdle < proactiveIdleHours) return;
      proactiveFiredRef.current = true;
      try {
        const r = await proactiveFn({ data: { userId, characterName: name, hoursIdle: Math.min(720, hoursIdle) } });
        if (r?.ok && r.greeting) {
          const aiMsg: Msg = { id: crypto.randomUUID(), role: "assistant", content: r.greeting, at: Date.now() };
          setConversations((convos) => convos.map((c) => c.id === activeId
            ? { ...c, messages: [...c.messages, aiMsg], updatedAt: Date.now() }
            : c));
          if (authUser && activeId) upsertSingleMessage(authUser.id, activeId, aiMsg);
          if (r.mood) setMood(r.mood);
        }
      } catch {}
    };

    const onVis = () => tryGreet();
    document.addEventListener("visibilitychange", onVis);
    // Coba juga langsung saat mount
    const t = setTimeout(tryGreet, 1500);
    return () => { document.removeEventListener("visibilitychange", onVis); clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proactiveEnabled, proactiveIdleHours, userId, activeId, name, authUser]);

  // Touch lastActivity setiap kali user interaksi kirim
  useEffect(() => {
    if (typeof window === "undefined") return;
    const touch = () => { try { localStorage.setItem(lastActivityKey, String(Date.now())); } catch {} };
    window.addEventListener("focus", touch);
    return () => window.removeEventListener("focus", touch);
  }, []);
  const buildSettings = useCallback((): SettingsSnapshot => ({
    bg, name, persona, lang: language, speed, provider, vvSpeaker, vvTranslate, preGen: preGenAudio, theme,
    cloneSampleName,
    cloneSampleMime: typeof window !== "undefined" ? localStorage.getItem(STORAGE.cloneSampleMime) ?? undefined : undefined,
    cloneSampleB64: typeof window !== "undefined" ? localStorage.getItem(STORAGE.cloneSample) ?? undefined : undefined,
  }), [bg, name, persona, language, speed, provider, vvSpeaker, vvTranslate, preGenAudio, theme, cloneSampleName]);

  const applySettings = useCallback((s: SettingsSnapshot) => {
    if (s.bg) setBg(s.bg);
    if (s.name) setName(s.name);
    // Persona: hanya overwrite kalau cloud punya isi non-kosong.
    // String kosong dari cloud dianggap "belum diset" biar tidak menimpa persona lokal.
    if (typeof s.persona === "string" && s.persona.trim().length > 0) setPersona(s.persona);
    if (s.lang) setLanguage(s.lang as typeof language);
    if (typeof s.speed === "number") setSpeed(s.speed);
    if (s.provider === "voicevox" || s.provider === "clone") setProvider(s.provider);
    if (typeof s.vvSpeaker === "number") setVvSpeaker(s.vvSpeaker);
    if (typeof s.vvTranslate === "boolean") setVvTranslate(s.vvTranslate);
    if (typeof s.preGen === "boolean") setPreGenAudio(s.preGen);
    if (s.theme === "dark" || s.theme === "light") setTheme(s.theme);
    if (s.cloneSampleName) setCloneSampleName(s.cloneSampleName);
    if (s.cloneSampleB64 && s.cloneSampleMime) {
      try {
        localStorage.setItem(STORAGE.cloneSample, s.cloneSampleB64);
        localStorage.setItem(STORAGE.cloneSampleMime, s.cloneSampleMime);
        if (s.cloneSampleName) localStorage.setItem(STORAGE.cloneSampleName, s.cloneSampleName);
        setHasCloneSample(true);
      } catch {}
    }
  }, []);

  // ===== Load from local on mount (guest mode entry point) =====
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
    initialLoadDoneRef.current = true;
  }, []);

  // ===== Sync on auth change =====
  useEffect(() => {
    if (!authReady) return;
    if (!authUser) {
      lastSyncedAuthIdRef.current = null;
      cloudHydratedRef.current = false;
      return;
    }
    if (lastSyncedAuthIdRef.current === authUser.id) return;
    lastSyncedAuthIdRef.current = authUser.id;
    cloudHydratedRef.current = false;
    pullFromCloud(authUser.id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authReady, authUser]);



  async function pullFromCloud(uid: string) {
    setSyncing(true);
    try {
      const [{ data: settingsRow }, { data: convosRows }, { data: msgsRows }] = await Promise.all([
        supabase.from("user_settings").select("data").eq("user_id", uid).maybeSingle(),
        supabase.from("conversations").select("*").eq("user_id", uid).eq("character_id", "furina").order("updated_at", { ascending: false }),
        supabase.from("messages").select("*").eq("user_id", uid).order("created_at", { ascending: true }),
      ]);

      const hasCloudData = !!settingsRow || (convosRows && convosRows.length > 0);
      const hasLocalData = !!localStorage.getItem(STORAGE.convos) || !!localStorage.getItem(STORAGE.name);

      if (!hasCloudData && hasLocalData) {
        const migratedTo = localStorage.getItem(STORAGE.migratedFlag);
        if (migratedTo !== uid) {
          // Auto-migrate guest data → account
          await migrateMemFn({ data: { fromGuestId: guestId, toUserId: uid } }).catch((e) => console.warn("mem migrate:", e));
          await pushSettingsTo(uid, buildSettings());
          await pushAllConversationsTo(uid, conversations);
          localStorage.setItem(STORAGE.migratedFlag, uid);
          toast.success("Data guest dipindahkan ke akunmu.");
          cloudHydratedRef.current = true;
          setSyncing(false);
          return;
        }
      }

      if (hasCloudData) {
        // Hydrate from cloud (this is the source of truth)
        if (settingsRow?.data) applySettings(settingsRow.data as SettingsSnapshot);

        const byConv: Record<string, Msg[]> = {};
        for (const r of (msgsRows ?? [])) {
          const list = byConv[r.conversation_id] ?? (byConv[r.conversation_id] = []);
          list.push({
            id: r.id,
            role: (r.role as "user" | "assistant"),
            content: r.content,
            at: new Date(r.created_at).getTime(),
            status: (r.status as MsgStatus) ?? "read",
            audioUrl: r.audio_url ?? undefined,
            audioEmotion: r.audio_emotion ?? undefined,
            imageDataUrl: r.image_url ?? undefined,
            stickerId: r.sticker_id ?? undefined,
          });
        }
        const convList: Conversation[] = (convosRows ?? []).map((c) => ({
          id: c.id,
          title: c.title,
          messages: byConv[c.id] ?? [],
          updatedAt: new Date(c.updated_at).getTime(),
        }));
        if (!convList.length) convList.push(newConversation());
        setConversations(convList);
        // Preserve last active convo kalau masih ada di list; kalau tidak, pilih terbaru.
        const savedActive = typeof window !== "undefined" ? localStorage.getItem(STORAGE.activeId) : null;
        const preserved = savedActive && convList.some((c) => c.id === savedActive) ? savedActive : convList[0].id;
        setActiveId(preserved);
      } else if (hasLocalData) {
        // Cloud kosong tapi local punya data → push local ke cloud (bukan reset).
        // Ini fallback aman kalau flag migrasi sebelumnya sudah diset tapi cloud entah kenapa hilang.
        try {
          await pushAllConversationsTo(uid, conversations);
          await pushSettingsTo(uid, buildSettings());
          toast.info("Menyimpan ulang data lokal ke akun.");
        } catch (e) { console.warn("re-sync local→cloud:", e); }
      } else {
        // Brand new account, no local data either → fresh start
        const fresh = [newConversation()];
        setConversations(fresh);
        setActiveId(fresh[0].id);
        // Also reset visual / settings to defaults
        setBg(furinaDefault); setName("Furina"); setPersona(""); setLanguage("auto");
        setSpeed(1.0); setProvider("voicevox"); setVvSpeaker(VV_SPEAKERS[0].id);
        setVvTranslate(true); setPreGenAudio(true);
      }

    } catch (e) {
      console.error("pullFromCloud:", e);
      toast.error("Gagal sinkronisasi data dari akun.");
    } finally {
      cloudHydratedRef.current = true;
      setSyncing(false);
    }
  }

  async function pushSettingsTo(uid: string, s: SettingsSnapshot) {
    try {
      let payload: SettingsSnapshot = s;
      // Defense-in-depth: kalau persona lokal kosong tapi cloud punya isi,
      // jangan overwrite persona di cloud. Merge fields lain seperti biasa.
      if (!s.persona || s.persona.trim().length === 0) {
        const { data: existing } = await supabase
          .from("user_settings").select("data").eq("user_id", uid).maybeSingle();
        const cloudPersona = (existing?.data as SettingsSnapshot | undefined)?.persona;
        if (cloudPersona && cloudPersona.trim().length > 0) {
          payload = { ...s, persona: cloudPersona };
        }
      }
      await supabase.from("user_settings").upsert({ user_id: uid, data: payload, updated_at: new Date().toISOString() });
    } catch (e) {
      console.warn("settings push failed:", e);
    }
  }

  async function pushAllConversationsTo(uid: string, convs: Conversation[]) {
    if (!convs.length) return;
    try {
      const convRows = convs.map((c) => ({
        id: c.id, user_id: uid, character_id: "furina", title: c.title,
        updated_at: new Date(c.updatedAt).toISOString(),
      }));
      await supabase.from("conversations").upsert(convRows);
      const msgRows = convs.flatMap((c) => c.messages.map((m) => ({
        id: m.id, conversation_id: c.id, user_id: uid, role: m.role,
        content: m.content, status: m.status ?? "sent",
        created_at: new Date(m.at).toISOString(),
        audio_url: m.audioUrl ?? null, audio_emotion: m.audioEmotion ?? null,
        image_url: m.imageDataUrl && m.imageDataUrl.length < 300000 ? m.imageDataUrl : null,
        sticker_id: m.stickerId ?? null,
      })));
      // chunk to avoid payload limits
      for (let i = 0; i < msgRows.length; i += 200) {
        await supabase.from("messages").upsert(msgRows.slice(i, i + 200));
      }
    } catch (e) {
      console.warn("conversations push failed:", e);
    }
  }

  async function upsertSingleMessage(uid: string, convId: string, m: Msg) {
    try {
      await supabase.from("messages").upsert({
        id: m.id, conversation_id: convId, user_id: uid, role: m.role,
        content: m.content, status: m.status ?? "sent",
        created_at: new Date(m.at).toISOString(),
        audio_url: m.audioUrl ?? null, audio_emotion: m.audioEmotion ?? null,
        image_url: m.imageDataUrl && m.imageDataUrl.length < 300000 ? m.imageDataUrl : null,
        sticker_id: m.stickerId ?? null,
      });
    } catch (e) {
      console.warn("message upsert:", e);
    }
  }

  async function upsertSingleConversation(uid: string, c: Conversation) {
    try {
      await supabase.from("conversations").upsert({
        id: c.id, user_id: uid, character_id: "furina", title: c.title,
        updated_at: new Date(c.updatedAt).toISOString(),
      });
    } catch (e) {
      console.warn("conv upsert:", e);
    }
  }

  // ===== Auto-persist conversations to localStorage + cloud (debounced) =====
  // NOTE: Hanya push conversation row untuk convo AKTIF, tidak semua.
  // Mass-push sebelumnya membuat semua conversations.updated_at jadi sama (bug: waktu riwayat seragam)
  // dan berpotensi race dengan per-message upsert (bug: pesan terbaru sesekali "hilang").
  // Message rows tetap ditulis per-bubble via upsertSingleMessage().
  useEffect(() => {
    if (!conversations.length) return;
    try {
      const slim = conversations.map((c) => ({
        ...c,
        messages: c.messages.map((m) =>
          m.imageDataUrl && m.imageDataUrl.length > 200_000 ? { ...m, imageDataUrl: undefined } : m,
        ),
      }));
      localStorage.setItem(STORAGE.convos, JSON.stringify(slim));
    } catch {}
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });

    if (authUser && initialLoadDoneRef.current && activeId) {
      const active = conversations.find((c) => c.id === activeId);
      if (!active) return;
      if (conversationsDebounceRef.current) clearTimeout(conversationsDebounceRef.current);
      conversationsDebounceRef.current = setTimeout(() => {
        upsertSingleConversation(authUser.id, active).catch(() => {});
      }, 1200);
    }
  }, [conversations, authUser, activeId]);


  useEffect(() => {
    if (activeId) try { localStorage.setItem(STORAGE.activeId, activeId); } catch {}
  }, [activeId]);

  // ===== Auto-persist settings to cloud (debounced) =====
  useEffect(() => {
    if (!authUser || !initialLoadDoneRef.current) return;
    // WAJIB: tunggu sampai pullFromCloud selesai supaya push tidak menimpa
    // data cloud dengan state kosong hasil mount awal.
    if (!cloudHydratedRef.current) return;
    if (settingsDebounceRef.current) clearTimeout(settingsDebounceRef.current);
    settingsDebounceRef.current = setTimeout(() => {
      pushSettingsTo(authUser.id, buildSettings()).catch(() => {});
    }, 800);
  }, [authUser, buildSettings]);

  // Auto-focus dihapus agar keyboard tidak muncul otomatis di mobile

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
    if (authUser) upsertSingleConversation(authUser.id, c);
    setTimeout(() => inputRef.current?.focus(), 0);
  }
  function selectConversation(id: string) { stopTTS(); setActiveId(id); setOpenConvos(false); }
  async function deleteConversation(id: string) {
    setConversations((prev) => {
      const filtered = prev.filter((c) => c.id !== id);
      const next = filtered.length ? filtered : [newConversation()];
      if (id === activeId) setActiveId(next[0].id);
      return next;
    });
    if (authUser) {
      try {
        await supabase.from("messages").delete().eq("conversation_id", id).eq("user_id", authUser.id);
        await supabase.from("conversations").delete().eq("id", id).eq("user_id", authUser.id);
      } catch (e) { console.warn(e); }
    }
  }
  function renameConversation(id: string, title: string) {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title: title.trim() || c.title } : c)));
    if (authUser) {
      const c = conversations.find((x) => x.id === id);
      if (c) upsertSingleConversation(authUser.id, { ...c, title: title.trim() || c.title });
    }
  }

  async function preGenerateAudio(msg: Msg) {
    if (!preGenAudio) return;
    if (provider !== "voicevox") return;
    if (msg.audioUrl) return;
    if (msg.stickerId) return;
    const clean = msg.content.replace(/\*[^*]+\*/g, "").replace(/\[stiker:[^\]]*\]/g, "").trim();
    if (!clean) return;
    try {
      const { mp3Url, emotion } = await ttsVV({
        data: { text: clean.slice(0, 1200), speaker: vvSpeaker, speed, translateToJa: vvTranslate },
      });
      updateMessageById(msg.id, { audioUrl: mp3Url, audioEmotion: emotion });
    } catch (e) {
      console.warn("pre-gen tts failed:", e);
    }
  }

  // Trigger summarization every 20 user+assistant messages
  async function maybeSummarize(conv: Conversation) {
    const total = conv.messages.length;
    const last = conv.lastSummaryCount ?? 0;
    if (total - last < 20) return;
    const transcript = conv.messages
      .slice(-30)
      .map((m) => `${m.role === "user" ? "USER" : "FURINA"}: ${m.content}`)
      .join("\n");
    try {
      await summarizeFn({ data: { userId, conversationTitle: conv.title, transcript } });
      setConversations((prev) => prev.map((c) => c.id === conv.id ? { ...c, lastSummaryCount: total } : c));
    } catch (e) {
      console.warn("summarize failed:", e);
    }
  }

  // ===== Send =====
  async function sendMessage(text: string, retryMsgId?: string) {
    const trimmed = text.trim();
    if (!trimmed && !pendingImage) return;
    if (sending) return;

    const imageDataUrl = pendingImage?.dataUrl;
    const messageContent = trimmed || (imageDataUrl ? "(gambar)" : "");

    let userMsgId: string;
    if (retryMsgId) {
      userMsgId = retryMsgId;
      updateMessageById(retryMsgId, { status: "sending", failedPayload: undefined });
    } else {
      userMsgId = crypto.randomUUID();
      const userMsg: Msg = {
        id: userMsgId, role: "user",
        content: messageContent,
        at: Date.now(), status: "sending",
        imageDataUrl,
      };
      updateActiveMessages((prev) => [...prev, userMsg]);
      if (activeConvo && (activeConvo.title === "Percakapan baru" || !activeConvo.title)) {
        const t = (trimmed || "Gambar baru").slice(0, 40).replace(/\s+/g, " ").trim();
        renameConversation(activeConvo.id, t || "Percakapan baru");
      }
      if (authUser && activeConvo) {
        upsertSingleMessage(authUser.id, activeConvo.id, userMsg);
        upsertSingleConversation(authUser.id, { ...activeConvo, updatedAt: Date.now() });
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
      if (!ctxMsgs.length || ctxMsgs[ctxMsgs.length - 1]?.content !== messageContent) {
        ctxMsgs.push({ role: "user", content: messageContent });
      }

      const lastAssistant = [...currentMsgs].reverse().find((m) => m.role === "assistant");
      const millisSinceLastAssistant = lastAssistant ? Math.max(0, Date.now() - lastAssistant.at) : undefined;

      const chatResult = await chat({
        data: {
          messages: ctxMsgs,
          characterName: name,
          systemPersona: persona,
          language,
          userId,
          imageDataUrl,
          millisSinceLastAssistant,
          conversationId: activeId,
          clientNow: Date.now(),
          tz: (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { return undefined; } })(),
        },
      });

      const bubbles: string[] = (chatResult as { bubbles?: string[]; reply: string }).bubbles?.length
        ? (chatResult as { bubbles: string[] }).bubbles
        : [chatResult.reply];
      const moodOut = (chatResult as { mood?: { score: number; label: string } }).mood;
      if (moodOut) setMood(moodOut);

      updateMessageById(userMsgId, { status: "read" });
      try { localStorage.setItem(lastActivityKey, String(Date.now())); } catch {}
      proactiveFiredRef.current = true;

      // Render bubbles one-by-one with typing delay based on length
      let lastAiMsg: Msg | null = null;
      for (let i = 0; i < bubbles.length; i++) {
        const text = bubbles[i];
        if (i > 0) {
          const words = text.split(/\s+/).length;
          const delayMs = Math.min(1600, 350 + words * 55);
          await new Promise((r) => setTimeout(r, delayMs));
        }
        const aiMsg: Msg = {
          id: crypto.randomUUID(), role: "assistant", content: text, at: Date.now(),
        };
        lastAiMsg = aiMsg;
        updateActiveMessages((prev) => [...prev, aiMsg]);
        if (authUser && activeConvo) upsertSingleMessage(authUser.id, activeConvo.id, aiMsg);
      }

      // Audio hanya di bubble terakhir
      if (lastAiMsg) preGenerateAudio(lastAiMsg);

      // Background: maybe summarize
      const updatedConv = conversations.find((c) => c.id === activeId);
      if (updatedConv && lastAiMsg) maybeSummarize({ ...updatedConv, messages: [...updatedConv.messages, lastAiMsg] });


      // Style profile update every 10 user messages
      userMsgCountRef.current += 1;
      if (userMsgCountRef.current % 10 === 0) {
        const recentUserMsgs = (updatedConv?.messages ?? [])
          .filter((m) => m.role === "user" && m.content)
          .slice(-30)
          .map((m) => m.content);
        if (recentUserMsgs.length >= 3) {
          updateStyleFn({ data: { userId, userMessages: recentUserMsgs } }).catch(() => {});
        }
      }

      // Background: compact old memories (rate-limited server-side)
      compactMemFn({ data: { userId, threshold: 60, batch: 15, force: false } }).catch(() => {});
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Gagal kirim";
      toast.error(msg);
      updateMessageById(userMsgId, { status: "failed", failedPayload: trimmed });
    } finally {
      setSending(false);
    }
  }

  function retrySend(m: Msg) { sendMessage(m.failedPayload ?? m.content, m.id); }



  // ===== TTS controls =====
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
      const clean = msg.content.replace(/\*[^*]+\*/g, "").replace(/\[stiker:[^\]]*\]/g, "").trim();
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

  // ===== Misc =====
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

  async function refreshMemories() {
    try {
      const { memories } = await listMemFn({ data: { userId } });
      setMemories(memories);
    } catch (e) { toast.error(e instanceof Error ? e.message : "Gagal memuat memori"); }
  }

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

  async function loginGoogle() {
    try {
      const result = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
      if (result.error) toast.error("Login gagal: " + (result.error.message ?? "unknown"));
    } catch (e) { toast.error(e instanceof Error ? e.message : "Login gagal"); }
  }

  async function logout() {
    await supabase.auth.signOut();
    // Wipe ALL furina:* keys from this browser → guest comes back blank
    clearAllFurinaLocal();
    // Reset state to defaults
    setAuthUser(null);
    setBg(furinaDefault); setName("Furina"); setPersona(""); setLanguage("auto");
    setSpeed(1.0); setProvider("voicevox"); setVvSpeaker(VV_SPEAKERS[0].id);
    setVvTranslate(true); setPreGenAudio(true); setTheme("dark");
    setHasCloneSample(false); setCloneSampleName("");
    setMemories([]);
    const fresh = [newConversation()];
    setConversations(fresh);
    setActiveId(fresh[0].id);
    lastSyncedAuthIdRef.current = null;
    toast.success("Sudah logout. Mode guest mulai bersih.");
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
            <span className={`h-2 w-2 rounded-full ${syncing ? "bg-amber-400 animate-pulse" : "bg-emerald-400"} shadow-[0_0_8px_rgba(52,211,153,0.8)]`} />
            <span className="truncate">{name}</span>
            <span
              title={`Mood: ${mood.label} (${mood.score})`}
              className={`h-1.5 w-1.5 rounded-full ${
                mood.score >= 60 ? "bg-pink-400" :
                mood.score >= 25 ? "bg-yellow-300" :
                mood.score > -20 ? "bg-sky-300" :
                mood.score > -55 ? "bg-orange-400" : "bg-red-400"
              }`}
            />
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
                <SheetDescription>{authUser ? "Tersinkron ke akunmu." : "Mode guest — login untuk simpan ke cloud."}</SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-2">
                <Button onClick={startNewConversation} className="w-full">
                  <Plus className="mr-2 h-4 w-4" /> Percakapan baru
                </Button>
                <div className="mt-3 space-y-3">
                  {(() => {
                    const now = Date.now();
                    const startOfDay = new Date(); startOfDay.setHours(0,0,0,0);
                    const todayStart = startOfDay.getTime();
                    const yesterdayStart = todayStart - 86400000;
                    const weekStart = todayStart - 6 * 86400000;
                    const monthStart = todayStart - 29 * 86400000;
                    const sorted = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);
                    const buckets: { label: string; items: Conversation[] }[] = [
                      { label: "Hari ini", items: [] },
                      { label: "Kemarin", items: [] },
                      { label: "7 hari terakhir", items: [] },
                      { label: "30 hari terakhir", items: [] },
                      { label: "Lebih lama", items: [] },
                    ];
                    for (const c of sorted) {
                      if (c.updatedAt >= todayStart) buckets[0].items.push(c);
                      else if (c.updatedAt >= yesterdayStart) buckets[1].items.push(c);
                      else if (c.updatedAt >= weekStart) buckets[2].items.push(c);
                      else if (c.updatedAt >= monthStart) buckets[3].items.push(c);
                      else buckets[4].items.push(c);
                    }
                    return buckets.filter((b) => b.items.length).map((bucket) => (
                      <div key={bucket.label}>
                        <div className="mb-1 px-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          {bucket.label}
                        </div>
                        <div className="space-y-1">
                          {bucket.items.map((c) => {
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
                                    <span className="text-[10px] text-muted-foreground">{relTime(c.updatedAt, now)}</span>
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
                    ));
                  })()}
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

              <Tabs defaultValue="persona" className="mt-4 w-full">
                <TabsList className="grid w-full grid-cols-5 h-9">
                  <TabsTrigger value="persona" className="text-[11px] px-1">Persona</TabsTrigger>
                  <TabsTrigger value="memori" className="text-[11px] px-1">Memori</TabsTrigger>
                  <TabsTrigger value="suara" className="text-[11px] px-1">Suara</TabsTrigger>
                  <TabsTrigger value="proaktif" className="text-[11px] px-1">Proaktif</TabsTrigger>
                  <TabsTrigger value="akun" className="text-[11px] px-1">Akun</TabsTrigger>
                </TabsList>

                {/* PERSONA TAB */}
                <TabsContent value="persona" className="mt-4 space-y-4">
                  <section className="rounded-lg border bg-muted/30 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold uppercase tracking-wider">Mood saat ini</Label>
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <span className={`h-2 w-2 rounded-full ${
                          mood.score >= 60 ? "bg-pink-400" :
                          mood.score >= 25 ? "bg-yellow-300" :
                          mood.score > -20 ? "bg-sky-300" :
                          mood.score > -55 ? "bg-orange-400" : "bg-red-400"
                        }`} />
                        <span className="font-medium capitalize">{mood.label}</span>
                        <span className="tabular-nums text-muted-foreground">({mood.score > 0 ? "+" : ""}{mood.score})</span>
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-relaxed">
                      Berubah otomatis dari cara kamu ngobrol. Manis → naik, kasar/cuek → turun, netral → luruh sendiri.
                    </p>
                  </section>

                  <section className="space-y-2">
                    <Label>Nama karakter</Label>
                    <Input value={name} onChange={(e) => { setName(e.target.value); savePref(STORAGE.name, e.target.value); }} />
                  </section>

                  <section className="space-y-2">
                    <Label>Kepribadian / system prompt (opsional)</Label>
                    <Textarea rows={6} placeholder="Kosongkan untuk kepribadian Furina default…"
                      value={persona}
                      onChange={(e) => { setPersona(e.target.value); savePref(STORAGE.persona, e.target.value); }} />
                    <p className="text-[10px] text-muted-foreground">Kalau kosong, Furina pakai kepribadian default (dramatis, tsundere halus, ekspresif terkendali).</p>
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

                  <section className="rounded-lg border bg-muted/30 p-3 space-y-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider">Tema</Label>
                    <Button size="sm" variant="outline" onClick={toggleTheme} className="w-full">
                      {theme === "dark" ? <><Sun className="mr-2 h-4 w-4" />Ganti ke Terang</> : <><Moon className="mr-2 h-4 w-4" />Ganti ke Gelap</>}
                    </Button>
                  </section>
                </TabsContent>

                {/* MEMORI TAB */}
                <TabsContent value="memori" className="mt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Memori (lintas-percakapan)</Label>
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={async () => {
                        toast.info("Meringkas memori lama…");
                        try {
                          const r = await compactMemFn({ data: { userId, threshold: 20, batch: 15, force: true } }) as { ok: boolean; reason?: string; compacted?: number };
                          if (r.ok) { toast.success(`${r.compacted} memori diringkas.`); refreshMemories(); }
                          else toast.info(r.reason === "below-threshold" ? "Belum banyak memori untuk diringkas." : "Tidak ada yang diringkas.");
                        } catch (e) { toast.error(e instanceof Error ? e.message : "Gagal"); }
                      }}>Ringkas</Button>
                      <Button variant="ghost" size="sm" onClick={async () => {
                        if (!confirm("Hapus semua memori?")) return;
                        await clearMemFn({ data: { userId } });
                        refreshMemories();
                        toast.success("Memori dibersihkan");
                      }}>Hapus semua</Button>
                    </div>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Fakta tentang kamu (otomatis dipelajari) + ringkasan percakapan lama. Memori lama otomatis diringkas biar hemat.
                  </p>
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

                  <div className="flex flex-wrap gap-1">
                    {[
                      { id: "all", label: "Semua" },
                      { id: "fact", label: "Fakta" },
                      { id: "episodic", label: "Kejadian" },
                      { id: "preference", label: "Preferensi" },
                      { id: "relation", label: "Relasi" },
                      { id: "style", label: "Gaya" },
                      { id: "summary", label: "Ringkasan" },
                    ].map((f) => (
                      <button
                        key={f.id}
                        onClick={() => setMemFilter(f.id)}
                        className={`rounded-full border px-2 py-0.5 text-[10px] transition ${
                          memFilter === f.id ? "border-primary bg-primary/15 text-primary" : "border-border text-muted-foreground hover:bg-muted"
                        }`}
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                  <Input placeholder="Cari memori…" value={memSearch} onChange={(e) => setMemSearch(e.target.value)} className="h-8 text-xs" />

                  <div className="max-h-[50vh] space-y-1 overflow-y-auto rounded-md border p-2 text-sm">
                    {(() => {
                      const q = memSearch.trim().toLowerCase();
                      const filtered = memories.filter((m) => {
                        if (memFilter !== "all" && (m.kind ?? "fact") !== memFilter) return false;
                        if (q && !m.content.toLowerCase().includes(q)) return false;
                        return true;
                      });
                      if (filtered.length === 0) return <p className="text-muted-foreground">Tidak ada memori cocok.</p>;
                      const kindColor: Record<string, string> = {
                        fact: "bg-muted",
                        episodic: "bg-blue-500/20 text-blue-600 dark:text-blue-300",
                        preference: "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300",
                        relation: "bg-purple-500/20 text-purple-600 dark:text-purple-300",
                        style: "bg-accent/40",
                        summary: "bg-primary/20",
                        meta_summary: "bg-primary/20",
                      };
                      return filtered.map((m) => {
                        const isEditing = editingMemId === m.id;
                        const kind = m.kind ?? "fact";
                        return (
                          <div key={m.id} className="rounded p-1.5 hover:bg-muted/60">
                            {isEditing ? (
                              <div className="space-y-2">
                                <Textarea
                                  value={editingMemContent}
                                  onChange={(e) => setEditingMemContent(e.target.value)}
                                  rows={3}
                                  className="text-sm"
                                />
                                <div className="flex items-center gap-2">
                                  <Label className="text-[10px] text-muted-foreground">Penting</Label>
                                  <Slider
                                    value={[editingMemImportance]}
                                    min={1} max={10} step={1}
                                    onValueChange={(v) => setEditingMemImportance(v[0] ?? 5)}
                                    className="flex-1"
                                  />
                                  <span className="w-6 text-right text-[11px] font-medium">{editingMemImportance}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Label className="text-[10px] text-muted-foreground">Tanggal</Label>
                                  <Input
                                    type="date"
                                    value={editingMemOccurred}
                                    onChange={(e) => setEditingMemOccurred(e.target.value)}
                                    className="h-7 flex-1 text-xs"
                                  />
                                  {editingMemOccurred && (
                                    <button onClick={() => setEditingMemOccurred("")} className="text-[10px] text-muted-foreground hover:text-destructive">×</button>
                                  )}
                                </div>
                                <div className="flex justify-end gap-2">
                                  <Button size="sm" variant="ghost" onClick={() => setEditingMemId(null)}>Batal</Button>
                                  <Button size="sm" onClick={async () => {
                                    if (editingMemContent.trim().length < 3) return;
                                    try {
                                      await updateMemFn({ data: {
                                        id: m.id, userId,
                                        content: editingMemContent.trim(),
                                        importance: editingMemImportance,
                                        occurred_at: editingMemOccurred || null,
                                      }});
                                      setEditingMemId(null);
                                      refreshMemories();
                                      toast.success("Memori diperbarui");
                                    } catch (e) { toast.error(e instanceof Error ? e.message : "Gagal simpan"); }
                                  }}>Simpan</Button>
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-start gap-2">
                                <span className={`mt-0.5 shrink-0 rounded px-1 text-[9px] font-semibold uppercase ${kindColor[kind] ?? "bg-muted"}`}>
                                  {kind}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <p className="break-words">{m.content}</p>
                                  {(m.occurred_at || m.emotion) && (
                                    <p className="mt-0.5 text-[10px] text-muted-foreground">
                                      {m.occurred_at && <>📅 {new Date(m.occurred_at).toLocaleDateString("id-ID")}</>}
                                      {m.occurred_at && m.emotion && " · "}
                                      {m.emotion && <>💭 {m.emotion}</>}
                                    </p>
                                  )}
                                </div>
                                <span className="mt-0.5 rounded bg-muted px-1 text-[9px] text-muted-foreground" title="Importance">
                                  {m.importance ?? 5}
                                </span>
                                <button
                                  onClick={() => {
                                    setEditingMemId(m.id);
                                    setEditingMemContent(m.content);
                                    setEditingMemImportance(m.importance ?? 5);
                                    setEditingMemOccurred(m.occurred_at ? m.occurred_at.slice(0, 10) : "");
                                  }}
                                  className="text-muted-foreground hover:text-primary"
                                  title="Edit"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  onClick={async () => { await delMemFn({ data: { id: m.id, userId } }); refreshMemories(); }}
                                  className="text-muted-foreground hover:text-destructive"
                                  title="Hapus"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      });
                    })()}
                  </div>
                  <p className="text-[10px] text-muted-foreground">{memories.length} memori tersimpan.</p>
                </TabsContent>

                {/* SUARA TAB */}
                <TabsContent value="suara" className="mt-4 space-y-3">
                  <Label>Mesin suara (TTS)</Label>
                  <Select value={provider} onValueChange={(v) => { setProvider(v as TTSProvider); savePref(STORAGE.provider, v); }}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="voicevox">VOICEVOX — anime Jepang (gratis, stabil)</SelectItem>
                      <SelectItem value="clone">Voice Clone — suara karakter custom (XTTS Space)</SelectItem>
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
                    </div>
                  ) : (
                    <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                      <Label className="text-xs font-semibold flex items-center gap-1">
                        <Sparkles className="h-3 w-3" /> Sampel suara karakter
                      </Label>
                      <p className="text-[10px] leading-relaxed text-muted-foreground">
                        Upload 1 file audio (mp3/wav, 6–15 detik, jernih, satu suara, tanpa musik). Clone via Coqui XTTS HF Space — gratis tanpa API key, kadang antri ~30 detik.
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
                </TabsContent>

                {/* PROAKTIF TAB */}
                <TabsContent value="proaktif" className="mt-4 space-y-4">
                  <section className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Sapa duluan saat kamu balik</Label>
                      <Switch checked={proactiveEnabled} onCheckedChange={setProactiveEnabled} />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      Kalau kamu lama tidak buka chat, Furina bisa nyapa duluan 1 kali saat kamu kembali. Maks sekali per sesi.
                    </p>
                  </section>

                  <section className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Ambang idle (jam)</Label>
                      <span className="text-xs text-muted-foreground tabular-nums">{proactiveIdleHours} jam</span>
                    </div>
                    <Slider min={1} max={48} step={1} value={[proactiveIdleHours]}
                      onValueChange={(v) => setProactiveIdleHours(v[0] ?? 6)} disabled={!proactiveEnabled} />
                    <p className="text-[10px] text-muted-foreground">
                      Furina nyapa duluan kalau kamu tidak chat lebih dari {proactiveIdleHours} jam.
                    </p>
                  </section>
                </TabsContent>

                {/* AKUN TAB */}
                <TabsContent value="akun" className="mt-4 space-y-4">
                  <section className="rounded-lg border bg-muted/30 p-3 space-y-2">
                    <Label className="text-xs font-semibold uppercase tracking-wider">Akun</Label>
                    {authUser ? (
                      <div className="space-y-2">
                        <p className="text-sm">Login sebagai <span className="font-medium">{authUser.email ?? authUser.id}</span></p>
                        <p className="text-[11px] text-muted-foreground">
                          ✓ Semua chat, kepribadian, dan pengaturan tersimpan otomatis ke akunmu.
                        </p>
                        <Button variant="outline" size="sm" className="w-full" onClick={logout}>
                          <LogOut className="mr-2 h-4 w-4" /> Logout (kembali ke guest kosong)
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <p className="text-xs text-muted-foreground">
                          Mode guest. Login pertama kali → data guest dipindahkan otomatis ke akun. Login berikutnya → memuat data akunmu.
                        </p>
                        <Button size="sm" className="w-full" onClick={loginGoogle}>
                          <LogIn className="mr-2 h-4 w-4" /> Masuk dengan Google
                        </Button>
                      </div>
                    )}
                  </section>

                  <Separator />

                  <Button variant="outline" className="w-full" onClick={clearChat}>
                    <Trash2 className="mr-2 h-4 w-4" /> Bersihkan percakapan ini
                  </Button>
                </TabsContent>
              </Tabs>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      {/* Chat messages */}
      <main ref={scrollRef} className="absolute inset-0 z-10 overflow-y-auto px-3 pt-20 pb-36 sm:px-4">
        <div className="mx-auto flex min-h-full max-w-3xl flex-col gap-3">
        {messages.length === 0 && (
          <div className="mt-auto mb-4 w-fit max-w-[min(92%,640px)] self-start animate-fade-in">
            <div className="bubble-ai rounded-2xl px-4 py-3 text-sm shadow-lg">
              Halo… akhirnya kamu datang juga~ ✦ Aku {name}. Ceritakan apa saja.
            </div>
            <div className="mt-1 px-1 text-[10px] opacity-70">baru saja</div>
          </div>
        )}
        <div className="mt-auto" />
        {messages.map((m) => {
          const isUser = m.role === "user";
          const isPlaying = playingId === m.id;
          const isLoading = loadingId === m.id;
          return (
            <div key={m.id} className={`flex w-full flex-col animate-fade-in ${isUser ? "items-end" : "items-start"}`}>
              <div className={`${isUser ? "bubble-user" : "bubble-ai"} w-fit max-w-[min(92%,640px)] rounded-2xl px-4 py-2.5 text-sm shadow-lg`}>
                {m.imageDataUrl && (
                  <button
                    type="button"
                    onClick={() => setLightboxUrl(m.imageDataUrl!)}
                    className="mb-2 block w-full overflow-hidden rounded-lg"
                    aria-label="Buka gambar"
                  >
                    <img
                      src={m.imageDataUrl}
                      alt="lampiran"
                      className="max-h-64 w-full cursor-zoom-in rounded-lg object-cover transition hover:opacity-90"
                      loading="lazy"
                    />
                  </button>
                )}
                {m.content && <div className="whitespace-pre-wrap break-words leading-relaxed">{m.content}</div>}
              </div>

              <div className="mt-1 flex items-center gap-1.5 px-1">
                <span className="text-[10px] opacity-70 tabular-nums" title={new Date(m.at).toLocaleString()}>{fmtTime(m.at)}</span>

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
          <div className="w-fit max-w-[min(92%,640px)] self-start bubble-ai rounded-2xl px-4 py-2.5 text-sm shadow-lg">
            <span className="inline-flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.3s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50 [animation-delay:-0.15s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/50" />
            </span>
          </div>
        )}
        </div>
      </main>


      {/* Composer */}
      <div className="composer-glass absolute bottom-0 left-0 right-0 z-20 p-3">
        <div className="mx-auto max-w-3xl">
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

      {/* Image lightbox */}
      <Dialog open={!!lightboxUrl} onOpenChange={(o) => { if (!o) setLightboxUrl(null); }}>
        <DialogContent className="max-w-[96vw] border-0 bg-black/90 p-2 sm:max-w-[90vw]">
          {lightboxUrl && (
            <div className="relative flex items-center justify-center">
              <img
                src={lightboxUrl}
                alt="Lampiran ukuran penuh"
                className="max-h-[85vh] w-auto max-w-full rounded object-contain"
              />
              <a
                href={lightboxUrl}
                download
                className="absolute bottom-2 right-2 inline-flex items-center gap-1 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-black shadow hover:bg-white"
              >
                <Download className="h-3 w-3" /> Unduh
              </a>
            </div>
          )}
        </DialogContent>
      </Dialog>
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
