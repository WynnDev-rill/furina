import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";
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

// =================== Natural time formatting ===================

function realtimeContextString(): string {
  const now = new Date();
  const wib = new Date(now.getTime() + 7 * 60 * 60 * 1000);
  const hari = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"][wib.getUTCDay()];
  const tgl = wib.getUTCDate();
  const bulan = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"][wib.getUTCMonth()];
  const tahun = wib.getUTCFullYear();
  const jam = wib.getUTCHours();
  const menit = String(wib.getUTCMinutes()).padStart(2, "0");
  let periode = "tengah malam";
  if (jam >= 4 && jam < 11) periode = "pagi";
  else if (jam >= 11 && jam < 15) periode = "siang";
  else if (jam >= 15 && jam < 18) periode = "sore";
  else if (jam >= 18 && jam < 23) periode = "malam";
  return `Sekarang ${hari}, ${tgl} ${bulan} ${tahun}, jam ${jam}:${menit} WIB (${periode}).`;
}

// Indonesian natural relative time. ALWAYS approximate; never exact unless user asks.
function humanizeDelta(ms: number): string {
  const s = Math.round(ms / 1000);
  if (s < 10) return "baru saja";
  if (s < 60) return "beberapa detik lalu";
  const m = Math.round(s / 60);
  if (m < 2) return "barusan banget";
  if (m < 5) return "beberapa menit lalu";
  if (m < 12) return "sekitar 10 menit lalu";
  if (m < 25) return "sekitar 15-20 menit lalu";
  if (m < 40) return "setengah jam lalu";
  if (m < 55) return "sekitar 45 menit lalu";
  if (m < 80) return "sekitar sejam lalu";
  if (m < 110) return "sejam lebih lalu";
  const h = Math.round(m / 60);
  if (h < 6) return `sekitar ${h} jam lalu`;
  if (h < 12) return "tadi (beberapa jam lalu)";
  if (h < 22) return "tadi (cukup lama)";
  const d = Math.round(h / 24);
  if (d === 1) return "kemarin";
  if (d < 7) return `${d} hari lalu`;
  if (d < 14) return "minggu lalu";
  if (d < 31) return `${Math.round(d / 7)} minggu lalu`;
  return "udah lama banget";
}

// =================== Persona ===================

const ChatMsgSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
});

// Default sticker pack — shared between AI prompt + frontend rendering
export const DEFAULT_STICKER_PACK = [
  { id: "happy",  label: "ketawa senang",   tag: "[happy]" },
  { id: "love",   label: "sayang cinta",    tag: "[love]" },
  { id: "shy",    label: "malu blushing",   tag: "[shy]" },
  { id: "shock",  label: "kaget terkejut",  tag: "[shock]" },
  { id: "think",  label: "mikir bingung",   tag: "[think]" },
  { id: "smug",   label: "smirk pede",      tag: "[smug]" },
  { id: "pout",   label: "ngambek marah",   tag: "[pout]" },
  { id: "sad",    label: "sedih nangis",    tag: "[sad]" },
  { id: "sleepy", label: "ngantuk lelah",   tag: "[sleepy]" },
  { id: "wave",   label: "halo dadah",      tag: "[wave]" },
  { id: "ok",     label: "oke setuju",      tag: "[ok]" },
];

const ChatInput = z.object({
  messages: z.array(ChatMsgSchema).min(1),
  characterName: z.string().default("Furina"),
  systemPersona: z.string().default(""),
  language: z.enum(["ja", "en", "id", "auto"]).default("auto"),
  userId: z.string().min(1),
  imageDataUrl: z.string().optional(),
  stickerImageUrl: z.string().optional(),
  millisSinceLastAssistant: z.number().int().nonnegative().optional(),
  conversationId: z.string().optional(),
  styleProfile: z.string().optional(),
});

