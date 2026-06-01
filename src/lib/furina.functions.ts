import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

const GATEWAY = "https://ai.gateway.lovable.dev/v1";

function apiKey() {
  const k = process.env.LOVABLE_API_KEY;
  if (!k) throw new Error("LOVABLE_API_KEY belum diset");
  return k;
}

async function embed(text: string): Promise<number[]> {
  const res = await fetch(`${GATEWAY}/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
    body: JSON.stringify({ model: "openai/text-embedding-3-small", input: text }),
  });
  if (!res.ok) throw new Error(`Embedding gagal: ${res.status}`);
  const j = await res.json();
  return j.data[0].embedding;
}

function partOfDay(d: Date): string {
  const h = d.getHours();
  if (h >= 5 && h < 11) return "pagi";
  if (h >= 11 && h < 15) return "siang";
  if (h >= 15 && h < 18) return "sore";
  if (h >= 18 && h < 22) return "malam";
  return "tengah malam";
}

// ============ CHAT ============
const MessageSchema = z.object({
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
});

const ChatInput = z.object({
  messages: z.array(MessageSchema).min(1),
  characterId: z.enum(["furina", "hutao"]),
  persona: z.string(),
  romantic: z.boolean().default(false),
  userTimezone: z.string().default("Asia/Jakarta"),
});

export const chatWithCharacter = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => ChatInput.parse(d))
  .handler(async ({ data, context }) => {
    const { userId } = context;
    const lastUser = [...data.messages].reverse().find((m) => m.role === "user");
    const userText = lastUser?.content ?? "";

    // RAG retrieval (per user + per character)
    let memoryContext = "";
    try {
      if (userText.trim()) {
        const qVec = await embed(userText);
        const { data: matches } = await supabaseAdmin.rpc("match_memories", {
          query_embedding: qVec as unknown as string,
          match_user_id: userId,
          match_character_id: data.characterId,
          match_count: 5,
        });
        if (matches && matches.length) {
          memoryContext =
            "\n\nMEMORI tentang user (gunakan natural, jangan dibacakan):\n" +
            matches.map((m: { content: string }) => `- ${m.content}`).join("\n");
        }
      }
    } catch (e) {
      console.error("RAG retrieval failed:", e);
    }

    const now = new Date();
    const localTime = new Intl.DateTimeFormat("id-ID", {
      timeZone: data.userTimezone,
      weekday: "long",
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
    }).format(now);
    const timeLine = `\nWaktu user sekarang: ${localTime} (${partOfDay(now)}). Sapa & respon sesuai waktu kalau relevan.`;

    const system = `${data.persona}\n\nBalas dalam bahasa yang sama dengan user (terutama Indonesia).${timeLine}${memoryContext}`;

    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
      body: JSON.stringify({
        model: "google/gemini-3-flash-preview",
        messages: [{ role: "system", content: system }, ...data.messages],
      }),
    });
    if (!res.ok) {
      const txt = await res.text();
      if (res.status === 429) throw new Error("Rate limit. Coba lagi sebentar.");
      if (res.status === 402) throw new Error("Kredit AI habis. Tambah kredit di workspace.");
      throw new Error(`Chat gagal: ${res.status} ${txt}`);
    }
    const json = await res.json();
    const reply: string = json.choices?.[0]?.message?.content ?? "";

    // Background memory extraction
    extractAndStoreMemory(userId, data.characterId, userText, reply).catch((e) =>
      console.error("Memory extract failed:", e),
    );

    return { reply };
  });

async function extractAndStoreMemory(
  userId: string,
  characterId: string,
  userMsg: string,
  assistantReply: string,
) {
  const exchange = `USER: ${userMsg}\nASSISTANT: ${assistantReply}`;
  const res = await fetch(`${GATEWAY}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
    body: JSON.stringify({
      model: "google/gemini-3-flash-preview",
      messages: [
        {
          role: "system",
          content:
            "Extract durable, personal facts about THE USER worth remembering long-term (name, preferences, relationships, ongoing projects, opinions). Output ONLY JSON array of short third-person strings. If nothing notable, output [].",
        },
        { role: "user", content: exchange },
      ],
    }),
  });
  if (!res.ok) return;
  const json = await res.json();
  const raw: string = json.choices?.[0]?.message?.content ?? "[]";
  const m = raw.match(/\[[\s\S]*\]/);
  if (!m) return;
  let facts: string[] = [];
  try { facts = JSON.parse(m[0]); } catch { return; }
  for (const f of facts.filter((x) => typeof x === "string" && x.trim().length > 3).slice(0, 5)) {
    try {
      const vec = await embed(f);
      await supabaseAdmin.from("memories").insert({
        user_id: userId,
        character_id: characterId,
        content: f,
        embedding: vec as unknown as string,
      });
    } catch (e) { console.error("Store memory fail:", e); }
  }
}

