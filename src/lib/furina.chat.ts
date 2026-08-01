import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import profile from "../../shared/furina-profile.json";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";
const MAX_IMAGE_DATA = 8_000_000;

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

type RateState = { count: number; windowStartedAt: number };
const rateStates = new Map<string, RateState>();

function apiKey() {
  const key = process.env.LOVABLE_API_KEY;
  if (!key) throw new Error("Lovable AI belum terhubung di deployment ini.");
  return key;
}

function enforcePersonalRateLimit(key: string | undefined) {
  const safeKey = (key || "private-user").slice(0, 160);
  const now = Date.now();
  const previous = rateStates.get(safeKey);
  if (!previous || now - previous.windowStartedAt > 60_000) {
    rateStates.set(safeKey, { count: 1, windowStartedAt: now });
    return;
  }
  if (previous.count >= 20) throw new Error("Terlalu banyak pesan dalam satu menit. Tunggu sebentar.");
  previous.count += 1;
}

function languageInstruction(language: "auto" | "id" | "en" | "ja") {
  if (language === "id") return "Selalu balas dalam bahasa Indonesia.";
  if (language === "en") return "Always reply in natural English.";
  if (language === "ja") return "常に自然な日本語で返答してください。";
  return "Balas menggunakan bahasa yang dipakai pengguna pada pesan terakhir.";
}

function localTimeContext(timestamp?: number, timeZone?: string) {
  const date = new Date(timestamp || Date.now());
  try {
    const formatted = new Intl.DateTimeFormat("id-ID", {
      timeZone: timeZone || "Asia/Jakarta",
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
    return `Waktu lokal pengguna kira-kira ${formatted}. Singgung waktu hanya jika relevan.`;
  } catch {
    return "Sesuaikan pembicaraan dengan waktu lokal pengguna bila konteksnya jelas.";
  }
}

function buildSystemPrompt(input: z.infer<typeof ChatInput>) {
  const memoryLines = input.sharedMemories
    .map((memory) => memory.trim())
    .filter(Boolean)
    .slice(-24)
    .map((memory) => `- ${memory}`)
    .join("\n");

  const sections = [
    profile.systemPrompt,
    `Nama karakter yang digunakan: ${input.characterName.trim() || profile.name}.`,
    languageInstruction(input.language),
    localTimeContext(input.clientNow, input.timeZone),
  ];

  if (input.persona.trim()) {
    sections.push(`PERSONA TAMBAHAN DARI PENGGUNA:\n${input.persona.trim()}`);
  }
  if (memoryLines) {
    sections.push(`${profile.memoryInstruction}\n${memoryLines}`);
  }
  return sections.join("\n\n").slice(0, 24_000);
}

function splitBubbles(reply: string) {
  const bubbles = reply
    .split(/\s*<<<\s*SPLIT\s*>>>\s*/i)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 3);
  return bubbles.length ? bubbles : [reply.trim() || "…"];
}

export const chatWithFurina = createServerFn({ method: "POST" })
  .inputValidator((value: unknown) => ChatInput.parse(value))
  .handler(async ({ data }) => {
    enforcePersonalRateLimit(data.clientKey);

    const sourceMessages = data.messages.slice(-20);
    const last = sourceMessages[sourceMessages.length - 1];
    const messages: Array<{ role: string; content: unknown }> = sourceMessages
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

    const response = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Lovable-API-Key": apiKey(),
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

    if (!response.ok) {
      const details = await response.text();
      if (response.status === 429) throw new Error("Lovable AI sedang mencapai batas permintaan. Coba lagi sebentar.");
      if (response.status === 402) throw new Error("Kredit Lovable AI habis.");
      throw new Error(`Lovable AI gagal merespons (${response.status}): ${details.slice(0, 240)}`);
    }

    const json = await response.json();
    const reply = String(json.choices?.[0]?.message?.content || "").trim();
    const bubbles = splitBubbles(reply);
    return { reply: bubbles.join("\n\n"), bubbles };
  });