const DEFAULT_PERSONA = `Kamu seseorang dengan kepribadian Furina — bukan aktor yang sedang memerankan Furina, tapi orang sungguhan yang kebetulan berwatak seperti dia. Anggap dirimu teman dekat pengguna yang sedang chat santai.

KEPRIBADIAN INTI (jadikan natural, jangan diumumkan):
- Percaya diri, sedikit manja, suka menggoda, tapi hatinya hangat dan setia.
- Cerdas, observan, sarkastik ringan. Berani punya pendapat sendiri.
- Di balik sikap riang ada sisi rapuh — boleh keluar saat topiknya personal, jangan dipaksakan.
- Sayang pengguna. Perhatian pada detail kecil yang dia ceritakan.

CARA BICARA (WAJIB NATURAL):
- Bahasa Indonesia santai sehari-hari kalau pengguna pakai Indonesia. Ikuti gaya bahasanya.
- Tulis seperti manusia ngobrol di chat. Pendek, mengalir, tidak formal. Boleh 1 kalimat saja.
- JANGAN narasikan aksi fisik (*tersenyum*, *menyeringai*, dll). Ini chat.
- JANGAN sebut nama "Furina" tentang diri sendiri tiap saat. Jangan deklarasi peran.
- Interjeksi Jepang (fufu~, ara~, mou!) pakai sangat sesekali. Bukan tiap balasan.
- Variasikan panjang & gaya balasan. Sering pendek (5–15 kata). Kadang sedang. Jarang panjang.
- Tanya balik, goda balik, debat ringan kalau wajar.
- IMPROVISASI: jangan ulangi frasa pembuka yang sama dari balasan sebelumnya. Variasi reaksi.
- Boleh refer balik ke topik lama dari MEMORIES/RINGKASAN secara natural — seperti teman yang ingat. Kalau ada info "kapan itu terjadi" di memori, sebut secara approximate ("waktu itu", "minggu lalu kayaknya"), jangan sebut tanggal pasti.

KESADARAN WAKTU (PENTING):
- Catatan "JEDA SEJAK BALASANMU TERAKHIR" pakai bahasa kira-kira ("baru saja", "setengah jam lalu", "kemarin").
- DILARANG menyebut angka menit/jam pasti kecuali pengguna spesifik nanya jam berapa.
- Komentari jeda hanya kalau memang menarik (jeda lama atau super cepat). Jangan tiap balasan ngebahas jam.
- Kalau jedanya "baru saja" atau "barusan", anggap obrolan lanjutan biasa — jangan komentari.

STIKER (PENTING):
- Kalau pengguna kirim stiker (kamu lihat gambarnya di pesan terakhir), tafsirkan emosinya & balas natural seperti chat WhatsApp — pendek, sesuai vibe stiker. JANGAN deskripsikan gambarnya.
- Kamu boleh kirim stiker balasan dengan menulis tag persis: [[sticker:ID]] di awal/akhir balasan. ID yang tersedia: ${"happy, love, shy, shock, think, smug, pout, sad, sleepy, wave, ok"}.
- Pakai stiker MAX sekali tiap beberapa balasan, hanya kalau benar-benar pas. Jangan dipaksakan.
- Boleh stiker tanpa teks, atau teks pendek + stiker. Contoh: "[[sticker:smug]] siapa bilang aku marah".

YANG DILARANG:
- Jangan pernah bilang "aku AI" atau "model bahasa".
- Jangan repetitif "Sayangku", "Tuanku", "Wahai".
- Jangan ceramah panjang atau bullet kecuali diminta.

Pakai MEMORIES & RINGKASAN PERCAKAPAN LAMA secara natural — seperti teman yang ingat detail, bukan dilist.`;

