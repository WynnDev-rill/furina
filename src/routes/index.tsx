import { createFileRoute } from "@tanstack/react-router";
import {
  MessageCircle,
  RefreshCw,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { CompanionStage } from "@/components/companion/CompanionStage";
import { generateCompanionReply } from "@/lib/companion/ai-horde";
import { COMPANION_NAME } from "@/lib/companion/persona";
import type {
  ChatMessage,
  CompanionEmotion,
  TouchRegion,
} from "@/lib/companion/types";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: `${COMPANION_NAME} — Virtual Companion` },
      {
        name: "description",
        content: "Original Japanese-speaking virtual companion with contextual 3D reactions.",
      },
    ],
  }),
  component: CompanionApp,
});

const STORAGE_KEY = "mirei:conversation:v1";

const initialGreeting: ChatMessage = {
  id: "mirei-greeting",
  role: "assistant",
  content: "やっと来たのね。べ、別に待っていたわけじゃないけど……今日は何を話す？",
  createdAt: Date.now(),
};

const touchReplies: Record<TouchRegion, { text: string; emotion: CompanionEmotion }> = {
  head: {
    text: "ちょ、ちょっと……急に頭を撫でないで。嫌とは言ってないけど。",
    emotion: "embarrassed",
  },
  face: {
    text: "近いわよ。そんなに見つめたら、さすがに落ち着かないじゃない。",
    emotion: "embarrassed",
  },
  shoulder: {
    text: "何？　ちゃんと聞いているから、そんなに急かさないで。",
    emotion: "annoyed",
  },
  hand: {
    text: "手を取りたいなら、最初からそう言えばいいのに。……少しだけよ。",
    emotion: "playful",
  },
  body: {
    text: "こら。触る場所は考えなさい。まったく、油断も隙もないんだから。",
    emotion: "annoyed",
  },
};

function createId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readStoredMessages() {
  if (typeof window === "undefined") return [initialGreeting];
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]") as ChatMessage[];
    if (!Array.isArray(stored) || !stored.length) return [initialGreeting];
    return stored
      .filter((item) => item && (item.role === "user" || item.role === "assistant"))
      .map((item) => ({
        id: String(item.id || createId()),
        role: item.role,
        content: String(item.content || "").slice(0, 4000),
        createdAt: Number(item.createdAt) || Date.now(),
      }))
      .slice(-80);
  } catch {
    return [initialGreeting];
  }
}