// ============ VOICEVOX TTS with emotion + chunking ============
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
  try {
    const res = await fetch(`${GATEWAY}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Lovable-API-Key": apiKey() },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash-lite",
        messages: [
          {
            role: "system",
            content:
              "Convert text to natural spoken Japanese for an anime-style female voice AND classify dominant emotion.\n" +
              "Allowed emotions: neutral, happy, sad, angry, excited, shy, tender, playful.\n" +
              "Output STRICT JSON: {\"emotion\":\"<one>\",\"ja\":\"<japanese>\"}\n" +
              "ja: ONLY natural spoken Japanese, no romaji/quotes/explanation.\n" +
              "Add small interjections (ふふっ, あら~, もう!, はぁ…, わぁ!) sparingly when emotion fits.\n" +
              "Convert numbers/symbols to Japanese reading.",
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
    const parsed = JSON.parse(m[0]);
    const emotion = (["neutral","happy","sad","angry","excited","shy","tender","playful"].includes(parsed.emotion)
      ? parsed.emotion : "neutral") as Emotion;
    const ja = typeof parsed.ja === "string" ? parsed.ja.replace(/^["「『]+|["」』]+$/g, "").trim() : srcText;
    return { ja: ja || srcText, emotion };
  } catch {
    return { ja: srcText, emotion: "neutral" };
  }
}

// Split Japanese text into chunks ≤ MAX_CHARS at sentence boundaries
function chunkJa(text: string, maxChars = 180): string[] {
  if (text.length <= maxChars) return [text];
  const parts: string[] = [];
  // Split on Japanese & latin sentence punctuation
  const sentences = text.split(/(?<=[。．！？!?\n])/);
  let buf = "";
  for (const s of sentences) {
    if ((buf + s).length > maxChars && buf) {
      parts.push(buf);
      buf = s;
    } else {
      buf += s;
    }
    // Hard split overly long single sentence
    while (buf.length > maxChars) {
      parts.push(buf.slice(0, maxChars));
      buf = buf.slice(maxChars);
    }
  }
  if (buf) parts.push(buf);
  return parts;
}

async function ttsQuestSynth(
  text: string,
  speaker: number,
  speed: number,
  pitch: number,
  intonation: number,
): Promise<Uint8Array> {
  const params = new URLSearchParams({
    speaker: String(speaker),
    text,
    speed: speed.toFixed(2),
    pitch: pitch.toFixed(2),
    intonationScale: intonation.toFixed(2),
  });
  const initUrl = `https://api.tts.quest/v3/voicevox/synthesis?${params.toString()}`;
  const init = await fetch(initUrl);
  if (!init.ok) throw new Error(`VOICEVOX init gagal: ${init.status}`);
  const meta = await init.json();
  if (!meta.success) throw new Error(meta.errorMessage || "VOICEVOX request gagal");

  const statusUrl: string = meta.audioStatusUrl;
  const mp3Url: string = meta.mp3DownloadUrl;
  let ready = false;
  for (let i = 0; i < 60; i++) {
    const s = await fetch(statusUrl);
    if (s.ok) {
      const sj = await s.json();
      if (sj.isAudioReady) { ready = true; break; }
      if (sj.isAudioError) throw new Error("VOICEVOX synthesis error (server tts.quest)");
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  if (!ready) throw new Error("VOICEVOX timeout — server tts.quest sedang sibuk, coba lagi");

  const audio = await fetch(mp3Url);
  if (!audio.ok) throw new Error(`VOICEVOX fetch gagal: ${audio.status}`);
  return new Uint8Array(await audio.arrayBuffer());
}

const VVInput = z.object({
  text: z.string().min(1).max(4000),
  speaker: z.number().int().min(0).max(100).default(14),
  speed: z.number().min(0.5).max(2).default(1.0),
  translateToJa: z.boolean().default(true),
});

export const speakVoicevox = createServerFn({ method: "POST" })
  .inputValidator((d: unknown) => VVInput.parse(d))
  .handler(async ({ data }) => {
    let jaText = data.text;
    let emotion: Emotion = "neutral";
    if (data.translateToJa) {
      const r = await detectEmotionAndTranslate(data.text);
      jaText = r.ja;
      emotion = r.emotion;
    }
    const profile = EMOTION_PROFILES[emotion];
    const finalSpeed = Math.min(2, Math.max(0.5, data.speed * profile.speedMul));

    // Chunk if long — synth sequentially & concat MP3 buffers
    const chunks = chunkJa(jaText, 180);
    const bufs: Uint8Array[] = [];
    for (const c of chunks) {
      const b = await ttsQuestSynth(c, data.speaker, finalSpeed, profile.pitch, profile.intonation);
      bufs.push(b);
    }
    const total = bufs.reduce((s, b) => s + b.length, 0);
    const merged = new Uint8Array(total);
    let off = 0;
    for (const b of bufs) { merged.set(b, off); off += b.length; }

    return {
      audio: Buffer.from(merged).toString("base64"),
      japaneseText: jaText,
      emotion,
      chunks: chunks.length,
    };
  });

// ============ CONVERSATIONS / MESSAGES CRUD ============
export const listConversations = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ characterId: z.enum(["furina","hutao"]) }).parse(d))
  .handler(async ({ data, context }) => {
    const { supabase } = context;
    const { data: rows, error } = await supabase
      .from("conversations")
      .select("id, title, created_at, updated_at")
      .eq("character_id", data.characterId)
      .order("updated_at", { ascending: false });
    if (error) throw new Error(error.message);
    return { conversations: rows ?? [] };
  });

