import { createFileRoute } from "@tanstack/react-router";
import {
  Heart,
  MessageCircle,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { CompanionStage } from "@/components/companion/CompanionStage";
import { InochiCompanionStage } from "@/components/companion/InochiCompanionStage";
import { generateCompanionReply } from "@/lib/companion/ai-horde";
import { COMPANION_NAME } from "@/lib/companion/persona";
import type {
  ChatMessage,
  CompanionContext,
  CompanionEmotion,
  CompanionGaze,
  CompanionGesture,
  RelationshipState,
  TouchRegion,
} from "@/lib/companion/types";
import { speakJapanese, stopJapaneseVoice } from "@/lib/companion/voice";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: `${COMPANION_NAME} — Virtual Companion` },
      {
        name: "description",
        content: "Original Japanese-speaking companion with switchable VRM 3D and Inochi2D character engines, contextual animation, memory, voice, and touch reactions.",
      },
      { name: "theme-color", content: "#100d19" },
    ],
  }),
  component: CompanionApp,
});

type AvatarEngine = "vrm" | "inochi";

const STORAGE = {
  messages: "mirei:final:conversation",
  memories: "mirei:final:memories",
  relationship: "mirei:final:relationship",
  voice: "mirei:final:voice",
  engine: "mirei:final:avatar-engine",
};

const DEFAULT_RELATIONSHIP: RelationshipState = {
  affinity: 18,
  trust: 12,
  annoyance: 0,
  interactionCount: 0,
  touchCount: 0,
};

const initialGreeting: ChatMessage = {
  id: "mirei-greeting",
  role: "assistant",
  content: "やっと来たのね。べ、別に待っていたわけじゃないけど……今日は何を話す？",
  createdAt: Date.now(),
};

const quickPrompts = [
  "今日はどうだった？",
  "少し疲れた。話を聞いて。",
  "私のこと、どう思ってる？",
];

function clamp(value: number, minimum = 0, maximum = 100) {
  return Math.max(minimum, Math.min(maximum, value));
}

function createId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function safeRead<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "null") as T | null;
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}

function normalizeMessages(value: unknown): ChatMessage[] {
  if (!Array.isArray(value)) return [initialGreeting];
  const messages = value
    .filter((item): item is ChatMessage => Boolean(item) && typeof item === "object")
    .map((item) => ({
      id: String(item.id || createId()),
      role: item.role === "assistant" ? "assistant" as const : "user" as const,
      content: String(item.content || "").slice(0, 5000),
      createdAt: Number(item.createdAt) || Date.now(),
    }))
    .filter((item) => item.content.trim())
    .slice(-100);
  return messages.length ? messages : [initialGreeting];
}

function normalizeRelationship(value: Partial<RelationshipState> | null): RelationshipState {
  return {
    affinity: clamp(Number(value?.affinity) || DEFAULT_RELATIONSHIP.affinity),
    trust: clamp(Number(value?.trust) || DEFAULT_RELATIONSHIP.trust),
    annoyance: clamp(Number(value?.annoyance) || 0),
    interactionCount: Math.max(0, Number(value?.interactionCount) || 0),
    touchCount: Math.max(0, Number(value?.touchCount) || 0),
  };
}

function extractMemory(text: string) {
  const cleaned = text.replace(/\s+/g, " ").trim().slice(0, 220);
  if (cleaned.length < 8) return null;
  const patterns = [
    /\b(?:aku|saya)\s+(?:suka|tidak suka|benci|tinggal|punya|memiliki|sedang|ingin|berencana|bekerja|belajar)\b/i,
    /\b(?:nama(?:ku| saya)|hobiku|pekerjaanku|tujuanku|targetku|proyekku)\b/i,
    /(?:私は|僕は|俺は|わたしは|好き|嫌い|住んで|仕事|勉強|目標|趣味)/,
    /\b(?:i am|i like|i dislike|i live|my name|my goal|my project|i work|i study)\b/i,
  ];
  return patterns.some((pattern) => pattern.test(cleaned)) ? cleaned : null;
}

function mergeMemories(current: string[], additions: Array<string | null | undefined>) {
  const next = [...current];
  for (const addition of additions) {
    const cleaned = String(addition || "").replace(/\s+/g, " ").trim().slice(0, 220);
    if (cleaned.length < 4) continue;
    if (!next.some((item) => item.toLowerCase() === cleaned.toLowerCase())) next.push(cleaned);
  }
  return next.slice(-36);
}

