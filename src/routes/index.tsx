import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useEffect, useRef, useState } from "react";
import { Send, Settings, Trash2, Plus, Volume2, VolumeX, Image as ImageIcon, RotateCcw, Play, Pause, Square, Loader2, MessageSquarePlus, MessagesSquare, Check, Pencil } from "lucide-react";
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
import {
  chatWithFurina,
  speakFurina,
  speakVoicevox,
  listMemories,
  deleteMemory,
  addMemory,
  clearAllMemories,
  cloneVoiceFromSamples,
  listElevenLabsVoices,
  deleteElevenLabsVoice,
} from "@/lib/furina.functions";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Furina — AI Companion" },
      { name: "description", content: "Your personal anime AI companion with natural Japanese/English voice, RAG memory, and a customizable Furina character." },
      { property: "og:title", content: "Furina — AI Companion" },
      { property: "og:description", content: "Personal AI companion with voice, memory, and Furina personality." },
    ],
  }),
  component: FurinaApp,
});

type Msg = { id: string; role: "user" | "assistant"; content: string; at: number };
type TTSProvider = "elevenlabs" | "voicevox";
type Conversation = { id: string; title: string; messages: Msg[]; updatedAt: number };

const STORAGE = {
  convos: "furina:conversations",
  activeId: "furina:activeConvoId",
  bg: "furina:bg",
  voice: "furina:voiceId",
  name: "furina:name",
  persona: "furina:persona",
  lang: "furina:lang",
  tts: "furina:ttsEnabled",
  speed: "furina:ttsSpeed",
  provider: "furina:ttsProvider",
  vvSpeaker: "furina:vvSpeaker",
  vvTranslate: "furina:vvTranslate",
  legacyMsgs: "furina:messages",
};

function newConversation(): Conversation {
  return { id: crypto.randomUUID(), title: "Percakapan baru", messages: [], updatedAt: Date.now() };
}



const VOICES = [
  { id: "XrExE9yKIg1WjnnlVkGX", label: "Matilda — sweet, soft" },
  { id: "EXAVITQu4vr4xnSDxMaL", label: "Sarah — warm feminine" },
  { id: "Xb7hH8MSUJpSbSDYk0k2", label: "Alice — bright young" },
  { id: "cgSgspJ2msm6clMCkdW9", label: "Jessica — gentle" },
  { id: "pFZP5JQG7iQjIQuC4Bku", label: "Lily — soft anime-like" },
  { id: "FGY2WhTYpPnrIDTdsKH5", label: "Laura — clear feminine" },
];

// VOICEVOX speakers — 100% gratis, suara anime Jepang natural
const VV_SPEAKERS = [
  { id: 3, label: "ずんだもん (Zundamon) — maskot imut, ceria" },
  { id: 2, label: "四国めたん (Metan) — gadis muda manis" },
  { id: 8, label: "春日部つむぎ (Tsumugi) — cerah, energik" },
  { id: 10, label: "雨晴はう (Hau) — lembut, tenang" },
  { id: 9, label: "波音リツ (Ritsu) — dewasa, kalem" },
  { id: 14, label: "冥鳴ひまり (Himari) — anggun, dramatis" },
  { id: 20, label: "もち子さん (Mochiko) — hangat, kakak" },
  { id: 23, label: "WhiteCUL — manis, polos" },
];

