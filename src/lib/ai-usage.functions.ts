import { OPENROUTER, readAiPreferences } from "./background-ai.server";
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { requireFurinaIdentity } from "./furina-identity.server";
import { geminiEnabled, encryptionSecret } from "./gemini-provider.server";
import { validateGeminiModelAccess } from "./gemini-chat";
import { isInvalidGeminiKey, normalizeGeminiKey, protectGeminiKey } from "./gemini-key";
import { profileContext } from "./user-profile.server";
import { fetchAllPages } from "./record-pagination";

const identity = z.object({ userId: z.string().uuid() });

export const getGeminiKeySettings = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.parse(input))
  .handler(async ({ data: { userId } }) => {
    await requireFurinaIdentity(userId, true);
    const [enabled, keys, profile] = await Promise.all([
      geminiEnabled(userId),
      fetchAllPages((from, to) =>
        supabaseAdmin
          .from("furina_gemini_keys")
          .select("id,suffix,invalid")
          .eq("user_id", userId)
          .order("created_at")
          .order("id")
          .range(from, to),
      ).catch(() => {
        throw new Error("Daftar API key belum dapat dimuat.");
      }),
      profileContext(userId),
    ]);
    return { enabled, keys, eligible: (profile.birthday?.age ?? 0) >= 18 };
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
    const validation = await validateGeminiModelAccess(key);
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
        "API key belum bisa mengakses model chat Gemini. Periksa akses model di proyek Google AI Studio.",
      );
    }
    const { box, fingerprint } = await protectGeminiKey(key, userId, encryptionSecret());
    const { data, error } = await supabaseAdmin.rpc("save_furina_gemini_key", {
      owner_id: userId,
      secret_box: box,
      key_fingerprint: fingerprint,
      key_suffix: key.slice(-4),
    });
    if (error || data !== "saved") throw new Error("API key belum dapat disimpan. Coba lagi.");
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

export const getAiChannelSettings = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.parse(input))
  .handler(async ({ data: { userId } }) => {
    await requireFurinaIdentity(userId, true);
    const preferences = await readAiPreferences(userId);
    const backgroundPaused =
      preferences?.lovable_background === false && !preferences.use_openrouter;
    return {
      chat: preferences?.lovable_chat ?? true,
      background: preferences?.lovable_background ?? true,
      issues: backgroundPaused
        ? ["Pekerjaan latar belakang nonaktif."]
        : [
            preferences?.background_text_issue &&
              `Tugas teks · ${preferences.background_text_issue}`,
            preferences?.embedding_issue && `Memori · ${preferences.embedding_issue}`,
          ].filter(Boolean),
    };
  });

export const setLovableChannel = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) =>
    identity.extend({ channel: z.enum(["chat", "background"]), enabled: z.boolean() }).parse(input),
  )
  .handler(async ({ data: { userId, channel, enabled } }) => {
    await requireFurinaIdentity(userId, true);
    const { error } = await supabaseAdmin
      .from("furina_ai_preferences")
      .upsert(
        channel === "chat"
          ? { user_id: userId, lovable_chat: enabled }
          : { user_id: userId, lovable_background: enabled },
        { onConflict: "user_id" },
      );
    if (error) throw new Error("Pengaturan Lovable belum dapat disimpan.");
  });

export const getOpenRouterKeySettings = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.parse(input))
  .handler(async ({ data: { userId } }) => {
    await requireFurinaIdentity(userId, true);
    const [preferences, keys] = await Promise.all([
      readAiPreferences(userId),
      fetchAllPages((from, to) =>
        supabaseAdmin
          .from("furina_openrouter_keys")
          .select("id,suffix,invalid")
          .eq("user_id", userId)
          .order("created_at")
          .order("id")
          .range(from, to),
      ),
    ]);
    return { enabled: preferences?.use_openrouter ?? false, keys, eligible: true };
  });

export const addOpenRouterKey = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) =>
    identity
      .extend({
        key: z
          .string()
          .trim()
          .max(300)
          .regex(/^sk-or-v1-[a-zA-Z0-9_-]+$/),
      })
      .parse(input),
  )
  .handler(async ({ data: { userId, key } }) => {
    await requireFurinaIdentity(userId, true);
    const response = await fetch(`${OPENROUTER}/key`, {
      redirect: "manual",
      signal: AbortSignal.timeout(8000),
      headers: { Authorization: `Bearer ${key}` },
    }).catch(() => null);
    if (!response?.ok)
      throw new Error(
        response?.status === 401
          ? "OpenRouter menolak API key ini."
          : "API key OpenRouter belum bisa diperiksa. Coba lagi.",
      );
    await response.body?.cancel().catch(() => undefined);
    const { box, fingerprint } = await protectGeminiKey(key, userId, encryptionSecret());
    const { error } = await supabaseAdmin.from("furina_openrouter_keys").upsert(
      {
        user_id: userId,
        encrypted_value: box,
        fingerprint,
        suffix: key.slice(-4),
        invalid: false,
      },
      { onConflict: "user_id,fingerprint" },
    );
    if (error) throw new Error("API key OpenRouter belum dapat disimpan.");
  });

export const setOpenRouterProvider = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.extend({ enabled: z.boolean() }).parse(input))
  .handler(async ({ data: { userId, enabled } }) => {
    await requireFurinaIdentity(userId, true);
    if (enabled) {
      const { count, error } = await supabaseAdmin
        .from("furina_openrouter_keys")
        .select("id", { count: "exact", head: true })
        .eq("user_id", userId)
        .eq("invalid", false);
      if (error || !count) throw new Error("Tambahkan API key OpenRouter yang valid.");
    }
    const { error } = await supabaseAdmin
      .from("furina_ai_preferences")
      .upsert({ user_id: userId, use_openrouter: enabled }, { onConflict: "user_id" });
    if (error) throw new Error("Pengaturan OpenRouter belum dapat disimpan.");
  });

export const removeOpenRouterKey = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.extend({ id: z.string().uuid() }).parse(input))
  .handler(async ({ data: { userId, id } }) => {
    await requireFurinaIdentity(userId, true);
    const { error } = await supabaseAdmin
      .from("furina_openrouter_keys")
      .delete()
      .eq("user_id", userId)
      .eq("id", id);
    if (error) throw new Error("API key OpenRouter belum dapat dihapus.");
  });