function touchReaction(
  region: TouchRegion,
  relationship: RelationshipState,
  repeated: boolean,
): { text: string; emotion: CompanionEmotion; gesture: CompanionGesture; gaze: CompanionGaze; intensity: number } {
  const close = relationship.trust >= 52 || relationship.affinity >= 58;
  if (region === "head") {
    return repeated
      ? { text: "もう……そんなに何度も撫でたら、髪が乱れるでしょう。少しだけなら許すけど。", emotion: "embarrassed", gesture: "shy_hair_touch", gaze: "side", intensity: 0.72 }
      : { text: close ? "ちょっと……急に撫でないで。……でも、今だけならそのままでいい。" : "急に頭を撫でるなんて、距離感がおかしいんじゃない？　嫌とは言ってないけど。", emotion: "embarrassed", gesture: "look_away", gaze: "side", intensity: 0.66 };
  }
  if (region === "face") {
    return { text: "近いわよ。そんなに見つめられたら、さすがに落ち着かないじゃない。", emotion: "embarrassed", gesture: "lean_closer", gaze: "side", intensity: 0.76 };
  }
  if (region === "shoulder") {
    return { text: "何？　ちゃんと聞いているから、そんなに急かさないで。", emotion: "annoyed", gesture: "hands_on_hips", gaze: "user", intensity: 0.48 };
  }
  if (region === "hand") {
    return { text: close ? "手を取りたいなら、最初からそう言えばいいのに。……少しだけよ。" : "手？　仕方ないわね。ほんの少しだけだから、勘違いしないで。", emotion: "playful", gesture: "hand_to_chest", gaze: "user", intensity: 0.62 };
  }
  return repeated
    ? { text: "こら。何度も同じことをしたら、本気で怒るわよ。", emotion: "annoyed", gesture: "crossed_arms", gaze: "user", intensity: 0.86 }
    : { text: "触る場所は考えなさい。まったく、油断も隙もないんだから。", emotion: "annoyed", gesture: "crossed_arms", gaze: "user", intensity: 0.7 };
}

