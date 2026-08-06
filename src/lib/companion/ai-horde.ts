import { buildCompanionPrompt } from "./persona";
import type {
  ChatMessage,
  CompanionEmotion,
  CompanionGesture,
  CompanionReply,
} from "./types";

const API_BASE = "https://aihorde.net/api/v2";
const ANONYMOUS_API_KEY = "0000000000";
const CLIENT_AGENT = "MireiCompanion:0.1:github.com/WynnDev-rill/furina";

const EMOTIONS = new Set<CompanionEmotion>([
  "neutral",
  "happy",
  "embarrassed",
  "annoyed",
  "worried",
  "sad",
  "surprised",
  "playful",
]);

const GESTURES = new Set<CompanionGesture>([
  "idle",
  "soft_smile",
  "look_away",
  "hands_on_hips",
  "lean_closer",
  "small_wave",
  "thinking",
  "pout",
]);

type HordeSubmitResponse = { id?: string; message?: string };
type HordeStatusResponse = {
  done?: boolean;
  faulted?: boolean;
  wait_time?: number;
  generations?: Array<{ text?: string }>;
};

function delay(milliseconds: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

function extractJson(text: string) {
  const cleaned = text.replace(/```(?:json)?/gi, "").replace(/```/g, "").trim();
  const first = cleaned.indexOf("{");
  const last = cleaned.lastIndexOf("}");
  if (first === -1 || last <= first) return null;
  try {
    return JSON.parse(cleaned.slice(first, last + 1)) as Partial<CompanionReply>;
  } catch {
    return null;
  }
}

function normalizeReply(rawText: string): CompanionReply {
  const parsed = extractJson(rawText);
  const speech = String(parsed?.speech || rawText)
    .replace(/^MIREI:\s*/i, "")
    .trim()
    .slice(0, 700);
  const emotion = EMOTIONS.has(parsed?.emotion as CompanionEmotion)
    ? (parsed?.emotion as CompanionEmotion)
    : "neutral";
  const gesture = GESTURES.has(parsed?.gesture as CompanionGesture)
    ? (parsed?.gesture as CompanionGesture)
    : "idle";
  const intensity = Math.max(0, Math.min(1, Number(parsed?.intensity) || 0.45));
  const gaze = ["user", "side", "down"].includes(String(parsed?.gaze))
    ? (parsed?.gaze as CompanionReply["gaze"])
    : "user";

  return {
    speech: speech || "べ、別に無視したわけじゃないわ。もう一度言って。",
    emotion,
    intensity,
    gesture,
    gaze,
  };
}

export async function generateCompanionReply(
  messages: ChatMessage[],
  signal?: AbortSignal,
): Promise<CompanionReply> {
  const submitResponse = await fetch(`${API_BASE}/generate/text/async`, {
    method: "POST",
    signal,
    headers: {
      "content-type": "application/json",
      apikey: ANONYMOUS_API_KEY,
      "Client-Agent": CLIENT_AGENT,
    },
    body: JSON.stringify({
      prompt: buildCompanionPrompt(messages),
      params: {
        max_context_length: 4096,
        max_length: 220,
        temperature: 0.82,
        top_p: 0.9,
        top_k: 40,
        rep_pen: 1.08,
        stop_sequence: ["USER:", "\n\nUSER"],
      },
      trusted_workers: false,
      validated_backends: false,
      slow_workers: true,
    }),
  });

  const submitted = (await submitResponse.json()) as HordeSubmitResponse;
  if (!submitResponse.ok || !submitted.id) {
    throw new Error(submitted.message || `AI Horde rejected the request (${submitResponse.status}).`);
  }

  const startedAt = Date.now();
  while (Date.now() - startedAt < 150_000) {
    await delay(2_500, signal);
    const statusResponse = await fetch(
      `${API_BASE}/generate/text/status/${encodeURIComponent(submitted.id)}`,
      {
        signal,
        headers: {
          apikey: ANONYMOUS_API_KEY,
          "Client-Agent": CLIENT_AGENT,
        },
      },
    );
    const status = (await statusResponse.json()) as HordeStatusResponse;
    if (!statusResponse.ok) throw new Error(`AI Horde status failed (${statusResponse.status}).`);
    if (status.faulted) throw new Error("The community worker could not complete this reply.");
    if (status.done) {
      const text = status.generations?.[0]?.text;
      if (!text) throw new Error("The community worker returned an empty reply.");
      return normalizeReply(text);
    }
  }

  throw new Error("The community queue took too long. Try again shortly.");
}
