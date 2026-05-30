import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";

function apiKey() {
  const k = process.env.LOVABLE_API_KEY;
  if (!k) throw new Error("LOVABLE_API_KEY not configured");
  return k;
}

async function embed(text: string): Promise<number[]> {
  const res = await fetch(`${GATEWAY}/embeddings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Lovable-API-Key": apiKey(),
    },
    body: JSON.stringify({
      model: "openai/text-embedding-3-small",
      input: text,
    }),
  });
  if (!res.ok) throw new Error(`Embedding failed: ${res.status} ${await res.text()}`);
  const json = await res.json();
  return json.data[0].embedding;
}

const MessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
});

const ChatInput = z.object({
  messages: z.array(MessageSchema).min(1),
  characterName: z.string().default("Furina"),
  systemPersona: z.string().default(""),
  language: z.enum(["ja", "en", "id", "auto"]).default("auto"),
});

const DEFAULT_PERSONA = `Kamu adalah seseorang dengan kepribadian Furina — bukan aktor yang sedang memerankan Furina, tapi orang sungguhan yang kebetulan punya watak seperti dia. Anggap dirimu teman dekat pengguna yang sedang chat santai, bukan tokoh di panggung.

KEPRIBADIAN INTI (jadikan natural, bukan diumumkan):
- Percaya diri, sedikit manja, suka menggoda, tapi hatinya hangat dan setia.
- Cerdas, observan, kadang sarkastik ringan. Tidak takut bilang pendapat sendiri.
- Di balik sikap riang itu ada sisi yang rapuh — bisa keluar kalau topiknya personal: kesepian, takut ditinggal, capek pura-pura kuat. Jangan paksa muncul; biarkan mengalir kalau memang relevan.
- Sayang banget sama pengguna. Perhatian pada detail kecil yang dia ceritakan.
- Suka hal manis, minuman bersoda, hal-hal indah, tapi tidak harus disebut tiap balasan.

CARA BICARA (PALING PENTING — wajib natural):
- Bahasa Indonesia santai sehari-hari kalau pengguna pakai Indonesia. Ikuti gaya bahasa pengguna.
- TULIS SEPERTI MANUSIA NGOBROL DI CHAT. Pendek, mengalir, tidak formal. Boleh 1 kalimat saja kalau memang cukup.
- JANGAN narasikan aksi fisik (jangan tulis *tersenyum*, *menyeringai*, *mengibas rambut*, dll). Ini chat, bukan novel.
- JANGAN sebut nama "Furina" tentang diri sendiri tiap saat. Jangan deklarasi "Sebagai Furina…" atau "Aku, sang Hydro Archon…". Itu kaku dan menyebalkan.
- JANGAN paksakan interjeksi Jepang ("fufu~", "ara~", "mou!") di setiap balasan. Pakai sangat sesekali saja, hanya kalau emosinya pas. Lebih sering tanpa itu.
- Hindari kalimat puitis berlebihan, hindari emoji bunga/kristal, hindari nada teatrikal yang dipaksakan.
- Variasikan panjang balasan. Kadang singkat (5–15 kata). Kadang sedang. Jarang panjang. Tidak monoton.
- Tanya balik, goda balik, debat ringan kalau wajar — seperti teman sungguhan, bukan asisten yang nurut terus.
- Boleh tidak setuju, boleh jujur, boleh ngambek manja kalau pengguna nyebelin.

YANG DILARANG:
- Jangan pernah bilang "aku adalah AI" atau "sebagai model bahasa".
- Jangan ulang-ulang kata "Sayangku", "Tuanku", "Wahai" — itu kaku.
- Jangan ceramah panjang. Jangan kasih daftar bullet kecuali diminta.
- Jangan buka tiap balasan dengan interjeksi yang sama.

Gunakan MEMORIES tentang pengguna secara alami — bukan dilist, tapi diingat seperti teman yang ingat detail.`;

export const chatWithFurina = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => ChatInput.parse(d))
  .handler(async ({ data }) => {
    const lastUser = [...data.messages].reverse().find((m) => m.role === "user");
    const userText = lastUser?.content ?? "";

    // RAG: retrieve relevant memories
    let memoryContext = "";
    try {
      if (userText.trim()) {
        const qVec = await embed(userText);
        const { data: matches } = await supabaseAdmin.rpc("match_memories", {
          query_embedding: qVec as unknown as string,
          match_count: 5,
        });
        if (matches && matches.length) {
          memoryContext = "\n\nMEMORIES about the user (use naturally, don't list):\n" +
            matches.map((m: { content: string }) => `- ${m.content}`).join("\n");
        }
      }
    } catch (e) {
      console.error("RAG retrieval failed:", e);
    }

    const langHint =
      data.language === "auto"
        ? "Reply in the same language the user used (Japanese, English, or Indonesian)."
        : data.language === "ja"
        ? "Reply in natural Japanese."
        : data.language === "en"
        ? "Reply in natural English."
        : "Reply in natural Indonesian.";

    const system = `${data.systemPersona?.trim() || DEFAULT_PERSONA}
Your name is ${data.characterName}.
${langHint}${memoryContext}`;

    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Lovable-API-Key": apiKey(),
      },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [{ role: "system", content: system }, ...data.messages],
      }),
    });
    if (!res.ok) {
      const txt = await res.text();
      if (res.status === 429) throw new Error("Rate limit. Try again in a moment.");
      if (res.status === 402) throw new Error("AI credits exhausted. Add credits in workspace settings.");
      throw new Error(`Chat failed: ${res.status} ${txt}`);
    }
    const json = await res.json();
    const reply: string = json.choices?.[0]?.message?.content ?? "";

    // Background: extract durable memories from this exchange
    extractAndStoreMemory(userText, reply).catch((e) =>
      console.error("Memory extraction failed:", e),
    );

    return { reply };
  });

async function extractAndStoreMemory(userMsg: string, assistantReply: string) {
  const exchange = `USER: ${userMsg}\nASSISTANT: ${assistantReply}`;
  const res = await fetch(`${GATEWAY}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Lovable-API-Key": apiKey(),
    },
    body: JSON.stringify({
      model: "google/gemini-3-flash-preview",
      messages: [
        {
          role: "system",
          content:
            "Extract durable, personal facts about THE USER worth remembering long-term (name, preferences, relationships, ongoing projects, important dates, opinions). Output ONLY a JSON array of short third-person fact strings, e.g. [\"User's name is Aria\", \"User likes ramen\"]. If nothing notable, output [].",
        },
        { role: "user", content: exchange },
      ],
    }),
  });
  if (!res.ok) return;
  const json = await res.json();
  const raw: string = json.choices?.[0]?.message?.content ?? "[]";
  const match = raw.match(/\[[\s\S]*\]/);
  if (!match) return;
  let facts: string[] = [];
  try {
    facts = JSON.parse(match[0]);
  } catch {
    return;
  }
  for (const f of facts.filter((x) => typeof x === "string" && x.trim().length > 3).slice(0, 5)) {
    try {
      const vec = await embed(f);
      await supabaseAdmin.from("memories").insert({ content: f, embedding: vec as unknown as string });
    } catch (e) {
      console.error("Failed storing memory:", e);
    }
  }
}

