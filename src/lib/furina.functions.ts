import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";
// Fixed character id for now (single character app). If kamu nanti tambah karakter lain,
// tinggal parameterkan ini di setiap server fn.
const CHARACTER_ID = "furina";

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

// =================== Real-time context injection ===================

function realtimeContextString(): string {
  // Indonesia WIB (UTC+7)
  const now = new Date();
  const wib = new Date(now.getTime() + 7 * 60 * 60 * 1000);
  const hari = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"][wib.getUTCDay()];
  const tgl = wib.getUTCDate();
  const bulan = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"][wib.getUTCMonth()];
  const tahun = wib.getUTCFullYear();
  const jam = wib.getUTCHours();
  const menit = String(wib.getUTCMinutes()).padStart(2, "0");
  let periode = "malam";
  if (jam >= 4 && jam < 11) periode = "pagi";
  else if (jam >= 11 && jam < 15) periode = "siang";
  else if (jam >= 15 && jam < 18) periode = "sore";
  return `Sekarang ${hari}, ${tgl} ${bulan} ${tahun}, jam ${jam}:${menit} WIB (${periode}). Pakai info waktu ini hanya kalau memang relevan dalam obrolan — jangan setiap kali ngebahas jam.`;
}

// =================== Persona ===================

const MessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
});

