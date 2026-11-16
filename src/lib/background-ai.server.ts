import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { encryptionSecret } from "./gemini-provider.server";
import { openGeminiKey } from "./gemini-key";
import { fetchAllPages } from "./record-pagination";
import { requestOpenRouter } from "./openrouter-routing";

export const OPENROUTER = "https://openrouter.ai/api/v1";
export const EMBEDDING_MODEL = "openai/text-embedding-3-small";
export type BackgroundEndpoint = "chat/completions" | "embeddings";

export async function readAiPreferences(userId: string) {
  const { data, error } = await supabaseAdmin
    .from("furina_ai_preferences")
    .select("*")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw new Error("Pengaturan AI belum dapat dimuat.");
  return data;
}

function issueFor(provider: string, status: number) {
  if (status === 402) return `${provider}: kredit habis.`;
  if (status === 429) return `${provider}: kuota tercapai. Coba lagi nanti.`;
  if (status === 401 || status === 403) return `${provider}: key atau akses ditolak.`;
  return `${provider}: layanan belum tersedia.`;
}

export async function requestBackgroundAi(
  userId: string | undefined,
  endpoint: BackgroundEndpoint,
  payload: Record<string, unknown>,
): Promise<Response> {
  const preferences = userId ? await readAiPreferences(userId) : null;
  const useLovable = preferences?.lovable_background ?? true;
  let issue: string | null = null;
  let response: Response | null = null;
  if (preferences?.use_openrouter && userId) {
    try {
      const keys = await fetchAllPages((from, to) =>
        supabaseAdmin
          .from("furina_openrouter_keys")
          .select("id,encrypted_value")
          .eq("user_id", userId)
          .eq("invalid", false)
          .order("created_at")
          .order("id")
          .range(from, to),
      );
      response = await requestOpenRouter(
        keys,
        (row) => openGeminiKey(row.encrypted_value, userId, encryptionSecret()).catch(() => null),
        (key, signal) =>
          fetch(`${OPENROUTER}/${endpoint}`, {
            method: "POST",
            redirect: "manual",
            signal,
            headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
            body: JSON.stringify(
              endpoint === "embeddings"
                ? { ...payload, model: EMBEDDING_MODEL, dimensions: 1536 }
                : { ...payload, model: "openrouter/free", provider: { require_parameters: true } },
            ),
          }),
        async (row) => {
          await supabaseAdmin
            .from("furina_openrouter_keys")
            .update({ invalid: true })
            .eq("user_id", userId)
            .eq("id", row.id)
            .eq("encrypted_value", row.encrypted_value);
        },
      );
      if (!response?.ok)
        issue = response
          ? issueFor("OpenRouter", response.status)
          : "OpenRouter: tambahkan API key aktif.";
    } catch {
      issue = "OpenRouter: layanan belum tersedia.";
    }
  }
  if (!response?.ok && useLovable) {
    const key = process.env.LOVABLE_API_KEY;
    response = key
      ? await fetch(`https://ai.gateway.lovable.dev/v1/${endpoint}`, {
          method: "POST",
          redirect: "manual",
          signal: AbortSignal.timeout(12000),
          headers: { "Lovable-API-Key": key, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }).catch(() => new Response(null, { status: 504 }))
      : new Response(null, { status: 503 });
    if (!response.ok)
      issue = [issue, issueFor("Lovable", response.status)].filter(Boolean).join(" ");
    else if (issue) issue += " Dibantu Lovable.";
  }
  if (userId) {
    const column = endpoint === "embeddings" ? "embedding_issue" : "background_text_issue";
    if ((preferences?.[column] ?? null) !== issue) {
      await supabaseAdmin
        .from("furina_ai_preferences")
        .upsert(
          endpoint === "embeddings"
            ? { user_id: userId, embedding_issue: issue }
            : { user_id: userId, background_text_issue: issue },
          { onConflict: "user_id" },
        );
    }
  }
  return response ?? new Response(null, { status: 503 });
}
