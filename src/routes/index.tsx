import { createFileRoute } from "@tanstack/react-router";
import { useServerFn } from "@tanstack/react-start";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Send, Settings as SettingsIcon, Volume2, Pause, MessageSquarePlus, MessagesSquare,
  Trash2, Pencil, LogOut, Check, CheckCheck, AlertCircle, RotateCw, Loader2, X, Users, Heart,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Label } from "@/components/ui/label";
import { Toaster, toast } from "sonner";
import { cn } from "@/lib/utils";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";
import { CHARACTERS, VV_SPEAKERS, characterList, type CharacterId } from "@/lib/characters";
import {
  chatWithCharacter, speakVoicevox,
  listConversations, createConversation, renameConversation, deleteConversation,
  listMessages, saveMessage,
} from "@/lib/furina.functions";
import { getCachedAudio, setCachedAudio, base64ToBlob } from "@/lib/audio-cache";

export const Route = createFileRoute("/")({
  component: AppPage,
  head: () => ({ meta: [{ title: "Furina & Hu Tao — AI Companion" }] }),
});

interface Msg {
  id: string;            // db id or local pending id
  role: "user" | "assistant";
  content: string;
  status: "sending" | "sent" | "delivered" | "read" | "failed";
  created_at: string;
}
interface Conv { id: string; title: string; updated_at: string }

const LS = {
  charId: "furina:character",
  romantic: (c: string) => `furina:romantic:${c}`,
  voice: (c: string) => `furina:voice:${c}`,
  speed: "furina:speed",
  translate: "furina:translate",
  activeConv: (c: string) => `furina:activeConv:${c}`,
};

function AppPage() {
  const [session, setSession] = useState<Awaited<ReturnType<typeof supabase.auth.getSession>>["data"]["session"]>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setAuthLoading(false); });
    return () => subscription.unsubscribe();
  }, []);

  if (authLoading) return <FullScreen><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></FullScreen>;
  if (!session) return <LoginScreen />;
  return <ChatApp />;
}

function FullScreen({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen flex items-center justify-center bg-background">{children}</div>;
}

function LoginScreen() {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");

  const handleGoogle = async () => {
    setLoading(true);
    const r = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
    if (r.error) { toast.error("Login Google gagal: " + (r.error as Error).message); setLoading(false); }
  };

  const handleEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin } });
        if (error) throw error;
        toast.success("Akun dibuat. Silakan login.");
        setMode("login");
      }
    } catch (err) {
      toast.error((err as Error).message);
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-indigo-950 to-rose-950 p-4">
      <Toaster richColors position="top-center" />
      <div className="w-full max-w-sm rounded-2xl bg-background/90 backdrop-blur p-6 shadow-2xl border border-border">
        <div className="flex flex-col items-center gap-3 mb-5">
          <div className="flex -space-x-3">
            <Avatar className="h-14 w-14 ring-2 ring-cyan-400"><AvatarImage src={CHARACTERS.furina.avatar} /><AvatarFallback>F</AvatarFallback></Avatar>
            <Avatar className="h-14 w-14 ring-2 ring-rose-400"><AvatarImage src={CHARACTERS.hutao.avatar} /><AvatarFallback>H</AvatarFallback></Avatar>
          </div>
          <h1 className="text-xl font-bold">Selamat datang</h1>
          <p className="text-xs text-muted-foreground text-center">Ngobrol dengan Furina & Hu Tao. Data tersimpan di akunmu.</p>
        </div>

        <Button onClick={handleGoogle} disabled={loading} className="w-full mb-3 bg-white text-black hover:bg-white/90">
          <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
          Lanjut dengan Google
        </Button>

        <div className="flex items-center gap-3 my-4"><div className="h-px bg-border flex-1" /><span className="text-xs text-muted-foreground">atau email</span><div className="h-px bg-border flex-1" /></div>

        <form onSubmit={handleEmail} className="space-y-2">
          <Input type="email" placeholder="email@kamu.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input type="password" placeholder="password (min 6)" value={password} onChange={(e) => setPassword(e.target.value)} minLength={6} required />
          <Button type="submit" disabled={loading} className="w-full">{mode === "login" ? "Login" : "Daftar"}</Button>
        </form>
        <button onClick={() => setMode(mode === "login" ? "signup" : "login")} className="w-full text-xs text-muted-foreground mt-3 hover:text-foreground">
          {mode === "login" ? "Belum punya akun? Daftar" : "Sudah punya akun? Login"}
        </button>
      </div>
    </div>
  );
}