export const createConversation = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({
    characterId: z.enum(["furina","hutao"]),
    title: z.string().min(1).max(120).default("Percakapan baru"),
  }).parse(d))
  .handler(async ({ data, context }) => {
    const { supabase, userId } = context;
    const { data: row, error } = await supabase
      .from("conversations")
      .insert({ user_id: userId, character_id: data.characterId, title: data.title })
      .select("id, title, created_at, updated_at")
      .single();
    if (error) throw new Error(error.message);
    return { conversation: row };
  });

export const renameConversation = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid(), title: z.string().min(1).max(120) }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase.from("conversations").update({ title: data.title }).eq("id", data.id);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const deleteConversation = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid() }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase.from("conversations").delete().eq("id", data.id);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

export const listMessages = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ conversationId: z.string().uuid() }).parse(d))
  .handler(async ({ data, context }) => {
    const { data: rows, error } = await context.supabase
      .from("messages")
      .select("id, role, content, status, created_at")
      .eq("conversation_id", data.conversationId)
      .order("created_at", { ascending: true });
    if (error) throw new Error(error.message);
    return { messages: rows ?? [] };
  });

export const saveMessage = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({
    conversationId: z.string().uuid(),
    role: z.enum(["user","assistant"]),
    content: z.string().min(1),
    status: z.enum(["sending","sent","delivered","read","failed"]).default("sent"),
  }).parse(d))
  .handler(async ({ data, context }) => {
    const { supabase, userId } = context;
    const { data: row, error } = await supabase
      .from("messages")
      .insert({
        conversation_id: data.conversationId,
        user_id: userId,
        role: data.role,
        content: data.content,
        status: data.status,
      })
      .select("id, role, content, status, created_at")
      .single();
    if (error) throw new Error(error.message);
    // Bump conversation updated_at
    await supabase.from("conversations").update({ updated_at: new Date().toISOString() }).eq("id", data.conversationId);
    return { message: row };
  });

export const updateMessageStatus = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({
    id: z.string().uuid(),
    status: z.enum(["sending","sent","delivered","read","failed"]),
  }).parse(d))
  .handler(async ({ data, context }) => {
    const { error } = await context.supabase.from("messages").update({ status: data.status }).eq("id", data.id);
    if (error) throw new Error(error.message);
    return { ok: true };
  });

// ============ USER SETTINGS (JSON string roundtrip for serialization safety) ============
export const getUserSettings = createServerFn({ method: "GET" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const { data, error } = await context.supabase
      .from("user_settings").select("data").eq("user_id", context.userId).maybeSingle();
    if (error) throw new Error(error.message);
    return { settingsJson: JSON.stringify(data?.data ?? {}) };
  });

export const saveUserSettings = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ dataJson: z.string().max(50000) }).parse(d))
  .handler(async ({ data, context }) => {
    const parsed = JSON.parse(data.dataJson);
    const { error } = await context.supabase
      .from("user_settings")
      .upsert({ user_id: context.userId, data: parsed, updated_at: new Date().toISOString() });
    if (error) throw new Error(error.message);
    return { ok: true };
  });
