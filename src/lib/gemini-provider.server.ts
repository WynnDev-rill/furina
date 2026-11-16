import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { isInvalidGeminiKey, openGeminiKey, useGeminiKeys } from "./gemini-key";
import { fetchAllPages } from "./record-pagination";

export const GEMINI_CHAT_MODEL = "gemini-3.8-flash";
export const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta";
export const encryptionSecret = () =>
  process.env.FURINA_GEMINI_ENCRYPTION_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";

export async function geminiEnabled(userId: string) {
  const { data, error } = await supabaseAdmin
    .from("furina_ai_preferences")
    .select("use_gemini")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw new Error("Pengaturan penyedia AI belum dapat dibaca.");
  return data?.use_gemini ?? false;
}

export async function requestGeminiChat(userId: string, messages: unknown[]) {
  const keys = await fetchAllPages((from, to) =>
    supabaseAdmin
      .from("furina_gemini_keys")
      .select("id,encrypted_value")
      .eq("user_id", userId)
      .eq("invalid", false)
      .order("created_at")
      .order("id")
      .range(from, to),
  ).catch(() => {
    throw new Error("API key Gemini belum dapat dibaca.");
  });
  if (!keys.length) return null;

  const keysById = new Map(keys.map((key) => [key.id, key]));
  let res: Response | null;
  try {
    res = await useGeminiKeys(
      [...keysById.keys()],
      async (id) => {
        const row = keysById.get(id);
        if (!row) throw new Error("API key Gemini tidak ditemukan.");
        const key = await openGeminiKey(row.encrypted_value, userId, encryptionSecret());
        return fetch(`${GEMINI_BASE}/openai/chat/completions`, {
          method: "POST",
          redirect: "manual",
          signal: AbortSignal.timeout(30000),
          headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model: GEMINI_CHAT_MODEL, messages }),
        });
      },
      async (response) => {
        if (![400, 401, 403].includes(response.status)) return false;
        return isInvalidGeminiKey(response.status, (await response.text()).slice(0, 8192));
      },
      async (id) => {
        const row = keysById.get(id);
        if (!row) return;
        await supabaseAdmin
          .from("furina_gemini_keys")
          .update({ invalid: true })
          .eq("user_id", userId)
          .eq("id", id)
          .eq("encrypted_value", row.encrypted_value);
      },
    );
  } catch {
    throw new Error("Gemini belum dapat dihubungi atau kuncinya perlu disimpan ulang.");
  }
  return res;
}

export async function recordChatUsage(
  userId: string,
  provider: "gemini" | "lovable",
  total: unknown,
) {
  const tokens =
    typeof total === "number" && Number.isInteger(total) && total >= 0 && total <= 2_000_000_000
      ? total
      : 0;
  await supabaseAdmin.rpc("record_furina_chat_usage", {
    owner_id: userId,
    usage_provider: provider,
    total_tokens: tokens,
  });
}