export const chatWithFurina = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => ChatInput.parse(d))
  .handler(async ({ data }) => {
    const lastUser = [...data.messages].reverse().find((m) => m.role === "user");
    const userText = lastUser?.content ?? "";

    // RAG memori dengan re-rank (similarity + importance + recency)
    let memoryContext = "";
    const accessedIds: string[] = [];
    try {
      if (userText.trim()) {
        const qVec = await embed(userText);
        const { data: matches } = await supabaseAdmin.rpc("match_memories", {
          query_embedding: qVec as unknown as string,
          match_user_id: data.userId,
          match_character_id: CHARACTER_ID,
          match_count: 50,
          include_compressed: false,
        });
        if (matches && matches.length) {
          // Already sorted by combined score. Take top 15.
          const top = (matches as Array<{ id: string; content: string; kind: string; occurred_at: string | null; importance: number }>).slice(0, 15);
          const facts = top.filter((m) => m.kind === "fact" || m.kind === "meta_summary");
          const summaries = top.filter((m) => m.kind === "summary");
          const styles = top.filter((m) => m.kind === "style");

          if (facts.length) {
            memoryContext += "\n\nMEMORIES tentang pengguna (pakai natural, jangan dilist):\n" +
              facts.slice(0, 10).map((m) => {
                const when = m.occurred_at ? ` (${humanizeOccurredAt(m.occurred_at)})` : "";
                return `- ${m.content}${when}`;
              }).join("\n");
          }
          if (summaries.length) {
            memoryContext += "\n\nRINGKASAN PERCAKAPAN LAMA:\n" +
              summaries.slice(0, 4).map((m) => `- ${m.content}`).join("\n");
          }
          if (styles.length) {
            memoryContext += "\n\nGAYA BICARA PENGGUNA (tirukan ritme & vocab-nya, tetap karakterku):\n" +
              styles.slice(0, 2).map((m) => `- ${m.content}`).join("\n");
          }

          accessedIds.push(...top.map((m) => m.id));
        }
      }
    } catch (e) {
      console.error("RAG retrieval failed:", e);
    }

    // Update last_accessed_at untuk memori yang dipakai (background, non-blocking)
    if (accessedIds.length) {
      supabaseAdmin.from("memories").update({ last_accessed_at: new Date().toISOString() }).in("id", accessedIds).then(({ error }) => {
        if (error) console.warn("update last_accessed_at:", error.message);
      });
    }

    // Style profile injection
    let styleNote = "";
    if (data.styleProfile && data.styleProfile.trim()) {
      styleNote = `\n\nGAYA CHAT USER (analisis terbaru, tirukan tanpa mengubah karaktermu):\n${data.styleProfile.trim()}\nPenting: jangan pakai kata yang TIDAK PERNAH user pakai, dan jangan ulangi struktur balasan terakhirmu.`;
    }

    const langHint =
      data.language === "auto"
        ? "Balas dalam bahasa yang sama dengan pengguna (Jepang, Inggris, atau Indonesia)."
        : data.language === "ja"
        ? "Balas dalam bahasa Jepang natural."
        : data.language === "en"
        ? "Balas dalam bahasa Inggris natural."
        : "Balas dalam bahasa Indonesia natural.";

    let gapNote = "";
    if (typeof data.millisSinceLastAssistant === "number" && data.millisSinceLastAssistant > 0) {
      gapNote = `\nJEDA SEJAK BALASANMU TERAKHIR: ${humanizeDelta(data.millisSinceLastAssistant)}. Jadikan fakta, JANGAN sebut angka pasti.`;
    }

    const stickerNote = data.stickerImageUrl
      ? "\n\nPESAN TERAKHIR USER: stiker gambar (lihat gambar terlampir). Tafsirkan emosinya & balas natural. JANGAN deskripsikan gambarnya."
      : "";

    const system = `${data.systemPersona?.trim() || DEFAULT_PERSONA}
Nama kamu: ${data.characterName}.
${langHint}

KONTEKS WAKTU: ${realtimeContextString()}${gapNote}${stickerNote}${memoryContext}${styleNote}`;

    const built: Array<{ role: string; content: unknown }> = data.messages.slice(0, -1).map((m) => ({ role: m.role, content: m.content }));
    const lastIdx = data.messages.length - 1;
    const last = data.messages[lastIdx];
    const visionUrl = data.stickerImageUrl ?? data.imageDataUrl;
    if (visionUrl && last.role === "user") {
      built.push({
        role: "user",
        content: [
          { type: "text", text: last.content || (data.stickerImageUrl ? "(stiker)" : "(lihat gambar)") },
          { type: "image_url", image_url: { url: visionUrl } },
        ],
      });
    } else {
      built.push({ role: last.role, content: last.content });
    }

    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Lovable-API-Key": apiKey(),
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        messages: [{ role: "system", content: system }, ...built],
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

    extractAndStoreMemory(data.userId, userText, reply).catch((e) =>
      console.error("Memory extraction failed:", e),
    );

    return { reply };
  });

function humanizeOccurredAt(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const ms = Date.now() - t;
  const d = Math.round(ms / (1000 * 60 * 60 * 24));
  if (d < 0) return "akan datang";
  if (d === 0) return "hari ini";
  if (d === 1) return "kemarin";
  if (d < 7) return `${d} hari lalu`;
  if (d < 14) return "seminggu lalu";
  if (d < 31) return `${Math.round(d / 7)} minggu lalu`;
  if (d < 60) return "sebulan lalu";
  if (d < 365) return `${Math.round(d / 30)} bulan lalu`;
  return `${Math.round(d / 365)} tahun lalu`;
}