function FurinaApp() {
  const chat = useServerFn(chatWithFurina);
  const tts = useServerFn(speakFurina);
  const ttsVV = useServerFn(speakVoicevox);
  const listMemFn = useServerFn(listMemories);
  const delMemFn = useServerFn(deleteMemory);
  const addMemFn = useServerFn(addMemory);
  const clearMemFn = useServerFn(clearAllMemories);

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [bg, setBg] = useState<string>(furinaDefault);
  const [voiceId, setVoiceId] = useState(VOICES[0].id);
  const [name, setName] = useState("Furina");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState<"auto" | "ja" | "en" | "id">("auto");
  const [ttsOn, setTtsOn] = useState(true);
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
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCache = useRef<Map<string, string>>(new Map());
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const activeConvo = conversations.find((c) => c.id === activeId);
  const messages = activeConvo?.messages ?? [];

  // Load persisted state
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

      const b = localStorage.getItem(STORAGE.bg);
      if (b) setBg(b);
      const v = localStorage.getItem(STORAGE.voice);
      if (v) setVoiceId(v);
      const n = localStorage.getItem(STORAGE.name);
      if (n) setName(n);
      const p = localStorage.getItem(STORAGE.persona);
      if (p) setPersona(p);
      const l = localStorage.getItem(STORAGE.lang);
      if (l) setLanguage(l as typeof language);
      const t = localStorage.getItem(STORAGE.tts);
      if (t) setTtsOn(t === "1");
      const sp = localStorage.getItem(STORAGE.speed);
      if (sp) setSpeed(Math.min(1.2, Math.max(0.7, parseFloat(sp) || 1.0)));
      const pr = localStorage.getItem(STORAGE.provider);
      if (pr === "elevenlabs" || pr === "voicevox") setProvider(pr);
      const vs = localStorage.getItem(STORAGE.vvSpeaker);
      if (vs) setVvSpeaker(parseInt(vs, 10) || VV_SPEAKERS[0].id);
      const vt = localStorage.getItem(STORAGE.vvTranslate);
      if (vt) setVvTranslate(vt === "1");
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

  function updateActiveMessages(updater: (prev: Msg[]) => Msg[]) {
    setConversations((convos) =>
      convos.map((c) =>
        c.id === activeId
          ? { ...c, messages: updater(c.messages), updatedAt: Date.now() }
          : c,
      ),
    );
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


  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    const userMsg: Msg = { id: crypto.randomUUID(), role: "user", content: text, at: Date.now() };
    const next = [...messages, userMsg];
    updateActiveMessages(() => next);
    // Auto-title percakapan baru dari pesan pertama
    if (activeConvo && (activeConvo.title === "Percakapan baru" || !activeConvo.title)) {
      const t = text.slice(0, 40).replace(/\s+/g, " ").trim();
      renameConversation(activeConvo.id, t || "Percakapan baru");
    }
    setInput("");
    setSending(true);
    try {
      const apiMessages = next.slice(-12).map((m) => ({ role: m.role, content: m.content }));
      const { reply } = await chat({
        data: {
          messages: apiMessages,
          characterName: name,
          systemPersona: persona,
          language,
        },
      });
      const aiMsg: Msg = { id: crypto.randomUUID(), role: "assistant", content: reply, at: Date.now() };
      updateActiveMessages((prev) => [...prev, aiMsg]);
      if (ttsOn) playTTS(aiMsg.id, reply);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      toast.error(msg);
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }


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

  async function playTTS(msgId: string, text: string) {
    try {
      const clean = text.replace(/\*[^*]+\*/g, "").trim();
      if (!clean) return;
      stopTTS();
      const cacheKey =
        provider === "voicevox"
          ? `vv:${msgId}:${vvSpeaker}:${speed}:${vvTranslate ? 1 : 0}`
          : `el:${msgId}:${voiceId}:${speed}`;
      let src = audioCache.current.get(cacheKey);
      if (!src) {
        setLoadingId(msgId);
        try {
          if (provider === "voicevox") {
            const { audio } = await ttsVV({
              data: {
                text: clean.slice(0, 1200),
                speaker: vvSpeaker,
                speed,
                translateToJa: vvTranslate,
              },
            });
            src = `data:audio/mpeg;base64,${audio}`;
          } else {
            const { audio } = await tts({
              data: { text: clean.slice(0, 1500), voiceId, language, speed },
            });
            src = `data:audio/mpeg;base64,${audio}`;
          }
          audioCache.current.set(cacheKey, src);
        } finally {
          setLoadingId(null);
        }
      }
      const a = new Audio(src);
      audioRef.current = a;
      setPlayingId(msgId);
      setPaused(false);
      a.onended = () => { setPlayingId(null); setPaused(false); audioRef.current = null; };
      await a.play();
    } catch (e) {
      setLoadingId(null);
      setPlayingId(null);
      setPaused(false);
      const msg = e instanceof Error ? e.message : "Voice failed";
      toast.error(msg);
    }
  }



  function handleBgUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result);
      setBg(url);
      try { localStorage.setItem(STORAGE.bg, url); } catch (err) {
        toast.error("Image too large to save persistently");
      }
    };
    reader.readAsDataURL(file);
  }

  async function refreshMemories() {
    try {
      const { memories } = await listMemFn();
      setMemories(memories);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed loading memories");
    }
  }

  function clearChat() {
    updateActiveMessages(() => []);
  }


  function savePref(key: string, value: string) {
    try { localStorage.setItem(key, value); } catch {}
  }

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-black">
      {/* Background character */}
      <img
        src={bg}
        alt={`${name} background`}
        className="absolute inset-0 h-full w-full object-cover"
        draggable={false}
      />
      {/* Subtle vertical fade for legibility */}
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
          <Button
            size="icon"
            variant="ghost"
            onClick={startNewConversation}
            className="rounded-full bg-black/30 text-white backdrop-blur-md hover:bg-black/50"
            aria-label="Percakapan baru"
            title="Percakapan baru"
          >
            <MessageSquarePlus className="h-5 w-5" />
          </Button>

          <Sheet open={openConvos} onOpenChange={setOpenConvos}>
            <SheetTrigger asChild>
              <Button size="icon" variant="ghost" className="rounded-full bg-black/30 text-white backdrop-blur-md hover:bg-black/50" aria-label="Riwayat percakapan" title="Riwayat percakapan">
                <MessagesSquare className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-full overflow-y-auto sm:max-w-sm">
              <SheetHeader>
                <SheetTitle>Riwayat Percakapan</SheetTitle>
                <SheetDescription>Semua percakapanmu tersimpan lokal di browser.</SheetDescription>
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
                      <div
                        key={c.id}
                        className={`group rounded-lg border p-2 transition ${isActive ? "border-primary bg-accent" : "hover:bg-muted"}`}
                      >
                        {editingTitleId === c.id ? (
                          <div className="flex items-center gap-1">
                            <Input
                              autoFocus
                              value={editingTitleVal}
                              onChange={(e) => setEditingTitleVal(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") { renameConversation(c.id, editingTitleVal); setEditingTitleId(null); }
                                if (e.key === "Escape") setEditingTitleId(null);
                              }}
                              className="h-7 text-sm"
                            />
                            <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => { renameConversation(c.id, editingTitleVal); setEditingTitleId(null); }}>
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
                            <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => { setEditingTitleId(c.id); setEditingTitleVal(c.title); }}>
                              <Pencil className="h-3 w-3" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-6 w-6 text-destructive"
                              onClick={() => { if (confirm("Hapus percakapan ini?")) deleteConversation(c.id); }}
                            >
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
              <SheetDescription>Personalisasi karakter, suara, dan memori.</SheetDescription>
            </SheetHeader>

            <div className="mt-6 space-y-6">
              <section className="space-y-2">
                <Label>Nama karakter</Label>
                <Input value={name} onChange={(e) => { setName(e.target.value); savePref(STORAGE.name, e.target.value); }} />
              </section>

              <section className="space-y-2">
                <Label>Kepribadian / system prompt (opsional)</Label>
                <Textarea
                  rows={5}
                  placeholder="Kosongkan untuk kepribadian Furina default…"
                  value={persona}
                  onChange={(e) => { setPersona(e.target.value); savePref(STORAGE.persona, e.target.value); }}
                />
              </section>

              <section className="space-y-3">
                <Label>Mesin suara (TTS)</Label>
                <Select
                  value={provider}
                  onValueChange={(v) => {
                    setProvider(v as TTSProvider);
                    savePref(STORAGE.provider, v);
                    audioCache.current.clear();
                  }}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="voicevox">VOICEVOX — anime Jepang (gratis)</SelectItem>
                    <SelectItem value="elevenlabs">ElevenLabs — multibahasa (premium)</SelectItem>
                  </SelectContent>
                </Select>

                {provider === "elevenlabs" ? (
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Voice ElevenLabs</Label>
                    <Select value={voiceId} onValueChange={(v) => { setVoiceId(v); savePref(STORAGE.voice, v); audioCache.current.clear(); }}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {VOICES.map((v) => <SelectItem key={v.id} value={v.id}>{v.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">Karakter VOICEVOX (suara anime Jepang)</Label>
                    <Select
                      value={String(vvSpeaker)}
                      onValueChange={(v) => { const n = parseInt(v, 10); setVvSpeaker(n); savePref(STORAGE.vvSpeaker, v); audioCache.current.clear(); }}
                    >
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {VV_SPEAKERS.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <div className="flex items-center justify-between pt-1">
                      <Label className="text-xs">Auto-terjemah balasan ke Jepang</Label>
                      <Switch
                        checked={vvTranslate}
                        onCheckedChange={(c) => { setVvTranslate(c); savePref(STORAGE.vvTranslate, c ? "1" : "0"); audioCache.current.clear(); }}
                      />
                    </div>
                    <p className="text-[11px] leading-relaxed text-muted-foreground">
                      Teks balasan tetap dalam bahasa pilihanmu (mis. Indonesia), tapi suaranya otomatis dibacakan dalam bahasa Jepang ala anime. 100% gratis lewat VOICEVOX.
                    </p>
                  </div>
                )}
                <div className="flex items-center justify-between pt-2">
                  <Label className="flex items-center gap-2">{ttsOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />} TTS otomatis</Label>
                  <Switch checked={ttsOn} onCheckedChange={(c) => { setTtsOn(c); savePref(STORAGE.tts, c ? "1" : "0"); }} />
                </div>
                <div className="pt-2 space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Kecepatan bicara</Label>
                    <span className="text-xs text-muted-foreground tabular-nums">{speed.toFixed(2)}x</span>
                  </div>
                  <Slider
                    min={0.7}
                    max={1.2}
                    step={0.05}
                    value={[speed]}
                    onValueChange={(v) => { const s = v[0] ?? 1; setSpeed(s); savePref(STORAGE.speed, String(s)); audioCache.current.clear(); }}
                  />
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
                  <Label>Memori (RAG)</Label>
                  <Button variant="ghost" size="sm" onClick={async () => {
                    if (!confirm("Hapus semua memori?")) return;
                    await clearMemFn();
                    refreshMemories();
                    toast.success("Memori dibersihkan");
                  }}>Hapus semua</Button>
                </div>
                <div className="flex gap-2">
                  <Input placeholder="Tambah fakta tentang dirimu…" value={newMem} onChange={(e) => setNewMem(e.target.value)} />
                  <Button size="icon" onClick={async () => {
                    if (newMem.trim().length < 3) return;
                    try {
                      await addMemFn({ data: { content: newMem.trim() } });
                      setNewMem("");
                      refreshMemories();
                    } catch (e) { toast.error(e instanceof Error ? e.message : "Failed"); }
                  }}><Plus className="h-4 w-4" /></Button>
                </div>
                <div className="max-h-64 space-y-1 overflow-y-auto rounded-md border p-2 text-sm">
                  {memories.length === 0 && <p className="text-muted-foreground">Belum ada memori. Furina akan otomatis mengingat fakta dari obrolan.</p>}
                  {memories.map((m) => (
                    <div key={m.id} className="flex items-start gap-2 rounded p-1 hover:bg-muted">
                      <span className="flex-1">{m.content}</span>
                      <button onClick={async () => { await delMemFn({ data: { id: m.id } }); refreshMemories(); }} className="text-muted-foreground hover:text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </section>

              <Separator />

              <Button variant="outline" className="w-full" onClick={clearChat}>
                <Trash2 className="mr-2 h-4 w-4" /> Bersihkan percakapan
              </Button>
            </div>
          </SheetContent>
        </Sheet>
        </div>
      </header>


      {/* Chat messages overlay */}
      <main
        ref={scrollRef}
        className="absolute inset-0 z-10 flex flex-col gap-3 overflow-y-auto px-4 pt-20 pb-32"
      >
        {messages.length === 0 && (
          <div className="mt-auto mb-4 max-w-[85%] self-start rounded-2xl bg-white/95 px-4 py-3 text-sm text-foreground shadow-lg backdrop-blur">
            Halo… ara, akhirnya kamu datang juga~ ✦ Aku {name}. Ceritakan apa saja padaku.
          </div>
        )}
        <div className="mt-auto" />
        {messages.map((m) => {
          const isUser = m.role === "user";
          const isPlaying = playingId === m.id;
          const isLoading = loadingId === m.id;
          return (
            <div key={m.id} className={isUser ? "flex max-w-[85%] self-end flex-col items-end" : "flex max-w-[85%] self-start flex-col items-start"}>
              <div
                className={
                  isUser
                    ? "rounded-2xl bg-[oklch(0.55_0.18_265)] px-4 py-2.5 text-sm text-white shadow-lg"
                    : "rounded-2xl bg-white/95 px-4 py-2.5 text-sm text-foreground shadow-lg backdrop-blur"
                }
              >
                {m.content}
              </div>
              {!isUser && (
                <div className="mt-1 flex items-center gap-1 px-1">
                  {isLoading && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-black/50 px-2.5 py-1 text-[11px] text-white backdrop-blur-md animate-pulse">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      Menyiapkan suara…
                      <span className="inline-flex gap-0.5 ml-0.5">
                        <span className="h-1 w-1 animate-bounce rounded-full bg-white/80 [animation-delay:-0.3s]" />
                        <span className="h-1 w-1 animate-bounce rounded-full bg-white/80 [animation-delay:-0.15s]" />
                        <span className="h-1 w-1 animate-bounce rounded-full bg-white/80" />
                      </span>
                    </span>
                  )}
                  {!isLoading && !isPlaying && (
                    <button
                      onClick={() => playTTS(m.id, m.content)}
                      className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md transition hover:bg-black/60"
                      aria-label="Putar suara"
                    >
                      <Play className="h-3 w-3" />
                    </button>
                  )}
                  {!isLoading && isPlaying && !paused && (
                    <button
                      onClick={pauseTTS}
                      className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md transition hover:bg-black/60"
                      aria-label="Jeda"
                    >
                      <Pause className="h-3 w-3" />
                    </button>
                  )}
                  {!isLoading && isPlaying && paused && (
                    <button
                      onClick={resumeTTS}
                      className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md transition hover:bg-black/60"
                      aria-label="Lanjutkan"
                    >
                      <Play className="h-3 w-3" />
                    </button>
                  )}
                  {!isLoading && isPlaying && (
                    <button
                      onClick={stopTTS}
                      className="rounded-full bg-black/40 p-1.5 text-white backdrop-blur-md transition hover:bg-black/60"
                      aria-label="Berhenti"
                    >
                      <Square className="h-3 w-3" />
                    </button>
                  )}
                </div>
              )}
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
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ketik pesan Anda di sini..."
            rows={1}
            className="max-h-32 min-h-[44px] flex-1 resize-none border-0 bg-transparent focus-visible:ring-0"
          />
          <Button onClick={send} disabled={sending || !input.trim()} size="icon" className="h-11 w-11 rounded-full">
            <Send className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
