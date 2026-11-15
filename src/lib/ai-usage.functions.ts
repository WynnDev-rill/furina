import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { requireFurinaIdentity } from "./furina-identity.server";
import {
  geminiEnabled,
  encryptionSecret,
  GEMINI_BASE,
  GEMINI_CHAT_MODEL,
} from "./gemini-provider.server";
import { isInvalidGeminiKey, normalizeGeminiKey, protectGeminiKey } from "./gemini-key";
import { localCalendar } from "./birth-date";
import { profileContext } from "./user-profile.server";

const identity = z.object({ userId: z.string().uuid() });

export const getAiUsage = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.parse(input))
  .handler(async ({ data: { userId } }) => {
    await requireFurinaIdentity(userId, true);
    const day = localCalendar(new Date(), "Asia/Jakarta").toISOString().slice(0, 10);
    const [enabled, keys, usage, profile] = await Promise.all([
      geminiEnabled(userId),
      supabaseAdmin
        .from("furina_gemini_keys")
        .select("id,suffix,invalid")
        .eq("user_id", userId)
        .order("created_at")
        .order("id"),
      supabaseAdmin
        .from("furina_chat_usage")
        .select("provider,requests,tokens")
        .eq("user_id", userId)
        .gte("day", day.slice(0, 7) + "-01")
        .lte("day", day),
      profileContext(userId),
    ]);
    if (keys.error || usage.error) throw new Error("Penggunaan AI belum dapat dimuat.");
    return {
      enabled,
      keys: keys.data ?? [],
      eligible: (profile.birthday?.age ?? 0) >= 18,
      usage: (["lovable", "gemini"] as const).map((provider) =>
        (usage.data ?? [])
          .filter((row) => row.provider === provider)
          .reduce(
            (sum, row) => ({
              ...sum,
              requests: sum.requests + Number(row.requests),
              tokens: sum.tokens + Number(row.tokens),
            }),
            { provider, requests: 0, tokens: 0 },
          ),
      ),
    };
  });

export const addGeminiKey = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => {
    const result = identity.extend({ key: z.string().max(300) }).safeParse(input);
    const key = result.success ? normalizeGeminiKey(result.data.key) : null;
    if (!result.success || !key) {
      throw new Error("Tempel API key lengkap dari Google AI Studio tanpa tanda kutip atau label.");
    }
    return { userId: result.data.userId, key };
  })
  .handler(async ({ data: { userId, key } }) => {
    await requireFurinaIdentity(userId, true);
    if (((await profileContext(userId)).birthday?.age ?? 0) < 18) {
      throw new Error("API key Gemini tersedia untuk pengguna berusia 18 tahun ke atas.");
    }
    let validation: Response;
    try {
      validation = await fetch(`${GEMINI_BASE}/models/${GEMINI_CHAT_MODEL}`, {
        signal: AbortSignal.timeout(8000),
        headers: { "x-goog-api-key": key },
        redirect: "error",
      });
    } catch {
      throw new Error("Gemini belum dapat dihubungi. Coba lagi.");
    }
    if (validation.status === 429) {
      throw new Error("Gemini sedang membatasi permintaan. Coba lagi setelah kuota tersedia.");
    }
    if (validation.status >= 500) {
      throw new Error("Layanan Gemini sedang bermasalah. Coba lagi nanti.");
    }
    if (!validation.ok) {
      const reason = await validation.text().catch(() => "");
      if (isInvalidGeminiKey(validation.status, reason)) {
        throw new Error(
          "Google menolak API key ini. Salin ulang kunci aktif dari Google AI Studio.",
        );
      }
      throw new Error(
        "API key belum bisa mengakses Gemini 3.8 Flash. Periksa akses model di proyek Google AI Studio.",
      );
    }
    const { box, fingerprint } = await protectGeminiKey(key, userId, encryptionSecret());
    const { data, error } = await supabaseAdmin.rpc("save_furina_gemini_key", {
      owner_id: userId,
      secret_box: box,
      key_fingerprint: fingerprint,
      key_suffix: key.slice(-4),
    });
    if (error) throw new Error("API key belum dapat disimpan.");
    if (data === "full") throw new Error("Maksimal lima API key per akun.");
  });

export const setGeminiProvider = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.extend({ enabled: z.boolean() }).parse(input))
  .handler(async ({ data: { userId, enabled } }) => {
    await requireFurinaIdentity(userId, true);
    if (enabled) {
      if (((await profileContext(userId)).birthday?.age ?? 0) < 18)
        throw new Error("Akses Gemini memerlukan usia 18 tahun ke atas.");
      const { count, error } = await supabaseAdmin
        .from("furina_gemini_keys")
        .select("id", { count: "exact", head: true })
        .eq("user_id", userId)
        .eq("invalid", false);
      if (error || !count) throw new Error("Tambahkan API key Gemini yang valid terlebih dahulu.");
    }
    const { error } = await supabaseAdmin
      .from("furina_ai_preferences")
      .upsert({ user_id: userId, use_gemini: enabled });
    if (error) throw new Error("Penyedia gagal diganti.");
  });

export const removeGeminiKey = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.extend({ id: z.string().uuid() }).parse(input))
  .handler(async ({ data: { userId, id } }) => {
    await requireFurinaIdentity(userId, true);
    const { error } = await supabaseAdmin
      .from("furina_gemini_keys")
      .delete()
      .eq("user_id", userId)
      .eq("id", id);
    if (error) throw new Error("API key belum dapat dihapus.");
  });