function ChatApp() {
  // character selection
  const [charId, setCharId] = useState<CharacterId>(() => (typeof localStorage !== "undefined" ? (localStorage.getItem(LS.charId) as CharacterId) : null) || "furina");
  const character = CHARACTERS[charId];

  const [romantic, setRomantic] = useState<boolean>(() => typeof localStorage !== "undefined" ? localStorage.getItem(LS.romantic(charId)) === "1" : false);
  const [voiceId, setVoiceId] = useState<string>(() => typeof localStorage !== "undefined" ? localStorage.getItem(LS.voice(charId)) || character.recommendedVoice.id : character.recommendedVoice.id);
  const [speed, setSpeed] = useState<number>(() => Number(typeof localStorage !== "undefined" ? localStorage.getItem(LS.speed) : null) || 1.0);
  const [translate, setTranslate] = useState<boolean>(() => typeof localStorage !== "undefined" ? localStorage.getItem(LS.translate) !== "0" : true);

  // when char changes, load that char's settings
  useEffect(() => {
    localStorage.setItem(LS.charId, charId);
    setRomantic(localStorage.getItem(LS.romantic(charId)) === "1");
    setVoiceId(localStorage.getItem(LS.voice(charId)) || character.recommendedVoice.id);
  }, [charId, character.recommendedVoice.id]);

  useEffect(() => { localStorage.setItem(LS.romantic(charId), romantic ? "1" : "0"); }, [romantic, charId]);
  useEffect(() => { localStorage.setItem(LS.voice(charId), voiceId); }, [voiceId, charId]);
  useEffect(() => { localStorage.setItem(LS.speed, String(speed)); }, [speed]);
  useEffect(() => { localStorage.setItem(LS.translate, translate ? "1" : "0"); }, [translate]);

  // conversations & messages
  const [convs, setConvs] = useState<Conv[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const listConvsFn = useServerFn(listConversations);
  const createConvFn = useServerFn(createConversation);
  const renameConvFn = useServerFn(renameConversation);
  const deleteConvFn = useServerFn(deleteConversation);
  const listMsgsFn = useServerFn(listMessages);
  const saveMsgFn = useServerFn(saveMessage);
  const chatFn = useServerFn(chatWithCharacter);
  const speakFn = useServerFn(speakVoicevox);

  // load conversations when character changes
  const loadConvs = useCallback(async () => {
    const r = await listConvsFn({ data: { characterId: charId } });
    setConvs(r.conversations);
    const stored = localStorage.getItem(LS.activeConv(charId));
    const next = (stored && r.conversations.find((c) => c.id === stored)?.id) || r.conversations[0]?.id || null;
    setActiveConvId(next);
  }, [charId, listConvsFn]);

  useEffect(() => { loadConvs().catch((e) => toast.error("Gagal load: " + e.message)); }, [loadConvs]);

  // load messages when conv changes
  useEffect(() => {
    if (!activeConvId) { setMsgs([]); return; }
    localStorage.setItem(LS.activeConv(charId), activeConvId);
    listMsgsFn({ data: { conversationId: activeConvId } })
      .then((r) => setMsgs(r.messages as Msg[]))
      .catch((e) => toast.error("Gagal muat pesan: " + e.message));
  }, [activeConvId, charId, listMsgsFn]);

  const scrollerRef = useRef<HTMLDivElement>(null);
  useEffect(() => { scrollerRef.current?.scrollTo({ top: scrollerRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, sending]);

  const ensureConv = async (): Promise<string> => {
    if (activeConvId) return activeConvId;
    const r = await createConvFn({ data: { characterId: charId, title: "Percakapan baru" } });
    setConvs((c) => [r.conversation as Conv, ...c]);
    setActiveConvId(r.conversation.id);
    return r.conversation.id;
  };

  const sendMessage = async (textOverride?: string, retryMsgId?: string) => {
    const text = (textOverride ?? input).trim();
    if (!text || sending) return;
    setSending(true);
    setInput("");

    const convId = await ensureConv();

    // Optimistic user message
    const localId = retryMsgId || `local-${Date.now()}`;
    const userMsg: Msg = {
      id: localId, role: "user", content: text, status: "sending", created_at: new Date().toISOString(),
    };
    setMsgs((m) => retryMsgId ? m.map((x) => x.id === retryMsgId ? userMsg : x) : [...m, userMsg]);

    try {
      // Save user message
      const saved = await saveMsgFn({ data: { conversationId: convId, role: "user", content: text, status: "sent" } });
      setMsgs((m) => m.map((x) => x.id === localId ? { ...(saved.message as Msg), status: "sent" } : x));

      // Auto-title from first message
      if (msgs.length === 0) {
        const title = text.slice(0, 40);
        renameConvFn({ data: { id: convId, title } }).catch(() => {});
        setConvs((c) => c.map((cc) => cc.id === convId ? { ...cc, title } : cc));
      }

      // Build context for AI
      const persona = romantic ? character.personaRomantic : character.persona;
      const history = [...msgs, { role: "user" as const, content: text, id: "", status: "sent" as const, created_at: "" }]
        .map((m) => ({ role: m.role, content: m.content }));

      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Jakarta";
      const r = await chatFn({ data: { messages: history, characterId: charId, persona, romantic, userTimezone: tz } });

      // Mark user msg as "read" (blue ticks)
      setMsgs((m) => m.map((x) => x.id === (saved.message as Msg).id ? { ...x, status: "read" } : x));

      const aiSaved = await saveMsgFn({ data: { conversationId: convId, role: "assistant", content: r.reply, status: "sent" } });
      setMsgs((m) => [...m, aiSaved.message as Msg]);

      // refresh conv list ordering
      setConvs((cs) => {
        const idx = cs.findIndex((c) => c.id === convId);
        if (idx < 0) return cs;
        const updated = { ...cs[idx], updated_at: new Date().toISOString() };
        return [updated, ...cs.filter((c) => c.id !== convId)];
      });
    } catch (err) {
      setMsgs((m) => m.map((x) => x.id === localId ? { ...x, status: "failed" } : x));
      toast.error("Pesan gagal: " + (err as Error).message);
    } finally {
      setSending(false);
    }
  };

  // ============ TTS ============
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingTtsId, setLoadingTtsId] = useState<string | null>(null);

  const stopAudio = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    setPlayingId(null);
  };

  const playMessage = async (msg: Msg) => {
    if (playingId === msg.id) { stopAudio(); return; }
    stopAudio();

    const voice = resolveVoice(voiceId, character);
    if (!voice || voice.isOriginal) {
      toast.info("Suara original belum tersedia untuk karakter ini.");
      return;
    }

    const cacheKey = `${msg.id}:${voice.id}:${speed}:${translate ? 1 : 0}`;
    let blob = await getCachedAudio(cacheKey);

    if (!blob) {
      setLoadingTtsId(msg.id);
      try {
        const r = await speakFn({ data: { text: msg.content, speaker: voice.speaker!, speed, translateToJa: translate } });
        blob = base64ToBlob(r.audio);
        await setCachedAudio(cacheKey, blob);
      } catch (e) {
        toast.error("TTS gagal: " + (e as Error).message);
        setLoadingTtsId(null);
        return;
      }
      setLoadingTtsId(null);
    }

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.playbackRate = 1.0;
    audio.onended = () => { setPlayingId(null); URL.revokeObjectURL(url); };
    audio.onpause = () => { if (audio.ended) return; };
    audioRef.current = audio;
    setPlayingId(msg.id);
    audio.play().catch((e) => { toast.error("Tidak bisa play: " + e.message); setPlayingId(null); });
  };

  // ============ Conversation actions ============
  const newChat = async () => {
    const r = await createConvFn({ data: { characterId: charId, title: "Percakapan baru" } });
    setConvs((c) => [r.conversation as Conv, ...c]);
    setActiveConvId(r.conversation.id);
    setMsgs([]);
  };
  const deleteChat = async (id: string) => {
    if (!confirm("Hapus percakapan ini?")) return;
    await deleteConvFn({ data: { id } });
    setConvs((c) => c.filter((x) => x.id !== id));
    if (id === activeConvId) {
      const next = convs.find((c) => c.id !== id);
      setActiveConvId(next?.id || null);
    }
  };
  const renameChat = async (id: string, current: string) => {
    const title = prompt("Judul baru:", current);
    if (!title) return;
    await renameConvFn({ data: { id, title } });
    setConvs((c) => c.map((x) => x.id === id ? { ...x, title } : x));
  };

  const logout = async () => { stopAudio(); await supabase.auth.signOut(); };

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <Toaster richColors position="top-center" />

      {/* Header */}
      <header className={cn("border-b border-border bg-gradient-to-r", character.accent)}>
        <div className="max-w-3xl mx-auto px-3 py-2 flex items-center gap-3 backdrop-blur">
          <Select value={charId} onValueChange={(v) => setCharId(v as CharacterId)}>
            <SelectTrigger className="border-0 bg-transparent hover:bg-white/10 w-auto gap-2 p-1 h-auto">
              <div className="flex items-center gap-2">
                <Avatar className="h-9 w-9"><AvatarImage src={character.avatar} /><AvatarFallback>{character.name[0]}</AvatarFallback></Avatar>
                <div className="text-left">
                  <div className="text-sm font-semibold leading-tight">{character.name}</div>
                  <div className="text-[10px] text-muted-foreground leading-tight">{character.tagline}</div>
                </div>
              </div>
            </SelectTrigger>
            <SelectContent>
              {characterList().map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  <div className="flex items-center gap-2">
                    <Avatar className="h-6 w-6"><AvatarImage src={c.avatar} /><AvatarFallback>{c.name[0]}</AvatarFallback></Avatar>
                    <span>{c.name}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex-1" />

          {romantic && <Heart className="h-4 w-4 text-rose-400 fill-rose-400" />}

          <Sheet>
            <SheetTrigger asChild><Button variant="ghost" size="icon" className="h-8 w-8"><MessagesSquare className="h-4 w-4" /></Button></SheetTrigger>
            <SheetContent side="left" className="w-80">
              <SheetHeader><SheetTitle>Percakapan</SheetTitle></SheetHeader>
              <div className="mt-4 space-y-2 overflow-y-auto max-h-[calc(100vh-8rem)]">
                <Button variant="outline" className="w-full justify-start" onClick={newChat}><MessageSquarePlus className="h-4 w-4 mr-2" /> Percakapan baru</Button>
                {convs.map((c) => (
                  <div key={c.id} className={cn("flex items-center gap-1 rounded-md px-2 py-1.5 group", c.id === activeConvId && "bg-accent")}>
                    <button onClick={() => setActiveConvId(c.id)} className="flex-1 text-left text-sm truncate">{c.title}</button>
                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100" onClick={() => renameChat(c.id, c.title)}><Pencil className="h-3 w-3" /></Button>
                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100" onClick={() => deleteChat(c.id)}><Trash2 className="h-3 w-3" /></Button>
                  </div>
                ))}
              </div>
            </SheetContent>
          </Sheet>

          <Sheet>
            <SheetTrigger asChild><Button variant="ghost" size="icon" className="h-8 w-8"><SettingsIcon className="h-4 w-4" /></Button></SheetTrigger>
            <SheetContent side="right" className="w-80 overflow-y-auto">
              <SheetHeader><SheetTitle>Pengaturan</SheetTitle></SheetHeader>
              <div className="mt-4 space-y-5">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2"><Heart className="h-4 w-4 text-rose-400" /> Mode Pasangan</Label>
                    <Switch checked={romantic} onCheckedChange={setRomantic} />
                  </div>
                  <p className="text-xs text-muted-foreground">{character.name} akan lebih mesra & intim, seperti pacar.</p>
                </div>

                <div className="space-y-2">
                  <Label>Voice ({character.name})</Label>
                  <Select value={voiceId} onValueChange={setVoiceId}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectLabel>⭐ Rekomendasi</SelectLabel>
                        <SelectItem value={character.recommendedVoice.id}>{character.recommendedVoice.label}</SelectItem>
                      </SelectGroup>
                      {character.originalVoice && (
                        <SelectGroup>
                          <SelectLabel>🎤 Suara Original</SelectLabel>
                          <SelectItem value="original" disabled>{character.originalVoice.label}</SelectItem>
                        </SelectGroup>
                      )}
                      <SelectGroup>
                        <SelectLabel>VOICEVOX (lain)</SelectLabel>
                        {VV_SPEAKERS.filter((s) => `vv:${s.id}` !== character.recommendedVoice.id).map((s) => (
                          <SelectItem key={s.id} value={`vv:${s.id}`}>{s.name}</SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Kecepatan: {speed.toFixed(2)}x</Label>
                  <Slider min={0.5} max={1.5} step={0.05} value={[speed]} onValueChange={(v) => setSpeed(v[0])} />
                </div>

                <div className="flex items-center justify-between">
                  <Label>Auto-terjemah ke Jepang</Label>
                  <Switch checked={translate} onCheckedChange={setTranslate} />
                </div>

                <Button variant="outline" className="w-full" onClick={logout}><LogOut className="h-4 w-4 mr-2" /> Logout</Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </header>

      {/* Messages */}
      <div ref={scrollerRef} className="flex-1 overflow-y-auto px-3 py-4">
        <div className="max-w-3xl mx-auto space-y-3">
          {msgs.length === 0 && (
            <div className="text-center text-sm text-muted-foreground mt-12">
              Sapa {character.name} duluan 👋
            </div>
          )}
          {msgs.map((m) => (
            <MessageBubble
              key={m.id}
              msg={m}
              character={character}
              isPlaying={playingId === m.id}
              isLoadingTts={loadingTtsId === m.id}
              onPlay={() => playMessage(m)}
              onRetry={() => sendMessage(m.content, m.id)}
            />
          ))}
          {sending && <TypingIndicator character={character} />}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border p-3">
        <form
          onSubmit={(e) => { e.preventDefault(); sendMessage(); }}
          className="max-w-3xl mx-auto flex gap-2"
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
            placeholder={`Pesan untuk ${character.name}...`}
            className="resize-none min-h-[44px] max-h-32"
            rows={1}
            disabled={sending}
          />
          <Button type="submit" disabled={sending || !input.trim()} size="icon" className="h-11 w-11 shrink-0">
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  );
}

function resolveVoice(voiceId: string, character: typeof CHARACTERS["furina"]) {
  if (voiceId === "original") return character.originalVoice;
  if (voiceId === character.recommendedVoice.id) return character.recommendedVoice;
  if (voiceId.startsWith("vv:")) {
    const sp = parseInt(voiceId.slice(3), 10);
    const meta = VV_SPEAKERS.find((s) => s.id === sp);
    return { id: voiceId, label: meta?.name ?? "VOICEVOX", speaker: sp };
  }
  return character.recommendedVoice;
}

function MessageBubble({
  msg, character, isPlaying, isLoadingTts, onPlay, onRetry,
}: {
  msg: Msg; character: typeof CHARACTERS["furina"];
  isPlaying: boolean; isLoadingTts: boolean; onPlay: () => void; onRetry: () => void;
}) {
  const isUser = msg.role === "user";
  const time = msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  return (
    <div className={cn("flex gap-2", isUser ? "justify-end" : "justify-start")}>
      {!isUser && <Avatar className="h-7 w-7 mt-1 shrink-0"><AvatarImage src={character.avatar} /><AvatarFallback>{character.name[0]}</AvatarFallback></Avatar>}
      <div className={cn("max-w-[75%] rounded-2xl px-3 py-2 text-sm",
        isUser ? "bg-primary text-primary-foreground rounded-br-sm" : "bg-muted rounded-bl-sm")}>
        <div className="whitespace-pre-wrap break-words">{msg.content}</div>
        <div className={cn("flex items-center gap-1 mt-1 text-[10px] opacity-70", isUser ? "justify-end" : "justify-start")}>
          {!isUser && (
            <button onClick={onPlay} className="mr-1 inline-flex items-center hover:opacity-100 opacity-80" title="Putar suara">
              {isLoadingTts ? <Loader2 className="h-3 w-3 animate-spin" /> : isPlaying ? <Pause className="h-3 w-3" /> : <Volume2 className="h-3 w-3" />}
            </button>
          )}
          <span>{time}</span>
          {isUser && <StatusTick status={msg.status} onRetry={onRetry} />}
        </div>
      </div>
    </div>
  );
}

function StatusTick({ status, onRetry }: { status: Msg["status"]; onRetry: () => void }) {
  if (status === "failed") {
    return (
      <button onClick={onRetry} className="inline-flex items-center gap-0.5 text-red-400 hover:text-red-300" title="Kirim ulang">
        <AlertCircle className="h-3 w-3" /><RotateCw className="h-3 w-3" />
      </button>
    );
  }
  if (status === "sending") return <Loader2 className="h-3 w-3 animate-spin" />;
  if (status === "sent" || status === "delivered") return <Check className="h-3 w-3" />;
  if (status === "read") return <CheckCheck className="h-3 w-3 text-sky-400 animate-in fade-in zoom-in duration-300" />;
  return null;
}

function TypingIndicator({ character }: { character: typeof CHARACTERS["furina"] }) {
  return (
    <div className="flex gap-2 justify-start">
      <Avatar className="h-7 w-7 mt-1"><AvatarImage src={character.avatar} /><AvatarFallback>{character.name[0]}</AvatarFallback></Avatar>
      <div className="bg-muted rounded-2xl rounded-bl-sm px-3 py-2.5 flex gap-1">
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce" />
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:120ms]" />
        <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-bounce [animation-delay:240ms]" />
      </div>
    </div>
  );
}
