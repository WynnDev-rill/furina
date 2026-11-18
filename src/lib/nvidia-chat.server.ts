import { supabaseAdmin } from "@/integrations/supabase/client.server";
import {
  availableNvidiaChatModels,
  createNvidiaCatalogLoader,
  type NvidiaChatModel,
} from "./nvidia-catalog";
import { routeNvidiaChat, type NvidiaRoutingState } from "./nvidia-chat-routing";
import { NVIDIA } from "./nvidia-ai.server";
import { encryptionSecret } from "./gemini-provider.server";
import { openGeminiKey } from "./gemini-key";
import { fetchAllPages } from "./record-pagination";
import type { GeminiChatMessage } from "./gemini-chat";
import type { Json } from "@/integrations/supabase/types";

const freeCatalog = createNvidiaCatalogLoader();
const accessCache = new Map<string, { models: NvidiaChatModel[]; expires: number }>();

export async function discoverNvidiaChatModels(
  key: string,
  cacheId?: string,
  signal?: AbortSignal,
) {
  const catalog = await freeCatalog();
  const cached = cacheId ? accessCache.get(cacheId) : null;
  if (cached && cached.expires > Date.now()) {
    // The model listing is public. Only inference validates key access; free metadata is always rechecked.
    return availableNvidiaChatModels({ data: cached.models.map(({ id }) => ({ id })) }, catalog);
  }
  const response = await fetch(`${NVIDIA}/models`, {
    redirect: "manual",
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(8000)])
      : AbortSignal.timeout(8000),
    headers: { Authorization: `Bearer ${key}` },
  }).catch(() => null);
  if (!response?.ok) {
    const status = response?.status ?? 504;
    const rawRetry = response?.headers.get("retry-after");
    const seconds = rawRetry === null || rawRetry === undefined ? NaN : Number(rawRetry);
    const retry = Number.isFinite(seconds)
      ? seconds * 1000
      : Date.parse(rawRetry ?? "") - Date.now();
    await response?.body?.cancel().catch(() => undefined);
    throw Object.assign(
      new Error(
        status === 401
          ? "NVIDIA menolak API key ini."
          : "Akses model NVIDIA belum dapat diperiksa. Coba lagi.",
      ),
      {
        status,
        retryAfter: Math.max(1000, Number.isFinite(retry) ? retry : 60_000),
      },
    );
  }
  const models = availableNvidiaChatModels(await response.json(), catalog);
  if (cacheId) {
    if (accessCache.size >= 256) accessCache.delete(accessCache.keys().next().value!);
    accessCache.set(cacheId, { models, expires: Date.now() + 120_000 });
  }
  return models;
}

export function clearNvidiaChatAccess(id: string) {
  accessCache.delete(id);
}

export async function loadNvidiaChatState(userId: string) {
  const { data, error } = await supabaseAdmin
    .from("furina_nvidia_chat_state")
    .select("active_model,active_key_id,cooldowns,last_notice,updated_at")
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw new Error("Status percakapan NVIDIA belum dapat dimuat.");
  const cooldowns: Record<string, number> = {};
  if (data?.cooldowns && typeof data.cooldowns === "object" && !Array.isArray(data.cooldowns)) {
    for (const [id, until] of Object.entries(data.cooldowns)) {
      if (typeof until === "number" && Number.isFinite(until)) cooldowns[id] = until;
    }
  }
  return {
    state: {
      activeModel: data?.active_model ?? null,
      activeKeyId: data?.active_key_id ?? null,
      cooldowns,
    } satisfies NvidiaRoutingState,
    notice: data?.last_notice ?? null,
  };
}

export async function checkNvidiaChatEligibility(
  userId: string,
  row: { id: string; encrypted_value: string },
): Promise<"active" | "key-disabled" | "provider-disabled"> {
  const [preferences, key] = await Promise.all([
    supabaseAdmin
      .from("furina_ai_preferences")
      .select("chat_provider,use_nvidia_chat")
      .eq("user_id", userId)
      .maybeSingle(),
    supabaseAdmin
      .from("furina_nvidia_chat_keys")
      .select("id")
      .eq("user_id", userId)
      .eq("id", row.id)
      .eq("encrypted_value", row.encrypted_value)
      .eq("enabled", true)
      .eq("invalid", false)
      .maybeSingle(),
  ]);
  if (preferences.error || key.error) throw new Error("Aktivasi NVIDIA belum dapat diverifikasi.");
  if (preferences.data?.chat_provider !== "nvidia" || !preferences.data.use_nvidia_chat)
    return "provider-disabled";
  return key.data ? "active" : "key-disabled";
}

