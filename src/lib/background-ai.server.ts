import { requestBackgroundChain } from "./background-provider-routing";
import { NVIDIA, NVIDIA_EMBEDDING, NVIDIA_TEXT } from "./nvidia-ai.server";
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

export async function requestPersonalBackground(
  userId: string,
  provider: "openrouter" | "nvidia",
  endpoint: BackgroundEndpoint,
  payload: Record<string, unknown>,
  timeoutMs = 15000,
) {
  const nvidia = provider === "nvidia";
  const table = nvidia ? "furina_nvidia_keys" : "furina_openrouter_keys";
  const keys = await fetchAllPages((from, to) =>
    supabaseAdmin
      .from(table)
      .select("id,encrypted_value")
      .eq("user_id", userId)
      .eq("invalid", false)
      .order("created_at")
      .order("id")
      .range(from, to),
  );
  const { input_type, ...body } = payload;
  const requestBody =
    endpoint === "embeddings"
      ? nvidia
        ? {
            input: Array.isArray(body.input) ? body.input : [body.input],
            model: NVIDIA_EMBEDDING,
            input_type: input_type ?? "passage",
            encoding_format: "float",
            truncate: "END",
          }
        : { ...body, model: EMBEDDING_MODEL, dimensions: 1536 }
      : nvidia
        ? { ...body, model: NVIDIA_TEXT }
        : { ...body, model: "openrouter/free", provider: { require_parameters: true } };
  return requestOpenRouter(
    keys,
    (row) => openGeminiKey(row.encrypted_value, userId, encryptionSecret()).catch(() => null),
    (key, signal) =>
      fetch(`${nvidia ? NVIDIA : OPENROUTER}/${endpoint}`, {
        method: "POST",
        redirect: "manual",
        signal,
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      }),
    async (row) => {
      await supabaseAdmin
        .from(table)
        .update({ invalid: true })
        .eq("user_id", userId)
        .eq("id", row.id)
        .eq("encrypted_value", row.encrypted_value);
    },
    timeoutMs,
  );
}

export async function requestBackgroundAi(
  userId: string | undefined,
  endpoint: BackgroundEndpoint,
  payload: Record<string, unknown>,
): Promise<Response> {
  const preferences = userId ? await readAiPreferences(userId) : null;
  const { input_type: _inputType, ...lovablePayload } = payload;
  const {
    response,
    provider: used,
    failures,
  } = await requestBackgroundChain([
    {
      name: "OpenRouter",
      enabled: !!userId && preferences?.use_openrouter,
      request: async () =>
        userId ? requestPersonalBackground(userId, "openrouter", endpoint, payload) : null,
    },
    {
      name: "NVIDIA",
      enabled: !!userId && preferences?.use_nvidia,
      request: async () =>
        userId ? requestPersonalBackground(userId, "nvidia", endpoint, payload) : null,
    },
    {
      name: "Lovable",
      enabled: preferences?.lovable_background ?? true,
      request: async () => {
        const key = process.env.LOVABLE_API_KEY;
        if (!key) return new Response(null, { status: 503 });
        return fetch(`https://ai.gateway.lovable.dev/v1/${endpoint}`, {
          method: "POST",
          redirect: "manual",
          signal: AbortSignal.timeout(12000),
          headers: { "Lovable-API-Key": key, "Content-Type": "application/json" },
          body: JSON.stringify(lovablePayload),
        }).catch(() => new Response(null, { status: 504 }));
      },
    },
  ]);
  const issues = failures.map(({ name, status }) =>
    status === null ? `${name}: tambahkan API key aktif.` : issueFor(name, status),
  );
  if (issues.length && used) issues.push(`Dibantu ${used}.`);
  const issue = issues.join(" ") || null;
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
  if (!used || !response) return response ?? new Response(null, { status: 503 });
  const headers = new Headers(response.headers);
  headers.set("x-furina-ai-provider", used);
  return new Response(response.body, { status: response.status, headers });
}