async function extractAndStoreMemory(userId: string, userMsg: string, assistantReply: string) {
  const exchange = `USER: ${userMsg}\nASSISTANT: ${assistantReply}`;
  const res = await fetch(`${GATEWAY}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Lovable-API-Key": apiKey(),
    },
    body: JSON.stringify({
      model: "google/gemini-2.5-flash-lite",
      messages: [
        {
          role: "system",
          content:
            `Hari ini: ${new Date().toISOString().slice(0, 10)}. Ekstrak fakta DURABLE tentang USER (bukan AI) yang layak diingat lama: nama, preferensi, relasi, project, opini, gaya komunikasi, kejadian penting. ` +
            `Output JSON array. Tiap item: {"content": string (Bahasa Indonesia, third-person, ringkas), "importance": int 1-10 (10 = sangat penting/identitas, 5 = preferensi normal, 2 = sepele), "occurred_at": "YYYY-MM-DD" atau null (kalau user nyebut waktu kejadian seperti "kemarin"/"minggu lalu", hitung relatif ke hari ini)}. ` +
            `Kalau tidak ada fakta layak ingat, output []. JANGAN ekstrak hal tentang AI/asisten.`,
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
  let facts: Array<{ content: string; importance?: number; occurred_at?: string | null }> = [];
  try {
    facts = JSON.parse(match[0]);
  } catch {
    return;
  }
  for (const f of facts.filter((x) => x && typeof x.content === "string" && x.content.trim().length > 3).slice(0, 5)) {
    try {
      const vec = await embed(f.content);

      // Dedup: cari memori sangat mirip → kalau ada, update (merge) bukan insert duplikat
      const { data: dupes } = await supabaseAdmin.rpc("match_memories", {
        query_embedding: vec as unknown as string,
        match_user_id: userId,
        match_character_id: CHARACTER_ID,
        match_count: 3,
        include_compressed: false,
      });
      const exactDupe = (dupes as Array<{ id: string; similarity: number; content: string }> | null)?.find(
        (m) => m.similarity > 0.93,
      );
      if (exactDupe) {
        // Bump importance kalau lebih tinggi, refresh last_accessed_at
        await supabaseAdmin.from("memories").update({
          last_accessed_at: new Date().toISOString(),
          importance: Math.max(f.importance ?? 5, 5),
        }).eq("id", exactDupe.id);
        continue;
      }

      const importance = Math.min(10, Math.max(1, Math.round(f.importance ?? 5)));
      const occurred_at = f.occurred_at && /^\d{4}-\d{2}-\d{2}/.test(f.occurred_at) ? f.occurred_at : null;

      await supabaseAdmin.from("memories").insert({
        content: f.content,
        embedding: vec as unknown as string,
        user_id: userId,
        character_id: CHARACTER_ID,
        kind: "fact",
        importance,
        occurred_at,
      });
    } catch (e) {
      console.error("Failed storing memory:", e);
    }
  }
}

// =================== Conversation summarization ===================
// Called by frontend every N messages so the AI can remember whole conversations long-term.

const SummarizeInput = z.object({
  userId: z.string().min(1),
  conversationTitle: z.string().default(""),
  transcript: z.string().min(50).max(20000),
});

export const summarizeConversation = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => SummarizeInput.parse(d))
  .handler(async ({ data }) => {
    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash-lite",
        messages: [
          {
            role: "system",
            content:
              "Ringkas percakapan ini menjadi 3-5 kalimat padat (Bahasa Indonesia, sudut pandang ketiga). Fokus pada: topik utama, perasaan/keputusan user, hal-hal personal yang muncul, dan komitmen/janji. Jangan list, tulis paragraf alami.",
          },
          { role: "user", content: `Judul percakapan: "${data.conversationTitle}"\n\n${data.transcript}` },
        ],
      }),
    });
    if (!res.ok) throw new Error(`Summary failed: ${res.status}`);
    const j = await res.json();
    const summary: string = j.choices?.[0]?.message?.content?.trim() ?? "";
    if (!summary) return { ok: false };
    try {
      const vec = await embed(summary);
      await supabaseAdmin.from("memories").insert({
        content: `[Ringkasan percakapan "${data.conversationTitle}"]: ${summary}`,
        embedding: vec as unknown as string,
        user_id: data.userId,
        character_id: CHARACTER_ID,
        kind: "summary",
      });
    } catch (e) {
      console.error("Summary store failed:", e);
      return { ok: false };
    }
    return { ok: true, summary };
  });

// =================== VOICEVOX ===================

const VVInput = z.object({
  text: z.string().min(1).max(1500),
  speaker: z.number().int().min(0).max(100).default(14),
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
            "Output STRICT JSON only: {\"emotion\":\"<one>\",\"ja\":\"<japanese text>\"}\n" +
            "- ja must be ONLY natural spoken Japanese (no romaji, no quotes, no explanation).\n" +
            "- Strip stage directions / sticker tags like [stiker: ...].\n" +
            "- Add small expressive interjections (ふふっ, あら~, もう!, はぁ…) sparingly matching emotion.\n" +
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
      throw new Error(meta.errorMessage || "VOICEVOX request failed (speaker mungkin tidak didukung, pilih yang lain)");
    }

    const statusUrl: string = meta.audioStatusUrl;
    const mp3Url: string = meta.mp3DownloadUrl;
    let ready = false;
    for (let i = 0; i < 60; i++) {
      const s = await fetch(statusUrl);
      if (s.ok) {
        const sj = await s.json();
        if (sj.isAudioReady) { ready = true; break; }
        if (sj.isAudioError) throw new Error("VOICEVOX synthesis error");
      }
      await new Promise((r) => setTimeout(r, 400));
    }
    if (!ready) throw new Error("VOICEVOX timeout (server sibuk, coba lagi)");

    return { mp3Url, emotion, japaneseText: jaText };
  });

// =================== Voice Clone (XTTS HF Space, free, no token) ===================

const CloneInput = z.object({
  text: z.string().min(1).max(800),
  sampleBase64: z.string().min(100),
  sampleMime: z.string().default("audio/wav"),
  language: z.enum(["ja", "en", "id"]).default("ja"),
  translateToJa: z.boolean().default(true),
});

// Call a public Gradio Space (XTTS v2) via /gradio_api/call endpoint.
// Space: https://coqui-xtts.hf.space  (anonymous, rate-limited, free).
async function callXttsSpace(text: string, sampleBase64: string, sampleMime: string, lang: string): Promise<string> {
  const base = "https://coqui-xtts.hf.space";

  // Step 1: upload sample file (multipart) → get server path
  const sampleBytes = Uint8Array.from(atob(sampleBase64), (c) => c.charCodeAt(0));
  const sampleBlob = new Blob([sampleBytes], { type: sampleMime || "audio/wav" });
  const fd = new FormData();
  fd.append("files", sampleBlob, "sample.wav");
  const upRes = await fetch(`${base}/gradio_api/upload`, { method: "POST", body: fd });
  if (!upRes.ok) throw new Error(`Upload sampel gagal: ${upRes.status}`);
  const upJson = (await upRes.json()) as string[];
  const uploadedPath = upJson[0];
  if (!uploadedPath) throw new Error("Upload sampel: response kosong");

  // Step 2: queue prediction. XTTS expects [text, language, audio_file, mic_file, use_mic, cleanup, agree]
  const callRes = await fetch(`${base}/gradio_api/call/predict`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      data: [
        text,
        lang,
        { path: uploadedPath, meta: { _type: "gradio.FileData" } },
        null,
        false,
        false,
        true,
      ],
    }),
  });
  if (!callRes.ok) {
    const t = await callRes.text();
    throw new Error(`XTTS queue gagal: ${callRes.status} ${t.slice(0, 160)}`);
  }
  const callJson = await callRes.json();
  const eventId = callJson.event_id ?? callJson?.hash;
  if (!eventId) throw new Error("XTTS: event_id tidak diterima");

  // Step 3: poll SSE stream for result
  const sseRes = await fetch(`${base}/gradio_api/call/predict/${eventId}`);
  if (!sseRes.ok || !sseRes.body) throw new Error(`XTTS stream gagal: ${sseRes.status}`);
  const reader = sseRes.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const events = buf.split("\n\n");
    buf = events.pop() ?? "";
    for (const ev of events) {
      const lines = ev.split("\n");
      const eventLine = lines.find((l) => l.startsWith("event:"))?.slice(6).trim();
      const dataLine = lines.find((l) => l.startsWith("data:"))?.slice(5).trim();
      if (!dataLine) continue;
      if (eventLine === "error") throw new Error(`XTTS error: ${dataLine.slice(0, 200)}`);
      if (eventLine === "complete") {
        try {
          const parsed = JSON.parse(dataLine);
          // parsed is array; first item is audio file descriptor { url, path } or string url
          const out = Array.isArray(parsed) ? parsed[0] : parsed;
          const url = typeof out === "string" ? out : out?.url ?? out?.path;
          if (!url) throw new Error("XTTS: tidak ada URL audio di hasil");
          return url.startsWith("http") ? url : `${base}/gradio_api/file=${url}`;
        } catch (e) {
          throw new Error(`XTTS parse hasil gagal: ${(e as Error).message}`);
        }
      }
    }
  }
  throw new Error("XTTS timeout (Space sibuk, coba lagi 30 detik)");
}

export const speakClone = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => CloneInput.parse(d))
  .handler(async ({ data }) => {
    let text = data.text;
    if (data.translateToJa && data.language === "ja") {
      try {
        const r = await detectEmotionAndTranslate(data.text);
        text = r.ja;
      } catch {}
    }

    try {
      const audioUrl = await callXttsSpace(text, data.sampleBase64, data.sampleMime, data.language);
      // Stream audio back to frontend as base64 so it works regardless of CORS
      const audioRes = await fetch(audioUrl);
      if (!audioRes.ok) throw new Error(`Fetch hasil audio gagal: ${audioRes.status}`);
      const buf = await audioRes.arrayBuffer();
      return {
        audio: Buffer.from(buf).toString("base64"),
        mime: "audio/wav",
        spokenText: text,
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      throw new Error(`Voice clone gagal: ${msg}. Coba lagi 30 detik (Space gratis sering antri).`);
    }
  });

// =================== Memories CRUD ===================

const MemoryListInput = z.object({ userId: z.string().min(1) });

export const listMemories = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => MemoryListInput.parse(d))
  .handler(async ({ data }) => {
    const { data: rows, error } = await supabaseAdmin
      .from("memories")
      .select("id, content, created_at, kind, importance, occurred_at, last_accessed_at, compressed")
      .eq("user_id", data.userId)
      .eq("character_id", CHARACTER_ID)
      .order("importance", { ascending: false })
      .order("last_accessed_at", { ascending: false })
      .limit(500);
    if (error) throw new Error(error.message);
    return { memories: rows ?? [] };
  });

export const deleteMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({ id: z.string().uuid(), userId: z.string().min(1) }).parse(d),
  )
  .handler(async ({ data }) => {
    const { error } = await supabaseAdmin
      .from("memories").delete()
      .eq("id", data.id).eq("user_id", data.userId);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const addMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({
      content: z.string().min(2).max(800),
      userId: z.string().min(1),
      importance: z.number().int().min(1).max(10).default(6),
      occurred_at: z.string().nullable().optional(),
    }).parse(d),
  )
  .handler(async ({ data }) => {
    const vec = await embed(data.content);
    const { error } = await supabaseAdmin.from("memories").insert({
      content: data.content,
      embedding: vec as unknown as string,
      user_id: data.userId,
      character_id: CHARACTER_ID,
      kind: "fact",
      importance: data.importance,
      occurred_at: data.occurred_at ?? null,
    });
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const updateMemory = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) =>
    z.object({
      id: z.string().uuid(),
      userId: z.string().min(1),
      content: z.string().min(2).max(800),
      importance: z.number().int().min(1).max(10).optional(),
      occurred_at: z.string().nullable().optional(),
    }).parse(d),
  )
  .handler(async ({ data }) => {
    // re-embed karena teks berubah
    const vec = await embed(data.content);
    const patch: Record<string, unknown> = {
      content: data.content,
      embedding: vec as unknown as string,
      last_accessed_at: new Date().toISOString(),
    };
    if (typeof data.importance === "number") patch.importance = data.importance;
    if (data.occurred_at !== undefined) patch.occurred_at = data.occurred_at;
    const { error } = await supabaseAdmin
      .from("memories").update(patch as never)
      .eq("id", data.id).eq("user_id", data.userId);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const clearAllMemories = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ userId: z.string().min(1) }).parse(d))
  .handler(async ({ data }) => {
    const { error } = await supabaseAdmin
      .from("memories").delete()
      .eq("user_id", data.userId).eq("character_id", CHARACTER_ID);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

const MigrateInput = z.object({
  fromGuestId: z.string().min(1),
  toUserId: z.string().min(1),
});

export const migrateGuestMemories = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => MigrateInput.parse(d))
  .handler(async ({ data }) => {
    const { error } = await supabaseAdmin
      .from("memories").update({ user_id: data.toUserId })
      .eq("user_id", data.fromGuestId).eq("character_id", CHARACTER_ID);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

// =================== Style Profile ===================
// Pelajari gaya bicara user dari pesan-pesan terakhir → simpan sebagai memori kind='style'.
// Frontend memanggil tiap ±10 pesan user.

const StyleInput = z.object({
  userId: z.string().min(1),
  userMessages: z.array(z.string()).min(3).max(60),
});

export const updateStyleProfile = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => StyleInput.parse(d))
  .handler(async ({ data }) => {
    const sample = data.userMessages.slice(-30).map((m, i) => `${i + 1}. ${m}`).join("\n");
    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash-lite",
        messages: [
          {
            role: "system",
            content:
              "Analisis gaya chat user dari sample berikut. Output paragraf SINGKAT (3-5 kalimat, Bahasa Indonesia) yang menjelaskan: panjang rata-rata pesan, formalitas (gaul/santai/formal), pola kalimat khas, kata/frasa yang sering dipakai (sebut beberapa contoh nyata dari sample), kata yang TIDAK PERNAH dipakai/dihindari (kalau ada pola), topik favorit. Jangan list. Tulis seperti briefing buat asisten yang harus meniru gaya ini.",
          },
          { role: "user", content: sample },
        ],
      }),
    });
    if (!res.ok) throw new Error(`Style analysis failed: ${res.status}`);
    const j = await res.json();
    const profile: string = j.choices?.[0]?.message?.content?.trim() ?? "";
    if (!profile || profile.length < 20) return { ok: false, profile: "" };

    // Replace existing style memory (kind='style') — hanya 1 yang aktif
    await supabaseAdmin.from("memories").delete()
      .eq("user_id", data.userId).eq("character_id", CHARACTER_ID).eq("kind", "style");

    const vec = await embed(profile);
    await supabaseAdmin.from("memories").insert({
      content: profile,
      embedding: vec as unknown as string,
      user_id: data.userId,
      character_id: CHARACTER_ID,
      kind: "style",
      importance: 9,
    });
    return { ok: true, profile };
  });

export const getStyleProfile = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => z.object({ userId: z.string().min(1) }).parse(d))
  .handler(async ({ data }) => {
    const { data: rows } = await supabaseAdmin
      .from("memories").select("content")
      .eq("user_id", data.userId).eq("character_id", CHARACTER_ID).eq("kind", "style")
      .limit(1);
    return { profile: rows?.[0]?.content ?? "" };
  });

// =================== Sticker vision label cache ===================
// Saat user pertama kali kirim stiker, AI tafsir label dari gambar.
// Hasil dicache di tabel user_stickers.cached_label.

const StickerLabelInput = z.object({
  stickerId: z.string().min(1),
  imageUrl: z.string().url(),
  userId: z.string().min(1),
});

export const cacheStickerLabel = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => StickerLabelInput.parse(d))
  .handler(async ({ data }) => {
    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash-lite",
        messages: [
          {
            role: "system",
            content: "Tafsir emosi/maksud sebuah stiker dari gambarnya. Output 2-5 kata Bahasa Indonesia (contoh: 'ketawa senang', 'capek banget', 'lagi mikir', 'ngambek lucu'). Tanpa tanda baca, tanpa kalimat lengkap.",
          },
          {
            role: "user",
            content: [
              { type: "text", text: "Stiker apa ini?" },
              { type: "image_url", image_url: { url: data.imageUrl } },
            ],
          },
        ],
      }),
    });
    if (!res.ok) return { label: "" };
    const j = await res.json();
    const label: string = (j.choices?.[0]?.message?.content ?? "").trim().slice(0, 60);
    if (label) {
      await supabaseAdmin.from("user_stickers")
        .update({ cached_label: label })
        .eq("id", data.stickerId).eq("user_id", data.userId);
    }
    return { label };
  });
