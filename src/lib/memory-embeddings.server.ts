import { supabaseAdmin } from "@/integrations/supabase/client.server";
import {
  EMBEDDING_MODEL,
  requestBackgroundAi,
  requestPersonalBackground,
} from "./background-ai.server";

export function embeddingColumn(nvidia: boolean) {
  return nvidia ? "nvidia_embedding" : "embedding";
}

function readVector(vector: unknown, nvidia: boolean): string {
  if (
    !Array.isArray(vector) ||
    vector.length !== (nvidia ? 2048 : 1536) ||
    !vector.every(Number.isFinite)
  ) {
    throw new Error("Penyedia mengembalikan embedding memori yang tidak valid.");
  }
  return JSON.stringify(vector);
}

export async function embedMemory(
  userId: string,
  text: string,
  inputType: "passage" | "query" = "passage",
) {
  const response = await requestBackgroundAi(userId, "embeddings", {
    model: EMBEDDING_MODEL,
    input: text,
    input_type: inputType,
  });
  if (!response.ok) throw new Error("Embedding memori belum tersedia. Periksa AI dan API Key.");
  const nvidia = response.headers.get("x-furina-ai-provider") === "NVIDIA";
  return { nvidia, value: readVector((await response.json()).data?.[0]?.embedding, nvidia) };
}

export async function indexMissingMemories(
  userId: string,
  nvidia: boolean,
  useSaved: boolean,
  useHistory: boolean,
  cutoff: string | null,
) {
  const column = embeddingColumn(nvidia);
  let query = supabaseAdmin
    .from("memories")
    .select("id,content")
    .eq("user_id", userId)
    .eq("character_id", "furina")
    .neq("kind", "self")
    .is("merged_into", null)
    .is(column, null);
  const history = `saved.eq.false,compressed.eq.false${cutoff ? `,created_at.gt.${cutoff}` : ""}`;
  if (useSaved && useHistory) query = query.or(`saved.eq.true,and(${history})`);
  else if (useSaved) query = query.eq("saved", true);
  else if (useHistory) {
    query = query.eq("saved", false).eq("compressed", false);
    if (cutoff) query = query.gt("created_at", cutoff);
  } else return;
  const { data: notes, error } = await query
    .order("saved", { ascending: false })
    .order("created_at", { ascending: false })
    .order("id")
    .limit(12);
  if (error) throw error;
  if (!notes?.length) return;
  const payload = {
    model: EMBEDDING_MODEL,
    input: notes.map(({ content }) => content.slice(0, 12000)),
    input_type: "passage",
  };
  const response = nvidia
    ? await requestPersonalBackground(userId, "nvidia", "embeddings", payload, 5000)
    : await requestBackgroundAi(userId, "embeddings", payload);
  if (!response?.ok || (!nvidia && response.headers.get("x-furina-ai-provider") === "NVIDIA"))
    return;
  const entries = (await response.json()).data;
  if (!Array.isArray(entries) || entries.length !== notes.length) return;
  const vectors = entries.map((entry, index) => {
    if (entry.index !== undefined && entry.index !== index)
      throw new Error("Urutan embedding tidak sesuai.");
    return readVector(entry.embedding, nvidia);
  });
  await Promise.all(
    notes.map(async ({ id, content }, index) => {
      const patch = nvidia ? { nvidia_embedding: vectors[index] } : { embedding: vectors[index] };
      const { error: updateError } = await supabaseAdmin
        .from("memories")
        .update(patch)
        .eq("id", id)
        .eq("user_id", userId)
        .eq("content", content)
        .is(column, null);
      if (updateError) throw updateError;
    }),
  );
}