function CompanionApp() {
  const [hydrated, setHydrated] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([initialGreeting]);
  const [input, setInput] = useState("");
  const [emotion, setEmotion] = useState<CompanionEmotion>("neutral");
  const [thinking, setThinking] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [status, setStatus] = useState("online experiment");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages(readStoredMessages());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-80)));
  }, [hydrated, messages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, thinking]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (typeof speechSynthesis !== "undefined") speechSynthesis.cancel();
    };
  }, []);

  const recentMessages = useMemo(() => messages.slice(-16), [messages]);

  function speakJapanese(text: string) {
    if (!voiceEnabled || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ja-JP";
    utterance.rate = 1.03;
    utterance.pitch = 1.12;
    const voices = window.speechSynthesis.getVoices();
    utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith("ja")) || null;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  }

  async function sendMessage() {
    const text = input.trim();
    if (!text || thinking) return;

    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: text,
      createdAt: Date.now(),
    };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setThinking(true);
    setEmotion("neutral");
    setStatus("community model is thinking");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const reply = await generateCompanionReply(nextMessages, controller.signal);
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: "assistant",
        content: reply.speech,
        createdAt: Date.now(),
      };
      setMessages((current) => [...current, assistantMessage]);
      setEmotion(reply.emotion);
      setStatus(`${reply.emotion} · ${reply.gesture}`);
      speakJapanese(reply.speech);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      const fallback = "今は少し回線が混んでいるみたい。べ、別に逃げたわけじゃないから、もう一度話しかけて。";
      setMessages((current) => [
        ...current,
        {
          id: createId(),
          role: "assistant",
          content: fallback,
          createdAt: Date.now(),
        },
      ]);
      setEmotion("worried");
      setStatus(error instanceof Error ? error.message : "community provider unavailable");
      speakJapanese(fallback);
    } finally {
      setThinking(false);
      abortRef.current = null;
    }
  }

  function handleTouch(region: TouchRegion) {
    if (thinking) return;
    const reaction = touchReplies[region];
    setEmotion(reaction.emotion);
    setMessages((current) => [
      ...current,
      {
        id: createId(),
        role: "assistant",
        content: reaction.text,
        createdAt: Date.now(),
      },
    ]);
    setStatus(`touch reaction · ${region}`);
    speakJapanese(reaction.text);
  }

  function resetConversation() {
    abortRef.current?.abort();
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
    setMessages([initialGreeting]);
    setEmotion("neutral");
    setThinking(false);
    setSpeaking(false);
    setStatus("conversation reset");
  }

  return (
    <main className="min-h-[100dvh] overflow-hidden bg-[#0b0911] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_15%_10%,rgba(244,143,180,0.13),transparent_32%),radial-gradient(circle_at_90%_70%,rgba(130,112,224,0.12),transparent_34%)]" />

      <div className="relative mx-auto flex min-h-[100dvh] max-w-[1500px] flex-col px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-[max(0.75rem,env(safe-area-inset-top))] sm:px-5 lg:px-7">
        <header className="mb-3 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.045] px-4 py-3 backdrop-blur-xl">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-pink-300 to-violet-400 shadow-[0_0_28px_rgba(239,134,172,0.3)]">
              <Sparkles className="size-5 text-[#211326]" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold tracking-wide">{COMPANION_NAME}</h1>
              <p className="truncate text-xs text-white/50">{status}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setVoiceEnabled((value) => !value)}
              className="grid size-10 place-items-center rounded-xl border border-white/10 bg-white/[0.055] text-white/75 transition hover:bg-white/10"
              aria-label={voiceEnabled ? "Disable voice" : "Enable voice"}
            >
              {voiceEnabled ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
            </button>
            <button
              type="button"
              onClick={resetConversation}
              className="grid size-10 place-items-center rounded-xl border border-white/10 bg-white/[0.055] text-white/75 transition hover:bg-white/10"
              aria-label="Reset conversation"
            >
              <RefreshCw className="size-4" />
            </button>
          </div>
        </header>

        <section className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1.08fr)_minmax(390px,0.72fr)]">
          <div className="relative min-h-[48dvh] lg:min-h-0">
            {hydrated ? (
              <CompanionStage emotion={emotion} speaking={speaking || thinking} onTouch={handleTouch} />
            ) : (
              <div className="h-full min-h-[420px] animate-pulse rounded-[2rem] bg-white/[0.04]" />
            )}
            <div className="pointer-events-none absolute inset-x-0 bottom-4 flex justify-center">
              <div className="rounded-full border border-white/10 bg-black/35 px-3 py-1.5 text-[11px] tracking-wide text-white/55 backdrop-blur-lg">
                Tap her head, face, shoulder, hand, or body
              </div>
            </div>
          </div>

          <div className="flex min-h-[43dvh] flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-[#15121d]/90 shadow-2xl backdrop-blur-xl lg:min-h-0">
            <div className="flex items-center gap-2 border-b border-white/8 px-4 py-3 text-sm text-white/65">
              <MessageCircle className="size-4 text-pink-300" />
              Japanese conversation
              <span className="ml-auto rounded-full bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.15em] text-white/35">
                AI Horde
              </span>
            </div>

            <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-4 sm:px-4">
              {recentMessages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed shadow-sm ${
                      message.role === "user"
                        ? "rounded-br-md bg-gradient-to-br from-violet-500/85 to-fuchsia-500/75 text-white"
                        : "rounded-bl-md border border-white/8 bg-white/[0.055] text-white/85"
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))}

              {thinking && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/8 bg-white/[0.055] px-4 py-3">
                    {[0, 1, 2].map((index) => (
                      <span
                        key={index}
                        className="size-1.5 animate-bounce rounded-full bg-pink-300/80"
                        style={{ animationDelay: `${index * 140}ms` }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-white/8 p-3 sm:p-4">
              <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-black/20 p-2 focus-within:border-pink-300/35">
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder="話しかけてみて…"
                  rows={1}
                  maxLength={1800}
                  className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 text-sm text-white outline-none placeholder:text-white/30"
                />
                <button
                  type="button"
                  disabled={!input.trim() || thinking}
                  onClick={() => void sendMessage()}
                  className="grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-pink-300 to-violet-400 text-[#201326] shadow-[0_8px_28px_rgba(226,121,169,0.18)] transition active:scale-95 disabled:cursor-not-allowed disabled:opacity-35"
                  aria-label="Send message"
                >
                  <Send className="size-4" />
                </button>
              </div>
              <p className="mt-2 px-1 text-[10px] leading-relaxed text-white/30">
                Experimental community inference can queue or fail under heavy load. Conversation stays on this device.
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
