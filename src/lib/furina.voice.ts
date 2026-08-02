import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";

const GATEWAY = "https://ai.gateway.lovable.dev/v1/chat/completions";
const TTS_SYNTHESIS = "https://api.tts.quest/v3/voicevox/synthesis";
const MAX_WAIT_MS = 25_000;

export const VOICEVOX_SPEAKERS = [
  { id: 2, label: "Metan — Normal (anggun)" },
  { id: 0, label: "Metan — Manis" },
  { id: 6, label: "Metan — Ceria" },
  { id: 8, label: "Tsumugi — Ceria" },
  { id: 14, label: "Himari — Lembut" },
  { id: 20, label: "Mochiko — Dewasa" },
  { id: 3, label: "Zundamon — Normal" },
  { id: 1, label: "Zundamon — Manis" },
] as const;

const SpeakInput = z.object({
  text: z.string().min(1).max(600),
  speaker: z.number().int().min(0).max(120).default(2),
});

function hasJapanese(text: string) {
  return /[\u3040-\u30ff\u4e00-\u9faf]/.test(text);
}

function sanitize(text: string) {
  return text
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*_`#>|]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 400);
}

async function translateToJapanese(text: string) {
  const key = process.env["LOVABLE_API_KEY"]?.trim();
  if (!key) return text;
  try {
    const response = await fetch(GATEWAY, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Lovable-API-Key": key },
      body: JSON.stringify({
        model: "google/gemini-3.6-flash",
        temperature: 0.3,
        max_tokens: 400,
        messages: [
          {
            role: "system",
            content:
              "Terjemahkan teks pengguna ke bahasa Jepang lisan yang natural untuk dibacakan text-to-speech. Balas HANYA teks Jepangnya, tanpa romaji, tanpa penjelasan, tanpa tanda kutip.",
          },
          { role: "user", content: text },
        ],
      }),
    });
    if (!response.ok) return text;
    const json = (await response.json()) as { choices?: Array<{ message?: { content?: string } }> };
    const translated = String(json.choices?.[0]?.message?.content || "").trim();
    return translated || text;
  } catch {
    return text;
  }
}

async function waitForAudio(statusUrl: string) {
  const deadline = Date.now() + MAX_WAIT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(statusUrl, { cache: "no-store" });
      if (response.ok) {
        const status = (await response.json()) as { isAudioReady?: boolean; isAudioError?: boolean };
        if (status.isAudioReady) return true;
        if (status.isAudioError) return false;
      }
    } catch {
      // keep polling until the deadline
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
  return false;
}

/**
 * VOICEVOX melalui layanan publik tts.quest (gratis, tanpa API key).
 * Teks non-Jepang diterjemahkan lebih dulu supaya pelafalannya benar.
 */
export const speakWithVoicevox = createServerFn({ method: "POST" })
  .inputValidator((value: unknown) => SpeakInput.parse(value))
  .handler(async ({ data }) => {
    const cleaned = sanitize(data.text);
    if (!cleaned) throw new Error("Tidak ada teks yang bisa dibacakan.");

    const spoken = hasJapanese(cleaned) ? cleaned : await translateToJapanese(cleaned);
    const url = `${TTS_SYNTHESIS}?text=${encodeURIComponent(spoken.slice(0, 400))}&speaker=${data.speaker}`;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`Layanan VOICEVOX menolak permintaan (${response.status}).`);

    const json = (await response.json()) as {
      success?: boolean;
      errorMessage?: string;
      audioStatusUrl?: string;
      mp3DownloadUrl?: string;
      mp3StreamingUrl?: string;
      wavDownloadUrl?: string;
    };
    if (!json.success) throw new Error(json.errorMessage || "VOICEVOX gagal membuat suara.");

    const audioUrl = json.mp3StreamingUrl || json.mp3DownloadUrl || json.wavDownloadUrl;
    if (!audioUrl) throw new Error("VOICEVOX tidak mengembalikan tautan audio.");
    if (json.audioStatusUrl) {
      const ready = await waitForAudio(json.audioStatusUrl);
      if (!ready) throw new Error("Audio VOICEVOX terlalu lama disiapkan. Coba lagi.");
    }
    return { audioUrl, spoken };
  });
