import type { CompanionEmotion } from "./types";

type NativeVoiceBridge = {
  isAvailable?: () => boolean;
  speak?: (text: string, rate: number, pitch: number) => void;
  stop?: () => void;
};

declare global {
  interface Window {
    MireiNative?: NativeVoiceBridge;
  }
}

export type VoiceHandlers = {
  onStart: () => void;
  onEnd: () => void;
  onError?: (reason: string) => void;
  onEngine?: (engine: "voicevox" | "native" | "browser") => void;
};

type TtsQuestResponse = {
  success?: boolean;
  errorMessage?: string;
  audioStatusUrl?: string;
  mp3DownloadUrl?: string;
  mp3StreamingUrl?: string;
};

type TtsStatus = {
  isAudioReady?: boolean;
  isAudioError?: boolean;
};

let activeAudio: HTMLAudioElement | null = null;
let activeUtterance: SpeechSynthesisUtterance | null = null;
let nativeCleanup: (() => void) | null = null;

const SPEAKER_BY_EMOTION: Record<CompanionEmotion, number> = {
  neutral: 2,
  happy: 0,
  embarrassed: 0,
  annoyed: 6,
  worried: 37,
  sad: 37,
  surprised: 2,
  playful: 6,
};

function sleep(milliseconds: number) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, milliseconds));
}

export function stopJapaneseVoice() {
  nativeCleanup?.();
  nativeCleanup = null;
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.src = "";
    activeAudio.load();
    activeAudio = null;
  }
  if (typeof window !== "undefined") {
    try { window.MireiNative?.stop?.(); } catch {}
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  }
  activeUtterance = null;
}

async function waitForDownload(statusUrl: string, downloadUrl: string) {
  for (let attempt = 0; attempt < 18; attempt += 1) {
    const response = await fetch(statusUrl, { cache: "no-store" });
    if (response.ok) {
      const status = (await response.json()) as TtsStatus;
      if (status.isAudioError) throw new Error("VOICEVOX synthesis failed");
      if (status.isAudioReady) return downloadUrl;
    }
    await sleep(500);
  }
  throw new Error("VOICEVOX synthesis timeout");
}

async function playAudioUrl(url: string, handlers: VoiceHandlers) {
  const audio = new Audio();
  activeAudio = audio;
  audio.preload = "auto";
  audio.src = url;
  audio.onplaying = () => handlers.onStart();
  audio.onended = () => {
    if (activeAudio === audio) activeAudio = null;
    handlers.onEnd();
  };
  audio.onerror = () => {
    if (activeAudio === audio) activeAudio = null;
    handlers.onError?.("audio playback failed");
  };
  await audio.play();
}

async function tryVoicevox(text: string, emotion: CompanionEmotion, handlers: VoiceHandlers) {
  const speaker = SPEAKER_BY_EMOTION[emotion];
  const endpoint = new URL("https://api.tts.quest/v3/voicevox/synthesis");
  endpoint.searchParams.set("speaker", String(speaker));
  endpoint.searchParams.set("text", text.slice(0, 420));

  const response = await fetch(endpoint, { cache: "no-store" });
  if (!response.ok) throw new Error(`VOICEVOX request failed (${response.status})`);
  const result = (await response.json()) as TtsQuestResponse;
  if (!result.success) throw new Error(result.errorMessage || "VOICEVOX rejected the text");

  handlers.onEngine?.("voicevox");
  if (result.mp3StreamingUrl) {
    try {
      await playAudioUrl(result.mp3StreamingUrl, handlers);
      return;
    } catch {
      if (!result.audioStatusUrl || !result.mp3DownloadUrl) throw new Error("VOICEVOX stream unavailable");
    }
  }
  if (!result.audioStatusUrl || !result.mp3DownloadUrl) throw new Error("VOICEVOX returned no audio URL");
  const readyUrl = await waitForDownload(result.audioStatusUrl, result.mp3DownloadUrl);
  await playAudioUrl(readyUrl, handlers);
}

function tryNative(text: string, emotion: CompanionEmotion, handlers: VoiceHandlers) {
  const bridge = window.MireiNative;
  if (!bridge?.speak) return false;

  const start = () => handlers.onStart();
  const done = () => {
    cleanup();
    handlers.onEnd();
  };
  const failed = () => {
    cleanup();
    handlers.onError?.("native Japanese voice failed");
  };
  const cleanup = () => {
    window.removeEventListener("mirei-tts-start", start);
    window.removeEventListener("mirei-tts-done", done);
    window.removeEventListener("mirei-tts-error", failed);
    if (nativeCleanup === cleanup) nativeCleanup = null;
  };

  window.addEventListener("mirei-tts-start", start, { once: true });
  window.addEventListener("mirei-tts-done", done, { once: true });
  window.addEventListener("mirei-tts-error", failed, { once: true });
  nativeCleanup = cleanup;
  handlers.onEngine?.("native");
  const rate = emotion === "sad" || emotion === "worried" ? 0.92 : emotion === "annoyed" ? 1.08 : 1.0;
  const pitch = emotion === "embarrassed" || emotion === "happy" ? 1.12 : 1.05;
  bridge.speak(text, rate, pitch);
  return true;
}

function speakBrowser(text: string, emotion: CompanionEmotion, handlers: VoiceHandlers) {
  if (!("speechSynthesis" in window)) throw new Error("No Japanese voice engine available");
  const utterance = new SpeechSynthesisUtterance(text);
  activeUtterance = utterance;
  utterance.lang = "ja-JP";
  utterance.rate = emotion === "sad" || emotion === "worried" ? 0.92 : emotion === "annoyed" ? 1.08 : 1.01;
  utterance.pitch = emotion === "embarrassed" || emotion === "happy" ? 1.16 : 1.08;
  const voices = window.speechSynthesis.getVoices();
  utterance.voice = voices.find((voice) => voice.lang.toLowerCase().startsWith("ja")) || null;
  utterance.onstart = () => handlers.onStart();
  utterance.onend = () => {
    activeUtterance = null;
    handlers.onEnd();
  };
  utterance.onerror = () => {
    activeUtterance = null;
    handlers.onError?.("browser Japanese voice failed");
  };
  handlers.onEngine?.("browser");
  window.speechSynthesis.speak(utterance);
}

export async function speakJapanese(
  text: string,
  emotion: CompanionEmotion,
  handlers: VoiceHandlers,
) {
  if (typeof window === "undefined" || !text.trim()) return;
  stopJapaneseVoice();

  try {
    await tryVoicevox(text, emotion, handlers);
    return;
  } catch {
    if (tryNative(text, emotion, handlers)) return;
    speakBrowser(text, emotion, handlers);
  }
}
