import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { supabaseAdmin } from "@/integrations/supabase/client.server";
import { requireFurinaIdentity } from "./furina-identity.server";
import { readAiPreferences } from "./background-ai.server";
import { encryptionSecret } from "./gemini-provider.server";
import { protectGeminiKey } from "./gemini-key";
import { profileContext } from "./user-profile.server";
import { fetchAllPages } from "./record-pagination";
import {
  clearNvidiaChatAccess,
  validateNvidiaChatKey,
  loadNvidiaChatState,
} from "./nvidia-chat.server";

const identity = z.object({ userId: z.string().uuid() });
export const setChatProviderSelection = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) =>
    identity.extend({ provider: z.enum(["gemini", "nvidia"]) }).parse(input),
  )
  .handler(async ({ data: { userId, provider } }) => {
    await requireFurinaIdentity(userId, true);
    const { error } = await supabaseAdmin
      .from("furina_ai_preferences")
      .upsert({ user_id: userId, chat_provider: provider }, { onConflict: "user_id" });
    if (error) throw new Error("Penyedia percakapan belum dapat disimpan.");
  });

export const getNvidiaChatKeySettings = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.parse(input))
  .handler(async ({ data: { userId } }) => {
    await requireFurinaIdentity(userId, true);
    const [preferences, profile, routing, keys] = await Promise.all([
      readAiPreferences(userId),
      profileContext(userId),
      loadNvidiaChatState(userId),
      fetchAllPages((from, to) =>
        supabaseAdmin
          .from("furina_nvidia_chat_keys")
          .select("id,suffix,invalid,enabled")
          .eq("user_id", userId)
          .order("created_at")
          .order("id")
          .range(from, to),
      ),
    ]);
    const hasActiveKeys = keys.some((key) => key.enabled && !key.invalid);
    return {
      enabled: (preferences?.use_nvidia_chat ?? false) && hasActiveKeys,
      eligible: (profile.birthday?.age ?? 0) >= 18,
      keys,
      model: hasActiveKeys ? routing.state.activeModel : null,
      notice: hasActiveKeys
        ? routing.notice
        : "Tambahkan atau aktifkan API key NVIDIA untuk percakapan.",
    };
  });
export const addNvidiaChatKey = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => {
    const result = identity
      .extend({
        key: z
          .string()
          .trim()
          .max(300)
          .regex(/^nvapi-[A-Za-z0-9_-]+$/),
      })
      .safeParse(input);
    if (!result.success)
      throw new Error("Tempel API key NVIDIA lengkap tanpa label atau tanda kutip.");
    return result.data;
  })
  .handler(async ({ data: { userId, key } }) => {
    await requireFurinaIdentity(userId, true);
    if (((await profileContext(userId)).birthday?.age ?? 0) < 18)
      throw new Error("API key percakapan tersedia untuk usia 18 tahun ke atas.");
    if (!(await validateNvidiaChatKey(key)).length)
      throw new Error(
        "Key ini belum punya akses ke model percakapan dengan endpoint gratis terverifikasi.",
      );
    const { box, fingerprint } = await protectGeminiKey(key, userId, encryptionSecret());
    const { error } = await supabaseAdmin.from("furina_nvidia_chat_keys").upsert(
      {
        user_id: userId,
        encrypted_value: box,
        fingerprint,
        suffix: key.slice(-4),
        enabled: true,
        invalid: false,
      },
      { onConflict: "user_id,fingerprint" },
    );
    if (error) throw new Error("API key NVIDIA belum dapat disimpan.");
    const { error: preferenceError } = await supabaseAdmin
      .from("furina_ai_preferences")
      .upsert({ user_id: userId, use_nvidia_chat: true }, { onConflict: "user_id" });
    if (preferenceError) throw new Error("Key tersimpan, tetapi NVIDIA belum dapat diaktifkan.");
  });
export const setNvidiaChatProvider = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.extend({ enabled: z.boolean() }).parse(input))
  .handler(async ({ data: { userId, enabled } }) => {
    await requireFurinaIdentity(userId, true);
    if (enabled) {
      if (((await profileContext(userId)).birthday?.age ?? 0) < 18)
        throw new Error("API key percakapan tersedia untuk usia 18 tahun ke atas.");
      const { count, error } = await supabaseAdmin
        .from("furina_nvidia_chat_keys")
        .select("id", { count: "exact", head: true })
        .eq("user_id", userId)
        .eq("invalid", false)
        .eq("enabled", true);
      if (error || !count) throw new Error("Tambahkan dan aktifkan API key NVIDIA yang valid.");
    }
    const { error } = await supabaseAdmin
      .from("furina_ai_preferences")
      .upsert({ user_id: userId, use_nvidia_chat: enabled }, { onConflict: "user_id" });
    if (error) throw new Error("Pengaturan NVIDIA belum dapat disimpan.");
  });
export const setNvidiaChatKeyEnabled = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) =>
    identity.extend({ id: z.string().uuid(), enabled: z.boolean() }).parse(input),
  )
  .handler(async ({ data: { userId, id, enabled } }) => {
    await requireFurinaIdentity(userId, true);
    const { error } = await supabaseAdmin
      .from("furina_nvidia_chat_keys")
      .update({ enabled })
      .eq("user_id", userId)
      .eq("id", id);
    if (error) throw new Error("Status API key belum dapat disimpan.");
    clearNvidiaChatAccess(id);
  });
export const removeNvidiaChatKey = createServerFn({ method: "POST" })
  .inputValidator((input: unknown) => identity.extend({ id: z.string().uuid() }).parse(input))
  .handler(async ({ data: { userId, id } }) => {
    await requireFurinaIdentity(userId, true);
    const { error } = await supabaseAdmin
      .from("furina_nvidia_chat_keys")
      .delete()
      .eq("user_id", userId)
      .eq("id", id);
    if (error) throw new Error("API key NVIDIA belum dapat dihapus.");
    clearNvidiaChatAccess(id);
  });