function CompanionApp() {
  const [hydrated, setHydrated] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([initialGreeting]);
  const [memories, setMemories] = useState<string[]>([]);
  const [relationship, setRelationship] = useState<RelationshipState>(DEFAULT_RELATIONSHIP);
  const [input, setInput] = useState("");
  const [emotion, setEmotion] = useState<CompanionEmotion>("neutral");
  const [gesture, setGesture] = useState<CompanionGesture>("idle");
  const [gaze, setGaze] = useState<CompanionGaze>("user");
  const [intensity, setIntensity] = useState(0.4);
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [avatarEngine, setAvatarEngine] = useState<AvatarEngine>("vrm");
  const [chatVisible, setChatVisible] = useState(true);
  const [status, setStatus] = useState("ready");
  const [voiceEngine, setVoiceEngine] = useState("VOICEVOX ready");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const lastTouchRef = useRef<{ region: TouchRegion; at: number } | null>(null);

  useEffect(() => {
    setMessages(normalizeMessages(safeRead(STORAGE.messages, [initialGreeting])));
    setMemories(safeRead<string[]>(STORAGE.memories, []).filter((item) => typeof item === "string").slice(-36));
    setRelationship(normalizeRelationship(safeRead<Partial<RelationshipState>>(STORAGE.relationship, DEFAULT_RELATIONSHIP)));
    setVoiceEnabled(safeRead(STORAGE.voice, true));
    const savedEngine = safeRead<AvatarEngine>(STORAGE.engine, "vrm");
    setAvatarEngine(savedEngine === "inochi" ? "inochi" : "vrm");
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(STORAGE.messages, JSON.stringify(messages.slice(-100)));
    localStorage.setItem(STORAGE.memories, JSON.stringify(memories.slice(-36)));
    localStorage.setItem(STORAGE.relationship, JSON.stringify(relationship));
    localStorage.setItem(STORAGE.voice, JSON.stringify(voiceEnabled));
    localStorage.setItem(STORAGE.engine, JSON.stringify(avatarEngine));
  }, [avatarEngine, hydrated, memories, messages, relationship, voiceEnabled]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking, chatVisible]);

  useEffect(() => () => {
    abortRef.current?.abort();
    stopJapaneseVoice();
  }, []);

  const recentMessages = useMemo(() => messages.slice(-22), [messages]);
  const relationshipLabel = relationship.trust >= 72 ? "trusted" : relationship.affinity >= 48 ? "warming up" : "getting acquainted";

  function context(): CompanionContext {
    return {
      memories,
      relationship,
      localTime: new Intl.DateTimeFormat("ja-JP", {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date()),
    };
  }

  function animateReply(next: { emotion: CompanionEmotion; gesture: CompanionGesture; gaze: CompanionGaze; intensity: number }) {
    setEmotion(next.emotion);
    setGesture(next.gesture);
    setGaze(next.gaze);
    setIntensity(next.intensity);
  }

  function playVoice(text: string, nextEmotion: CompanionEmotion) {
    if (!voiceEnabled) return;
    void speakJapanese(text, nextEmotion, {
      onStart: () => setSpeaking(true),
      onEnd: () => setSpeaking(false),
      onError: () => setSpeaking(false),
      onEngine: (engine) => setVoiceEngine(engine === "voicevox" ? "VOICEVOX community" : engine === "native" ? "Android Japanese voice" : "browser Japanese voice"),
    });
  }

  async function sendMessage(explicitText?: string) {
    const text = (explicitText ?? input).trim();
    if (!text || thinking) return;

    stopJapaneseVoice();
    setSpeaking(false);
    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: text,
      createdAt: Date.now(),
    };
    const nextMessages = [...messages, userMessage];
    const extracted = extractMemory(text);
    const nextMemories = mergeMemories(memories, [extracted]);
    const nextRelationship = normalizeRelationship({
      ...relationship,
      affinity: relationship.affinity + (text.length > 22 ? 2 : 1),
      trust: relationship.trust + (extracted ? 2 : 0.5),
      annoyance: relationship.annoyance - 5,
      interactionCount: relationship.interactionCount + 1,
    });

    setMessages(nextMessages);
    setMemories(nextMemories);
    setRelationship(nextRelationship);
    setInput("");
    setThinking(true);
    setStatus("thinking");
    animateReply({ emotion: "neutral", gesture: "thinking", gaze: "down", intensity: 0.38 });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const reply = await generateCompanionReply(
        nextMessages,
        { memories: nextMemories, relationship: nextRelationship, localTime: context().localTime },
        controller.signal,
        (progress) => {
          if (progress.phase === "fallback") setStatus("instant local response");
          else if (progress.phase === "generating") setStatus("community model is replying");
          else setStatus(progress.waitSeconds ? `community queue · ~${progress.waitSeconds}s` : "community queue");
        },
      );
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: "assistant",
        content: reply.speech,
        createdAt: Date.now(),
      };
      setMessages((current) => [...current, assistantMessage]);
      setMemories((current) => mergeMemories(current, [reply.memory]));
      setRelationship((current) => normalizeRelationship({
        ...current,
        affinity: current.affinity + (reply.emotion === "happy" || reply.emotion === "embarrassed" ? 1 : 0),
        annoyance: current.annoyance - 3,
      }));
      animateReply(reply);
      setStatus(`${reply.emotion} · ${reply.gesture}`);
      playVoice(reply.speech, reply.emotion);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const fallback = "今は少し回線が変みたい。べ、別に逃げたわけじゃないから、もう一度話しかけて。";
      setMessages((current) => [...current, { id: createId(), role: "assistant", content: fallback, createdAt: Date.now() }]);
      animateReply({ emotion: "worried", gesture: "hand_to_chest", gaze: "user", intensity: 0.62 });
      setStatus("connection problem");
      playVoice(fallback, "worried");
    } finally {
      setThinking(false);
      abortRef.current = null;
    }
  }

  function handleTouch(region: TouchRegion) {
    if (thinking) return;
    const now = Date.now();
    const previous = lastTouchRef.current;
    const repeated = Boolean(previous && previous.region === region && now - previous.at < 4200);
    lastTouchRef.current = { region, at: now };
    const reaction = touchReaction(region, relationship, repeated);
    const annoyanceDelta = region === "body" ? (repeated ? 24 : 12) : region === "shoulder" ? 4 : -2;
    const affinityDelta = region === "head" || region === "hand" ? (repeated ? 0 : 1) : 0;

    setRelationship((current) => normalizeRelationship({
      ...current,
      affinity: current.affinity + affinityDelta,
      annoyance: current.annoyance + annoyanceDelta,
      touchCount: current.touchCount + 1,
    }));
    setMessages((current) => [...current, { id: createId(), role: "assistant" as const, content: reaction.text, createdAt: Date.now() }].slice(-100));
    animateReply(reaction);
    setStatus(`touch · ${region}`);
    if (navigator.vibrate) navigator.vibrate(region === "body" ? [25, 40, 25] : 18);
    playVoice(reaction.text, reaction.emotion);
  }

  function toggleVoice() {
    if (voiceEnabled) {
      stopJapaneseVoice();
      setSpeaking(false);
    }
    setVoiceEnabled((value) => !value);
  }

  function resetConversation() {
    abortRef.current?.abort();
    stopJapaneseVoice();
    setMessages([initialGreeting]);
    setMemories([]);
    setRelationship(DEFAULT_RELATIONSHIP);
    setEmotion("neutral");
    setGesture("idle");
    setGaze("user");
    setIntensity(0.4);
    setThinking(false);
    setSpeaking(false);
    setStatus("new beginning");
  }

  return (
    <main className="min-h-[100dvh] overflow-hidden bg-[#0b0911] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_10%_5%,rgba(244,143,180,0.16),transparent_30%),radial-gradient(circle_at_92%_76%,rgba(130,112,224,0.14),transparent_35%)]" />

      <div className="relative mx-auto flex min-h-[100dvh] max-w-[1540px] flex-col px-2.5 pb-[max(0.6rem,env(safe-area-inset-bottom))] pt-[max(0.6rem,env(safe-area-inset-top))] sm:px-5 lg:px-7">
        <header className="mb-2.5 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.05] px-3.5 py-2.5 shadow-xl backdrop-blur-2xl sm:px-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="relative grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-pink-200 via-pink-300 to-violet-400 shadow-[0_0_30px_rgba(239,134,172,0.35)]">
              <Sparkles className="size-5 text-[#281426]" />
              <span className="absolute -bottom-0.5 -right-0.5 size-3 rounded-full border-2 border-[#17121e] bg-emerald-400" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-base font-semibold tracking-wide">{COMPANION_NAME}</h1>
                <span className="rounded-full bg-pink-300/10 px-2 py-0.5 text-[9px] uppercase tracking-[0.14em] text-pink-200/70">{avatarEngine === "vrm" ? "VRM 3D" : "Inochi 2D"}</span>
              </div>
              <p className="truncate text-[11px] text-white/45">{status} · {relationshipLabel}</p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <div className="mr-1 hidden items-center gap-2 rounded-xl border border-white/8 bg-black/15 px-3 py-2 sm:flex">
              <Heart className="size-3.5 text-pink-300" />
              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full bg-gradient-to-r from-pink-300 to-violet-400 transition-all" style={{ width: `${relationship.affinity}%` }} />
              </div>
            </div>
            <div className="flex rounded-xl border border-white/10 bg-black/20 p-1" aria-label="Character engine">
              <button type="button" onClick={() => setAvatarEngine("vrm")} className={`rounded-lg px-2 py-2 text-[10px] font-medium transition ${avatarEngine === "vrm" ? "bg-pink-200 text-[#281426]" : "text-white/55 hover:bg-white/8"}`} aria-pressed={avatarEngine === "vrm"}>3D</button>
              <button type="button" onClick={() => setAvatarEngine("inochi")} className={`rounded-lg px-2 py-2 text-[10px] font-medium transition ${avatarEngine === "inochi" ? "bg-pink-200 text-[#281426]" : "text-white/55 hover:bg-white/8"}`} aria-pressed={avatarEngine === "inochi"}>2D</button>
            </div>
            <button type="button" onClick={toggleVoice} className="grid size-10 place-items-center rounded-xl border border-white/10 bg-white/[0.055] text-white/75 transition hover:bg-white/10" aria-label={voiceEnabled ? "Disable voice" : "Enable voice"}>
              {voiceEnabled ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
            </button>
            <button type="button" onClick={() => setChatVisible((value) => !value)} className="grid size-10 place-items-center rounded-xl border border-white/10 bg-white/[0.055] text-white/75 transition hover:bg-white/10" aria-label="Toggle chat">
              {chatVisible ? <PanelRightClose className="size-4" /> : <PanelRightOpen className="size-4" />}
            </button>
            <button type="button" onClick={resetConversation} className="grid size-10 place-items-center rounded-xl border border-white/10 bg-white/[0.055] text-white/75 transition hover:bg-white/10" aria-label="Reset conversation">
              <RefreshCw className="size-4" />
            </button>
          </div>
        </header>

        <section className={`grid min-h-0 flex-1 gap-2.5 transition-[grid-template-columns] duration-300 ${chatVisible ? "lg:grid-cols-[minmax(0,1.12fr)_minmax(380px,0.68fr)]" : "grid-cols-1"}`}>
          <div className="relative min-h-[52dvh] lg:min-h-0">
            {hydrated ? (
              avatarEngine === "vrm" ? (
                <CompanionStage emotion={emotion} gesture={gesture} gaze={gaze} intensity={intensity} speaking={speaking || thinking} onTouch={handleTouch} />
              ) : (
                <InochiCompanionStage emotion={emotion} gesture={gesture} gaze={gaze} intensity={intensity} speaking={speaking || thinking} onTouch={handleTouch} />
              )
            ) : (
              <div className="h-full min-h-[460px] animate-pulse rounded-[2rem] bg-white/[0.04]" />
            )}
            <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center px-3">
              <div className="rounded-full border border-white/10 bg-black/40 px-3 py-1.5 text-[10px] tracking-wide text-white/55 shadow-lg backdrop-blur-xl">
                {avatarEngine === "vrm" ? "VRM 3D · touch head, face, shoulder, hand, or body" : "Inochi2D · tap or drag the puppet to react"}
              </div>
            </div>
          </div>

          {chatVisible && (
            <div className="flex min-h-[40dvh] flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-[#15121d]/92 shadow-2xl backdrop-blur-2xl lg:min-h-0">
              <div className="flex items-center gap-2 border-b border-white/8 px-4 py-3 text-sm text-white/65">
                <MessageCircle className="size-4 text-pink-300" />
                Japanese conversation
                <span className="ml-auto max-w-40 truncate rounded-full bg-white/5 px-2 py-1 text-[9px] uppercase tracking-[0.12em] text-white/35">{voiceEngine}</span>
              </div>

              <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-4 sm:px-4">
                {recentMessages.map((message) => (
                  <div key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[89%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed shadow-sm ${message.role === "user" ? "rounded-br-md bg-gradient-to-br from-violet-500/90 to-fuchsia-500/78 text-white" : "rounded-bl-md border border-white/8 bg-white/[0.06] text-white/88"}`}>
                      {message.content}
                    </div>
                  </div>
                ))}

                {thinking && (
                  <div className="flex justify-start">
                    <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/8 bg-white/[0.055] px-4 py-3">
                      {[0, 1, 2].map((index) => <span key={index} className="size-1.5 animate-bounce rounded-full bg-pink-300/80" style={{ animationDelay: `${index * 140}ms` }} />)}
                    </div>
                  </div>
                )}
              </div>

              {messages.length <= 2 && !thinking && (
                <div className="flex gap-2 overflow-x-auto px-3 pb-2 sm:px-4">
                  {quickPrompts.map((prompt) => (
                    <button key={prompt} type="button" onClick={() => void sendMessage(prompt)} className="shrink-0 rounded-full border border-pink-200/15 bg-pink-200/[0.06] px-3 py-1.5 text-[11px] text-pink-100/70 transition hover:bg-pink-200/10">
                      {prompt}
                    </button>
                  ))}
                </div>
              )}

              <div className="border-t border-white/8 p-3 sm:p-4">
                <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-black/20 p-2 focus-within:border-pink-300/35">
                  <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); } }} placeholder="日本語でも、あなたの言葉でも…" rows={1} maxLength={1800} className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm text-white outline-none placeholder:text-white/28" />
                  <button type="button" disabled={!input.trim() || thinking} onClick={() => void sendMessage()} className="grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-pink-200 via-pink-300 to-violet-400 text-[#201326] shadow-[0_8px_28px_rgba(226,121,169,0.2)] transition active:scale-95 disabled:cursor-not-allowed disabled:opacity-35" aria-label="Send message">
                    <Send className="size-4" />
                  </button>
                </div>
                <p className="mt-2 px-1 text-[9px] leading-relaxed text-white/28">
                  AI Horde community inference with instant local fallback · Voice: VOICEVOX 四国めたん via TTS Quest · Avatar engine: {avatarEngine === "vrm" ? "VRM 3D" : "Inochi2D 2.5D"}
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
