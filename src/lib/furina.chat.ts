import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { buildFurinaSystemPrompt } from "./furina.persona";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";
const FALLBACK_SUPABASE_URL = "https://smltficntqkoncyrnajx.supabase.co";
const FALLBACK_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNtbHRmaWNudHFrb25jeXJuYWp4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk5NjkxNjQsImV4cCI6MjA5NTU0NTE2NH0.Wtv8cACK-0lIssboV7vQCpkTwJxlxz8gtriawtjHmhw";
const MAX_IMAGE_DATA = 8_000_000;
const REQUEST_TIMEOUT_MS = 45_000;

const MessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().max(8_000),
});

const ChatInput = z.object({
  messages: z.array(MessageSchema).min(1).max(24),
  characterName: z.string().max(40).default("Furina"),
  persona: z.string().max(6_000).default(""),
  language: z.enum(["auto", "id", "en", "ja"]).default("auto"),
  sharedMemories: z.array(z.string().max(240)).max(80).default([]),
  imageDataUrl: z.string().max(MAX_IMAGE_DATA).optional(),
  clientNow: z.number().int().positive().optional(),
  timeZone: z.string().max(80).optional(),
  clientKey: z.string().max(160).optional(),
});

type ChatInputValue = z.infer<typeof ChatInput>;
type GatewayMessage = { role: string; content: unknown };
type RateState = { count: number; windowStartedAt: number };

const rateStates = new Map<string, RateState>();

function enforcePersonalRateLimit(key: string | undefined) {
  const safeKey = (key || "private-user").slice(0, 160);
  const now = Date.now();
  const previous = rateStates.get(safeKey);
  if (!previous || now - previous.windowStartedAt > 60_000) {
    rateStates.set(safeKey, { count: 1, windowStartedAt: now });
    return;
  }
  if (previous.count >= 30) throw new Error("Terlalu banyak pesan dalam satu menit. Tunggu sebentar.");
  previous.count += 1;
}

function buildSystemPrompt(input: ChatInputValue) {
  return buildFurinaSystemPrompt({
    characterName: input.characterName,
    persona: input.persona,
    language: input.language,
    memories: input.sharedMemories,
    clientNow: input.clientNow,
    timeZone: input.timeZone,
  });
}

function splitBubbles(reply: string) {
  const cleaned = reply
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/^<think>[\s\S]*$/gi, "")
    .trim();
  const bubbles = cleaned
    .split(/\s*<<<\s*SPLIT\s*>>>\s*/i)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 3);
  return bubbles.length ? bubbles : [cleaned || "Aku gagal menyusun jawaban barusan. Coba kirim ulang sekali lagi."];
}

function prepareMessages(data: ChatInputValue) {
  const sourceMessages = data.messages.slice(-20);
  const last = sourceMessages[sourceMessages.length - 1];
  const messages: GatewayMessage[] = sourceMessages
    .slice(0, -1)
    .map((message) => ({ role: message.role, content: message.content }));

  if (data.imageDataUrl && last.role === "user") {
    if (!/^data:image\/(?:png|jpe?g|webp);base64,/i.test(data.imageDataUrl)) {
      throw new Error("Format gambar tidak didukung.");
    }
    messages.push({
      role: "user",
      content: [
        { type: "text", text: last.content || "Jelaskan gambar ini." },
        { type: "image_url", image_url: { url: data.imageDataUrl } },
      ],
    });
  } else {
    messages.push({ role: last.role, content: last.content });
  }
  return messages;
}

async function parseGatewayResponse(response: Response) {
  if (!response.ok) {
    const details = await response.text();
    if (response.status === 429) throw new Error("Lovable AI sedang mencapai batas permintaan. Coba lagi sebentar.");
    if (response.status === 402) throw new Error("Kredit Lovable AI habis.");
    throw new Error(`Lovable AI gagal merespons (${response.status}): ${details.slice(0, 220)}`);
  }
  const json = await response.json();
  const reply = String(json.choices?.[0]?.message?.content || json.reply || "").trim();
  const bubbles = splitBubbles(reply);
  return { reply: bubbles.join("\n\n"), bubbles };
}

async function callLovableGateway(data: ChatInputValue, messages: GatewayMessage[], signal: AbortSignal) {
  const key = process.env.LOVABLE_API_KEY?.trim();
  if (!key) return null;

  const response = await fetch(`${GATEWAY}/chat/completions`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      "Lovable-API-Key": key,
    },
    body: JSON.stringify({
      model: "google/gemini-2.5-flash",
      temperature: 0.82,
      max_tokens: 900,
      messages: [
        { role: "system", content: buildSystemPrompt(data) },
        ...messages,
      ],
    }),
  });
  return parseGatewayResponse(response);
}

async function callLovableCloudFunction(data: ChatInputValue, signal: AbortSignal) {
  const baseUrl = (
    process.env.SUPABASE_URL ||
    process.env.VITE_SUPABASE_URL ||
    FALLBACK_SUPABASE_URL
  ).replace(/\/$/, "");
  const publicKey =
    process.env.SUPABASE_PUBLISHABLE_KEY ||
    process.env.VITE_SUPABASE_PUBLISHABLE_KEY ||
    FALLBACK_SUPABASE_KEY;

  const response = await fetch(`${baseUrl}/functions/v1/furina-chat`, {
    method: "POST",
    signal,
    headers: {
      "Content-Type": "application/json",
      apikey: publicKey,
      Authorization: `Bearer ${publicKey}`,
    },
    body: JSON.stringify(data),
  });
  if (response.status === 404) return null;
  return parseGatewayResponse(response);
}

export const chatWithFurina = createServerFn({ method: "POST" })
  .inputValidator((value: unknown) => ChatInput.parse(value))
  .handler(async ({ data }) => {
    enforcePersonalRateLimit(data.clientKey);
    const messages = prepareMessages(data);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    try {
      const direct = await callLovableGateway(data, messages, controller.signal);
      if (direct) return direct;

      const cloud = await callLovableCloudFunction(data, controller.signal);
      if (cloud) return cloud;

      throw new Error(
        "Lovable AI belum tersambung ke backend deployment. Buka mode offline sementara atau hubungkan LOVABLE_API_KEY/Lovable Cloud.",
      );
    } catch (error) {
      if (controller.signal.aborted) {
        throw new Error("Lovable AI terlalu lama merespons. Periksa koneksi lalu coba lagi.");
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  });