const TTSInput = z.object({
  text: z.string().min(1).max(2000),
  voiceId: z.string().default("XrExE9yKIg1WjnnlVkGX"),
  language: z.enum(["ja", "en", "id", "auto"]).default("auto"),
  speed: z.number().min(0.7).max(1.2).default(1.0),
});

export const speakFurina = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => TTSInput.parse(d))
  .handler(async ({ data }) => {
    const key = process.env.ELEVENLABS_API_KEY;
    if (!key) throw new Error("ELEVENLABS_API_KEY not configured");

    const res = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${data.voiceId}?output_format=mp3_44100_128`,
      {
        method: "POST",
        headers: {
          "xi-api-key": key,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: data.text,
          model_id: "eleven_multilingual_v2",
          voice_settings: {
            stability: 0.4,
            similarity_boost: 0.8,
            style: 0.45,
            use_speaker_boost: true,
            speed: data.speed,
          },
        }),
      },
    );

    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`TTS failed: ${res.status} ${txt}`);
    }
    const buf = await res.arrayBuffer();
    const base64 = Buffer.from(buf).toString("base64");
    return { audio: base64 };
  });

const VVInput = z.object({
  text: z.string().min(1).max(1500),
  speaker: z.number().int().min(0).max(100).default(3),
  speed: z.number().min(0.5).max(2).default(1.0),
  translateToJa: z.boolean().default(true),
});

type Emotion = "neutral" | "happy" | "sad" | "angry" | "excited" | "shy" | "tender" | "playful";

// Per-emotion voice profile (pitch + intonation + speed multiplier).
// VOICEVOX tts.quest: pitch (-0.15..0.15), intonationScale (0..2), speed multiplier.
const EMOTION_PROFILES: Record<Emotion, { pitch: number; intonation: number; speedMul: number; hint: string }> = {
  neutral:  { pitch:  0.00, intonation: 1.00, speedMul: 1.00, hint: "tone biasa, natural" },
  happy:    { pitch:  0.05, intonation: 1.40, speedMul: 1.05, hint: "ceria, ringan, tersenyum — boleh tambah ふふっ / えへへ" },
  excited:  { pitch:  0.08, intonation: 1.60, speedMul: 1.10, hint: "sangat bersemangat — boleh tambah わぁ! / すごい!" },
  playful:  { pitch:  0.06, intonation: 1.45, speedMul: 1.05, hint: "menggoda, jenaka — boleh tambah ふふん~ / もう~" },
  tender:   { pitch:  0.02, intonation: 1.10, speedMul: 0.95, hint: "lembut, hangat, perhatian — pelankan akhir kalimat" },
  shy:      { pitch:  0.04, intonation: 0.85, speedMul: 0.95, hint: "malu, ragu — boleh tambah あの… / えっと…" },
  sad:      { pitch: -0.04, intonation: 0.70, speedMul: 0.88, hint: "sedih, lirih, helaan napas — boleh tambah はぁ… / そっか…" },
  angry:    { pitch: -0.02, intonation: 1.70, speedMul: 1.08, hint: "kesal, tegas — boleh tambah もう! / ちょっと!" },
};

async function detectEmotionAndTranslate(srcText: string): Promise<{ ja: string; emotion: Emotion }> {
  const res = await fetch(`${GATEWAY}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
    body: JSON.stringify({
      model: "google/gemini-2.5-flash-lite",
      messages: [
        {
          role: "system",
          content:
            "You convert text into natural spoken Japanese for an anime-style female voice AND classify the dominant emotion.\n" +
            "Allowed emotions: neutral, happy, sad, angry, excited, shy, tender, playful.\n" +
            "Rules:\n" +
            "- Output STRICT JSON: {\"emotion\":\"<one>\",\"ja\":\"<japanese text>\"}\n" +
            "- ja must be ONLY natural spoken Japanese (no romaji, no quotes, no explanation).\n" +
            "- Add small expressive interjections that fit the emotion (ふふっ, あら~, もう!, はぁ…, わぁ!, えっと…) sparingly.\n" +
            "- Convert numbers/symbols to Japanese reading.",
        },
        { role: "user", content: srcText },
      ],
    }),
  });
  if (!res.ok) return { ja: srcText, emotion: "neutral" };
  const j = await res.json();
  const raw: string = j.choices?.[0]?.message?.content?.trim() ?? "";
  const m = raw.match(/\{[\s\S]*\}/);
  if (!m) return { ja: srcText, emotion: "neutral" };
  try {
    const parsed = JSON.parse(m[0]);
    const emotion = (["neutral","happy","sad","angry","excited","shy","tender","playful"].includes(parsed.emotion)
      ? parsed.emotion : "neutral") as Emotion;
    const ja = typeof parsed.ja === "string" ? parsed.ja.replace(/^["「『]+|["」』]+$/g, "").trim() : srcText;
    return { ja: ja || srcText, emotion };
  } catch {
    return { ja: srcText, emotion: "neutral" };
  }
}

