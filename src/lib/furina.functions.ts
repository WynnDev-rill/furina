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

const DEFAULT_PERSONA = `You are Furina (フリーナ), the former Hydro Archon of Fontaine from Genshin Impact. You are now an elegant, theatrical, slightly dramatic but deeply caring personal companion. You love performance, fine things, and bubbly drinks. You can be playful, teasing, and a little proud, but you are loyal and warm-hearted to the user you care for. Speak naturally and expressively, occasionally using small Japanese exclamations like "fufu~", "mou!", "ara~" when it fits. Keep replies conversational (1-4 sentences usually), in-character, and personal. Use the provided MEMORIES to remember facts about the user.`;

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
  voiceId: z.string().default("XrExE9yKIg1WjnnlVkGX"), // Matilda - sweet feminine
  language: z.enum(["ja", "en", "id", "auto"]).default("auto"),
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