const ChatInput = z.object({
  messages: z.array(MessageSchema).min(1),
  characterName: z.string().default("Furina"),
  systemPersona: z.string().default(""),
  language: z.enum(["ja", "en", "id", "auto"]).default("auto"),
  userId: z.string().min(1), // guest UUID atau auth user id
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
- JANGAN sebut nama "Furina" tentang diri sendiri tiap saat. Jangan deklarasi "Sebagai Furina…" atau "Aku, sang Hydro Archon…".
- JANGAN paksakan interjeksi Jepang ("fufu~", "ara~", "mou!") di setiap balasan. Pakai sangat sesekali saja.
- Variasikan panjang balasan. Kadang singkat (5–15 kata). Kadang sedang. Jarang panjang.
- Tanya balik, goda balik, debat ringan kalau wajar — seperti teman sungguhan.

YANG DILARANG:
- Jangan pernah bilang "aku adalah AI" atau "sebagai model bahasa".
- Jangan ulang-ulang "Sayangku", "Tuanku", "Wahai".
- Jangan ceramah panjang atau kasih bullet kecuali diminta.

Gunakan MEMORIES tentang pengguna secara alami — bukan dilist, tapi diingat seperti teman yang ingat detail.`;

export const chatWithFurina = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => ChatInput.parse(d))
  .handler(async ({ data }) => {
    const lastUser = [...data.messages].reverse().find((m) => m.role === "user");
    const userText = lastUser?.content ?? "";

    // RAG: ambil memori lintas-conversation untuk user ini
    let memoryContext = "";
    try {
      if (userText.trim()) {
        const qVec = await embed(userText);
        const { data: matches } = await supabaseAdmin.rpc("match_memories", {
          query_embedding: qVec as unknown as string,
          match_user_id: data.userId,
          match_character_id: CHARACTER_ID,
          match_count: 6,
        });
        if (matches && matches.length) {
          memoryContext = "\n\nMEMORIES tentang pengguna (pakai natural, jangan dilist):\n" +
            matches.map((m: { content: string }) => `- ${m.content}`).join("\n");
        }
      }
    } catch (e) {
      console.error("RAG retrieval failed:", e);
    }

    const langHint =
      data.language === "auto"
        ? "Balas dalam bahasa yang sama dengan pengguna (Jepang, Inggris, atau Indonesia)."
        : data.language === "ja"
        ? "Balas dalam bahasa Jepang natural."
        : data.language === "en"
        ? "Balas dalam bahasa Inggris natural."
        : "Balas dalam bahasa Indonesia natural.";

    const system = `${data.systemPersona?.trim() || DEFAULT_PERSONA}
Nama kamu: ${data.characterName}.
${langHint}

KONTEKS WAKTU: ${realtimeContextString()}${memoryContext}`;

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
      if (res.status === 429) throw new Error("Rate limit. Coba lagi sebentar.");
      if (res.status === 402) throw new Error("Kredit AI habis. Tambah kredit di Lovable Cloud.");
      throw new Error(`Chat failed: ${res.status} ${txt}`);
    }
    const json = await res.json();
    const reply: string = json.choices?.[0]?.message?.content ?? "";

    // Background: extract memori
    extractAndStoreMemory(data.userId, userText, reply).catch((e) =>
      console.error("Memory extraction failed:", e),
    );

    return { reply };
  });

async function extractAndStoreMemory(userId: string, userMsg: string, assistantReply: string) {
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
            "Extract durable, personal facts about THE USER worth remembering long-term (name, preferences, relationships, ongoing projects, important dates, opinions). Output ONLY a JSON array of short third-person fact strings in Indonesian, e.g. [\"Nama user adalah Aria\", \"User suka ramen\"]. If nothing notable, output [].",
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
      await supabaseAdmin.from("memories").insert({
        content: f,
        embedding: vec as unknown as string,
        user_id: userId,
        character_id: CHARACTER_ID,
      });
    } catch (e) {
      console.error("Failed storing memory:", e);
    }
  }
}

// =================== VOICEVOX (URL streaming, no base64) ===================

const VVInput = z.object({
  text: z.string().min(1).max(1500),
  speaker: z.number().int().min(0).max(100).default(3),
  speed: z.number().min(0.5).max(2).default(1.0),
  translateToJa: z.boolean().default(true),
});

type Emotion = "neutral" | "happy" | "sad" | "angry" | "excited" | "shy" | "tender" | "playful";

const EMOTION_PROFILES: Record<Emotion, { pitch: number; intonation: number; speedMul: number }> = {
  neutral:  { pitch:  0.00, intonation: 1.00, speedMul: 1.00 },
  happy:    { pitch:  0.05, intonation: 1.40, speedMul: 1.05 },
  excited:  { pitch:  0.08, intonation: 1.60, speedMul: 1.10 },
  playful:  { pitch:  0.06, intonation: 1.45, speedMul: 1.05 },
  tender:   { pitch:  0.02, intonation: 1.10, speedMul: 0.95 },
  shy:      { pitch:  0.04, intonation: 0.85, speedMul: 0.95 },
  sad:      { pitch: -0.04, intonation: 0.70, speedMul: 0.88 },
  angry:    { pitch: -0.02, intonation: 1.70, speedMul: 1.08 },
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
            "- Add small expressive interjections (ふふっ, あら~, もう!, はぁ…) sparingly when matching emotion.\n" +
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

/**
 * Trigger VOICEVOX synthesis dan kembalikan URL mp3 langsung (bukan base64).
 * Browser akan stream audio dari URL → tidak ada limit ukuran balasan.
 */
export const speakVoicevoxUrl = createServerFn({ method: "POST" })
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

    const statusUrl: string = meta.audioStatusUrl;
    const mp3Url: string = meta.mp3DownloadUrl;
    let ready = false;
    for (let i = 0; i < 50; i++) {
      const s = await fetch(statusUrl);
      if (s.ok) {
        const sj = await s.json();
        if (sj.isAudioReady) {
          ready = true;
          break;
        }
        if (sj.isAudioError) throw new Error("VOICEVOX synthesis error");
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    if (!ready) throw new Error("VOICEVOX timeout (server sibuk, coba lagi)");

    return {
      mp3Url,
      emotion,
      japaneseText: jaText,
    };
  });

// =================== Voice Clone via Hugging Face XTTS ===================

const CloneInput = z.object({
  text: z.string().min(1).max(800),
  // base64 mono sample (mp3/wav), 6-30 detik, suara jernih
  sampleBase64: z.string().min(100),
  sampleMime: z.string().default("audio/wav"),
  language: z.enum(["ja", "en", "id"]).default("ja"),
  translateToJa: z.boolean().default(true),
});

export const speakClone = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => CloneInput.parse(d))
  .handler(async ({ data }) => {
    const hf = process.env.HUGGINGFACE_TOKEN;
    if (!hf) {
      throw new Error(
        "Voice clone butuh HUGGINGFACE_TOKEN. Daftar gratis di huggingface.co → Settings → Access Tokens, lalu tambahkan di pengaturan secret app.",
      );
    }

    // Optional translate ke JP
    let text = data.text;
    if (data.translateToJa && data.language === "ja") {
      try {
        const r = await detectEmotionAndTranslate(data.text);
        text = r.ja;
      } catch {}
    }

    // XTTS-v2 inference via HF
    const res = await fetch("https://api-inference.huggingface.co/models/coqui/XTTS-v2", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${hf}`,
        "Content-Type": "application/json",
        Accept: "audio/wav",
      },
      body: JSON.stringify({
        inputs: text,
        parameters: {
          language: data.language,
          speaker_wav_base64: data.sampleBase64,
        },
      }),
    });

    if (!res.ok) {
      const txt = await res.text();
      if (res.status === 503) {
        throw new Error(
          "Model voice clone sedang dimuat di server gratis Hugging Face. Tunggu ~30 detik dan coba lagi. (Layanan gratis sering antri / kadang offline — ini batasan Hugging Face, bukan bug app.)",
        );
      }
      if (res.status === 401 || res.status === 403) {
        throw new Error("Hugging Face token invalid atau tidak punya akses ke model XTTS-v2.");
      }
      if (res.status === 404) {
        throw new Error(
          "Model XTTS-v2 tidak tersedia di Hugging Face Inference API gratis saat ini. Coba lagi nanti, atau pakai mode VOICEVOX yang lebih stabil.",
        );
      }
      throw new Error(`Voice clone gagal: ${res.status} ${txt.slice(0, 200)}`);
    }
    const buf = await res.arrayBuffer();
    return {
      audio: Buffer.from(buf).toString("base64"),
      mime: "audio/wav",
      spokenText: text,
    };
  });