export async function requestNvidiaChat(userId: string, messages: GeminiChatMessage[]) {
  const deadline = Date.now() + 45_000;
  const { state: previous } = await loadNvidiaChatState(userId);

  const keys = await fetchAllPages((from, to) =>
    supabaseAdmin
      .from("furina_nvidia_chat_keys")
      .select("id,encrypted_value")
      .eq("user_id", userId)
      .eq("invalid", false)
      .eq("enabled", true)
      .order("created_at")
      .order("id")
      .range(from, to),
  );
  if (!keys.length)
    throw new Error(
      "Tidak ada API key NVIDIA percakapan yang aktif. Tambahkan atau aktifkan key di AI dan API Key.",
    );
  const secrets = new Map<string, string>();
  const candidates = keys.map(({ id }) => ({ id, models: [] as NvidiaChatModel[] }));
  const image = messages.some(
    ({ content }) => Array.isArray(content) && content.some((part) => part.type === "image_url"),
  );
  const result = await routeNvidiaChat({
    keys: candidates,
    state: previous,
    image,
    timeoutMs: Math.max(1, deadline - Date.now()),
    checkEligibility: (key) =>
      checkNvidiaChatEligibility(userId, keys.find(({ id }) => id === key.id)!),
    loadModels: async (candidate, signal) => {
      const row = keys.find(({ id }) => id === candidate.id)!;
      const key = await openGeminiKey(row.encrypted_value, userId, encryptionSecret()).catch(
        () => null,
      );
      if (!key)
        throw Object.assign(new Error("Key NVIDIA perlu ditambahkan ulang."), { status: 401 });
      const models = await discoverNvidiaChatModels(key, row.id, signal);
      secrets.set(row.id, key);
      return models;
    },
    request: (key, model, signal) =>
      fetch(`${NVIDIA}/chat/completions`, {
        method: "POST",
        redirect: "manual",
        signal,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${secrets.get(key.id)!}`,
        },
        body: JSON.stringify({
          model: model.id,
          messages,
          stream: false,
          max_tokens: 1400,
          temperature: 0.7,
          chat_template_kwargs: { enable_thinking: false },
        }),
      }),
  });
  const rejectedKeys = new Set(result.invalidKeys);
  if (keys.length && rejectedKeys.size === keys.length)
    result.response = new Response(null, { status: 401 });
  for (const id of rejectedKeys) {
    const row = keys.find((key) => key.id === id);
    if (!row) continue;
    clearNvidiaChatAccess(id);
    await supabaseAdmin
      .from("furina_nvidia_chat_keys")
      .update({ invalid: true })
      .eq("user_id", userId)
      .eq("id", id)
      .eq("encrypted_value", row.encrypted_value);
  }
  const switched =
    !!result.model && !!previous.activeModel && result.model.id !== previous.activeModel;
  const notice = result.response.ok
    ? switched
      ? `Model beralih ke ${result.model!.id} karena model sebelumnya belum tersedia.`
      : null
    : "NVIDIA belum tersedia. Model dan key yang sibuk diberi jeda; tidak memakai penyedia berbayar.";
  const { error } = await supabaseAdmin.rpc("save_furina_nvidia_chat_state", {
    owner_id: userId,
    model_id: result.model?.id ?? null,
    key_id: result.response.ok ? result.state.activeKeyId : null,
    blocked_until: result.state.cooldowns as Json,
    notice,
  });
  if (error) console.warn("NVIDIA routing status could not be saved.");
  return {
    response: result.response,
    provider: "nvidia" as const,
    model: result.model?.id ?? null,
    notice: result.response.ok
      ? (notice ?? (error ? "Status model NVIDIA belum tersimpan." : ""))
      : "",
  };
}

export async function validateNvidiaChatKey(key: string) {
  const models = await discoverNvidiaChatModels(key);
  if (!models.length)
    throw new Error("Tidak ada model percakapan dengan endpoint gratis terverifikasi.");
  // /models is public, so a tiny authenticated free inference is required before storing a key.
  const probes = [...models].sort(
    (a, b) => Number(b.id.includes("bolt")) - Number(a.id.includes("bolt")),
  );
  const result = await routeNvidiaChat({
    keys: [{ id: "validation", models: probes }],
    state: { activeModel: null, activeKeyId: null, cooldowns: {} },
    timeoutMs: 15_000,
    request: (_row, model, signal) =>
      fetch(`${NVIDIA}/chat/completions`, {
        method: "POST",
        redirect: "manual",
        signal,
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          model: model.id,
          messages: [{ role: "user", content: "Reply only OK." }],
          stream: false,
          max_tokens: 32,
          temperature: 0,
          chat_template_kwargs: { enable_thinking: false },
        }),
      }),
  });
  await result.response.body?.cancel().catch(() => undefined);
  if (result.invalidKeys.length) throw new Error("NVIDIA menolak API key ini.");
  if (!result.response.ok)
    throw new Error(
      result.response.status === 429
        ? "NVIDIA sedang membatasi permintaan. Key belum disimpan; coba lagi setelah kuota tersedia."
        : "Key belum dapat mengakses inferensi gratis NVIDIA. Periksa key dan kuota lalu coba lagi.",
    );
  return models;
}