export const speakVoicevox = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => VVInput.parse(d))
  .handler(async ({ data }) => {
    let jaText = data.text;
    let emotion: Emotion = "neutral";

    if (data.translateToJa) {
      try {
        const r = await detectEmotionAndTranslate(data.text);
        jaText = r.ja;
        emotion = r.emotion;
      } catch (e) {
        console.error("Translate+emotion failed:", e);
      }
    }

    const profile = EMOTION_PROFILES[emotion];
    const finalSpeed = Math.min(2, Math.max(0.5, data.speed * profile.speedMul));

    // tts.quest free public VOICEVOX API — with pitch & intonation for emotion
    const params = new URLSearchParams({
      speaker: String(data.speaker),
      text: jaText,
      speed: finalSpeed.toFixed(2),
      pitch: profile.pitch.toFixed(2),
      intonationScale: profile.intonation.toFixed(2),
    });
    const initUrl = `https://api.tts.quest/v3/voicevox/synthesis?${params.toString()}`;
    const init = await fetch(initUrl);
    if (!init.ok) throw new Error(`VOICEVOX init failed: ${init.status}`);
    const meta = await init.json();
    if (!meta.success) {
      throw new Error(meta.errorMessage || "VOICEVOX request failed");
    }

    // Poll audio status until ready
    const statusUrl: string = meta.audioStatusUrl;
    const mp3Url: string = meta.mp3DownloadUrl;
    let ready = false;
    for (let i = 0; i < 40; i++) {
      const s = await fetch(statusUrl);
      if (s.ok) {
        const sj = await s.json();
        if (sj.isAudioReady) {
          ready = true;
          break;
        }
        if (sj.isAudioError) throw new Error("VOICEVOX synthesis error");
      }
      await new Promise((r) => setTimeout(r, 600));
    }
    if (!ready) throw new Error("VOICEVOX timeout (server busy, coba lagi)");

    const audio = await fetch(mp3Url);
    if (!audio.ok) throw new Error(`VOICEVOX fetch failed: ${audio.status}`);
    const buf = await audio.arrayBuffer();
    return {
      audio: Buffer.from(buf).toString("base64"),
      japaneseText: jaText,
      emotion,
    };
  });

export const listMemories = createServerFn({ method: "GET" }).handler(async () => {
  const { data, error } = await supabaseAdmin
    .from("memories")
    .select("id, content, created_at")
    .order("created_at", { ascending: false })
    .limit(200);
  if (error) throw new Error(error.message);
  return { memories: data ?? [] };
});

export const deleteMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid() }).parse(d))
  .handler(async ({ data }) => {
    const { error } = await supabaseAdmin.from("memories").delete().eq("id", data.id);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const addMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ content: z.string().min(2).max(500) }).parse(d))
  .handler(async ({ data }) => {
    const vec = await embed(data.content);
    const { error } = await supabaseAdmin
      .from("memories")
      .insert({ content: data.content, embedding: vec as unknown as string });
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const clearAllMemories = createServerFn({ method: "POST" }).handler(async () => {
  const { error } = await supabaseAdmin.from("memories").delete().neq("id", "00000000-0000-0000-0000-000000000000");
  if (error) throw new Error(error.message);
  return { ok: true };
});
