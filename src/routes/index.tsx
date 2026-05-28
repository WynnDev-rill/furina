import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useEffect, useRef, useState } from "react";
import { Send, Settings, Trash2, Plus, Volume2, VolumeX, Image as ImageIcon, RotateCcw, Play, Pause, Square } from "lucide-react";
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
  listMemories,
  deleteMemory,
  addMemory,
  clearAllMemories,
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

const STORAGE = {
  msgs: "furina:messages",
  bg: "furina:bg",
  voice: "furina:voiceId",
  name: "furina:name",
  persona: "furina:persona",
  lang: "furina:lang",
  tts: "furina:ttsEnabled",
};

const VOICES = [
  { id: "XrExE9yKIg1WjnnlVkGX", label: "Matilda — sweet, soft" },
  { id: "EXAVITQu4vr4xnSDxMaL", label: "Sarah — warm feminine" },
  { id: "Xb7hH8MSUJpSbSDYk0k2", label: "Alice — bright young" },
  { id: "cgSgspJ2msm6clMCkdW9", label: "Jessica — gentle" },
  { id: "pFZP5JQG7iQjIQuC4Bku", label: "Lily — soft anime-like" },
  { id: "FGY2WhTYpPnrIDTdsKH5", label: "Laura — clear feminine" },
];

function FurinaApp() {
  const chat = useServerFn(chatWithFurina);
  const tts = useServerFn(speakFurina);
  const listMemFn = useServerFn(listMemories);
  const delMemFn = useServerFn(deleteMemory);
  const addMemFn = useServerFn(addMemory);
  const clearMemFn = useServerFn(clearAllMemories);

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [bg, setBg] = useState<string>(furinaDefault);
  const [voiceId, setVoiceId] = useState(VOICES[0].id);
  const [name, setName] = useState("Furina");
  const [persona, setPersona] = useState("");
  const [language, setLanguage] = useState<"auto" | "ja" | "en" | "id">("auto");
  const [ttsOn, setTtsOn] = useState(true);
  const [openSettings, setOpenSettings] = useState(false);
  const [memories, setMemories] = useState<{ id: string; content: string }[]>([]);
  const [newMem, setNewMem] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Load persisted state
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const m = localStorage.getItem(STORAGE.msgs);
      if (m) setMessages(JSON.parse(m));
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
    } catch {}
  }, []);

  useEffect(() => {
    try { localStorage.setItem(STORAGE.msgs, JSON.stringify(messages)); } catch {}
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    const userMsg: Msg = { id: crypto.randomUUID(), role: "user", content: text, at: Date.now() };
    const next = [...messages, userMsg];
    setMessages(next);
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
      setMessages((prev) => [...prev, aiMsg]);
      if (ttsOn) playTTS(reply);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      toast.error(msg);
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  async function playTTS(text: string) {
    try {
      const clean = text.replace(/\*[^*]+\*/g, "").trim();
      if (!clean) return;
      const { audio } = await tts({ data: { text: clean.slice(0, 1500), voiceId, language } });
      if (audioRef.current) {
        audioRef.current.pause();
      }
      const a = new Audio(`data:audio/mpeg;base64,${audio}`);
      audioRef.current = a;
      await a.play();
    } catch (e) {
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
    setMessages([]);
    try { localStorage.removeItem(STORAGE.msgs); } catch {}
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
        <div className="rounded-full bg-black/30 px-4 py-1.5 text-sm font-medium text-white backdrop-blur-md">
          {name}
        </div>
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

              <section className="space-y-2">
                <Label>Suara (ElevenLabs)</Label>
                <Select value={voiceId} onValueChange={(v) => { setVoiceId(v); savePref(STORAGE.voice, v); }}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {VOICES.map((v) => <SelectItem key={v.id} value={v.id}>{v.label}</SelectItem>)}
                  </SelectContent>
                </Select>
                <div className="flex items-center justify-between pt-2">
                  <Label className="flex items-center gap-2">{ttsOn ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />} TTS otomatis</Label>
                  <Switch checked={ttsOn} onCheckedChange={(c) => { setTtsOn(c); savePref(STORAGE.tts, c ? "1" : "0"); }} />
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
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.role === "user"
                ? "max-w-[85%] self-end rounded-2xl bg-[oklch(0.55_0.18_265)] px-4 py-2.5 text-sm text-white shadow-lg"
                : "max-w-[85%] self-start rounded-2xl bg-white/95 px-4 py-2.5 text-sm text-foreground shadow-lg backdrop-blur"
            }
          >
            {m.content}
          </div>
        ))}
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
