import { buildCompanionPrompt } from "./persona";
import type {
  ChatMessage,
  CompanionContext,
  CompanionEmotion,
  CompanionGesture,
  CompanionReply,
  ProviderProgress,
} from "./types";

const API_BASE = "https://aihorde.net/api/v2";
const ANONYMOUS_API_KEY = "0000000000";
const CLIENT_AGENT = "MireiCompanion:1.0:github.com/WynnDev-rill/furina";
const COMMUNITY_REPLY_BUDGET_MS = 30_000;

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
  "crossed_arms",
  "hand_to_chest",
  "shy_hair_touch",
]);

type HordeSubmitResponse = { id?: string; message?: string };
type HordeStatusResponse = {
  done?: boolean;
  faulted?: boolean;
  wait_time?: number;
  queue_position?: number;
  generations?: Array<{ text?: string }>;
};

function delay(milliseconds: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = globalThis.setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      "abort",
      () => {
        globalThis.clearTimeout(timer);
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

function cleanSpeech(value: string) {
  return value
    .replace(/^MIREI:\s*/i, "")
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/\*[^*]{0,80}\*/g, "")
    .trim()
    .slice(0, 900);
}

function normalizeReply(rawText: string): CompanionReply {
  const parsed = extractJson(rawText);
  const speech = cleanSpeech(String(parsed?.speech || rawText));
  const emotion = EMOTIONS.has(parsed?.emotion as CompanionEmotion)
    ? (parsed?.emotion as CompanionEmotion)
    : "neutral";
  const gesture = GESTURES.has(parsed?.gesture as CompanionGesture)
    ? (parsed?.gesture as CompanionGesture)
    : "idle";
  const intensity = Math.max(0.12, Math.min(1, Number(parsed?.intensity) || 0.48));
  const gaze = ["user", "side", "down"].includes(String(parsed?.gaze))
    ? (parsed?.gaze as CompanionReply["gaze"])
    : "user";
  const memory = String(parsed?.memory || "").replace(/\s+/g, " ").trim().slice(0, 180);

  return {
    speech: speech || "……聞こえているわ。もう一度、ゆっくり話して。",
    emotion,
    intensity,
    gesture,
    gaze,
    memory: memory.length >= 4 ? memory : undefined,
  };
}

function includesAny(text: string, words: string[]) {
  return words.some((word) => text.includes(word));
}

function buildLocalFallback(messages: ChatMessage[], context: CompanionContext): CompanionReply {
  const latest = messages.filter((message) => message.role === "user").at(-1)?.content.trim() || "";
  const lower = latest.toLowerCase();
  const close = context.relationship.trust >= 55 || context.relationship.affinity >= 60;

  if (includesAny(lower, ["sad", "sedih", "capek", "lelah", "疲れ", "つら", "悲し", "lonely", "kesepian"])) {
    return {
      speech: close
        ? "無理に平気なふりをしなくていいわ。……少しくらいなら、私がそばで聞いていてあげる。"
        : "それは簡単に片づけられる話じゃないわね。無理に元気を出さなくていいから、話せるところから聞かせて。",
      emotion: "worried",
      intensity: 0.66,
      gesture: "hand_to_chest",
      gaze: "user",
    };
  }

  if (includesAny(lower, ["love", "suka kamu", "sayang", "好き", "愛して", "cantik", "beautiful", "かわいい"])) {
    return {
      speech: close
        ? "そ、そういうことを急に言うのは反則よ。……嬉しくないとは言ってないけど。"
        : "急に距離を詰めすぎ。まずは、あなたがどんな人なのかもう少し見せなさい。",
      emotion: "embarrassed",
      intensity: 0.78,
      gesture: "shy_hair_touch",
      gaze: "side",
    };
  }

  if (includesAny(lower, ["hello", "halo", "hai", "こんにちは", "おはよう", "こんばんは"])) {
    return {
      speech: "来たのね。べつに待ちくたびれてはいないけど……今日は何を話す？",
      emotion: "happy",
      intensity: 0.42,
      gesture: "small_wave",
      gaze: "user",
    };
  }

  if (latest.endsWith("?") || latest.endsWith("？") || includesAny(lower, ["kenapa", "bagaimana", "apa ", "why", "how", "what"])) {
    return {
      speech: "ちゃんと考えて答えたいのに、今は回線が少し不安定みたい。要点をもう一度送ってくれたら、今度こそ逃さないわ。",
      emotion: "annoyed",
      intensity: 0.38,
      gesture: "thinking",
      gaze: "down",
    };
  }

  return {
    speech: close
      ? "うん、ちゃんと聞いているわ。続きも話しなさい……途中でやめられると気になるでしょう。"
      : "聞いているわ。もう少し詳しく話してくれたら、私もちゃんと意見を返せる。",
    emotion: "neutral",
    intensity: 0.34,
    gesture: "soft_smile",
    gaze: "user",
  };
}

export async function generateCompanionReply(
  messages: ChatMessage[],
  context: CompanionContext,
  signal?: AbortSignal,
  onProgress?: (progress: ProviderProgress) => void,
): Promise<CompanionReply> {
  try {
    const submitResponse = await fetch(`${API_BASE}/generate/text/async`, {
      method: "POST",
      signal,
      headers: {
        "content-type": "application/json",
        apikey: ANONYMOUS_API_KEY,
        "Client-Agent": CLIENT_AGENT,
      },
      body: JSON.stringify({
        prompt: buildCompanionPrompt(messages, context),
        params: {
          max_context_length: 6144,
          max_length: 300,
          temperature: 0.78,
          top_p: 0.92,
          top_k: 45,
          rep_pen: 1.1,
          rep_pen_range: 512,
          stop_sequence: ["USER:", "\n\nUSER", "```"],
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
    while (Date.now() - startedAt < COMMUNITY_REPLY_BUDGET_MS) {
      await delay(2_200, signal);
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
      onProgress?.({
        phase: status.wait_time && status.wait_time <= 1 ? "generating" : "queued",
        waitSeconds: Math.max(0, Number(status.wait_time) || 0),
      });
    }

    throw new Error("Community queue timeout");
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    onProgress?.({ phase: "fallback" });
    await delay(320, signal);
    return buildLocalFallback(messages, context);
  }
}