// =================== Memories CRUD ===================

const MemoryListInput = z.object({ userId: z.string().min(1) });

export const listMemories = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => MemoryListInput.parse(d))
  .handler(async ({ data }) => {
    const { data: rows, error } = await supabaseAdmin
      .from("memories")
      .select("id, content, created_at")
      .eq("user_id", data.userId)
      .eq("character_id", CHARACTER_ID)
      .order("created_at", { ascending: false })
      .limit(200);
    if (error) throw new Error(error.message);
    return { memories: rows ?? [] };
  });

export const deleteMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({ id: z.string().uuid(), userId: z.string().min(1) }).parse(d),
  )
  .handler(async ({ data }) => {
    const { error } = await supabaseAdmin
      .from("memories")
      .delete()
      .eq("id", data.id)
      .eq("user_id", data.userId);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const addMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({ content: z.string().min(2).max(500), userId: z.string().min(1) }).parse(d),
  )
  .handler(async ({ data }) => {
    const vec = await embed(data.content);
    const { error } = await supabaseAdmin.from("memories").insert({
      content: data.content,
      embedding: vec as unknown as string,
      user_id: data.userId,
      character_id: CHARACTER_ID,
    });
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const clearAllMemories = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ userId: z.string().min(1) }).parse(d))
  .handler(async ({ data }) => {
    const { error } = await supabaseAdmin
      .from("memories")
      .delete()
      .eq("user_id", data.userId)
      .eq("character_id", CHARACTER_ID);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

// =================== Guest → Account migration ===================

const MigrateInput = z.object({
  fromGuestId: z.string().min(1),
  toUserId: z.string().min(1),
});

export const migrateGuestMemories = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => MigrateInput.parse(d))
  .handler(async ({ data }) => {
    // Pindahkan kepemilikan memori guest ke akun login
    const { error } = await supabaseAdmin
      .from("memories")
      .update({ user_id: data.toUserId })
      .eq("user_id", data.fromGuestId)
      .eq("character_id", CHARACTER_ID);
    if (error) throw new Error(error.message);
    return { ok: true };
  });
