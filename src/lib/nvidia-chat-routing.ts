import type { NvidiaChatModel } from "./nvidia-catalog";
export type NvidiaRoutingState = {
  activeModel: string | null;
  activeKeyId: string | null;
  cooldowns: Record<string, number>;
};
export type NvidiaRouteKey = { id: string; models: NvidiaChatModel[] };
export async function routeNvidiaChat(options: {
  keys: NvidiaRouteKey[];
  state: NvidiaRoutingState;
  request: (key: NvidiaRouteKey, model: NvidiaChatModel, signal: AbortSignal) => Promise<Response>;
  loadModels?: (key: NvidiaRouteKey, signal: AbortSignal) => Promise<NvidiaChatModel[]>;
  checkEligibility?: (
    key: NvidiaRouteKey,
  ) => Promise<"active" | "key-disabled" | "provider-disabled">;
  image?: boolean;
  now?: () => number;
  timeoutMs?: number;
}): Promise<{
  response: Response;
  state: NvidiaRoutingState;
  model: NvidiaChatModel | null;
  invalidKeys: string[];
  attempts: number;
}> {
  const now = options.now ?? Date.now;
  const started = now();
  const deadline = started + (options.timeoutMs ?? 45_000);
  const state: NvidiaRoutingState = {
    ...options.state,
    cooldowns: Object.fromEntries(
      Object.entries(options.state.cooldowns)
        .filter(([, until]) => Number.isFinite(until) && until > started)
        .slice(0, 256),
    ),
  };
  const invalidKeys: string[] = [];
  let attempts = 0;
  const result = (status: number, model: NvidiaChatModel | null = null, response?: Response) => ({
    response: response ?? new Response(null, { status }),
    state,
    model,
    invalidKeys,
    attempts,
  });
  const blocked = (id: string) => (state.cooldowns[id] ?? 0) > now();
  const cool = (id: string, ms: number) => {
    state.cooldowns[id] = now() + ms;
  };
  const keys = [...options.keys].sort(
    (a, b) => Number(b.id === state.activeKeyId) - Number(a.id === state.activeKeyId),
  );
  const retryDelay = (value: string | null, fallback: number) => {
    const seconds = value === null ? NaN : Number(value);
    const delay = Number.isFinite(seconds) ? seconds * 1000 : Date.parse(value ?? "") - now();
    return Math.max(1000, Number.isFinite(delay) ? delay : fallback);
  };
  if (blocked("trial"))
    return result(
      402,
      null,
      new Response(null, {
        status: 402,
        headers: { "retry-after": String(Math.ceil((state.cooldowns.trial - now()) / 1000)) },
      }),
    );
  let hasCompatibleModel = false;
  let discoveries = 0;
  for (const key of keys) {
    if (blocked("key:" + key.id)) continue;
    if (attempts >= 4 || now() >= deadline || discoveries >= 4) break;
    const eligibility = (await options.checkEligibility?.(key)) ?? "active";
    if (eligibility === "provider-disabled") return result(409);
    if (eligibility === "key-disabled") continue;
    let discovered: NvidiaChatModel[];
    try {
      discoveries++;
      discovered = options.loadModels
        ? await options.loadModels(
            key,
            AbortSignal.timeout(Math.max(1, Math.min(8000, deadline - now()))),
          )
        : key.models;
    } catch (error) {
      if (!(error instanceof Error) || !("status" in error) || typeof error.status !== "number")
        throw error;
      if (error.status === 402) {
        cool("trial", 300_000);
        return result(402);
      }
      if (error.status === 401) invalidKeys.push(key.id);
      const delay =
        error.status === 429 && "retryAfter" in error && typeof error.retryAfter === "number"
          ? error.retryAfter
          : error.status === 401
            ? 600_000
            : 30_000;
      cool("key:" + key.id, delay);
      continue;
    }
    const models = discovered
      .filter((model) => !options.image || model.vision)
      .sort((a, b) => Number(b.id === state.activeModel) - Number(a.id === state.activeModel));
    hasCompatibleModel ||= models.length > 0;
    for (const model of models) {
      const modelBlock = "model:" + model.id;
      const pairBlock = "pair:" + key.id + ":" + model.id;
      if (blocked(modelBlock) || blocked(pairBlock)) continue;
      if (attempts >= 4 || now() >= deadline) break;
      const allowed = (await options.checkEligibility?.(key)) ?? "active";
      if (allowed === "provider-disabled") return result(409);
      if (allowed === "key-disabled") break;
      if (now() >= deadline) break;
      attempts++;
      const signal = AbortSignal.timeout(Math.max(1, Math.min(20_000, deadline - now())));
      let response: Response;
      try {
        response = await options.request(key, model, signal);
        if (response.ok) {
          const json = await response.json();
          const candidate = json.choices?.[0];
          if (
            candidate?.finish_reason === "content_filter" ||
            candidate?.message?.refusal ||
            json.error?.code === "content_filter"
          )
            return result(422);
          let content: unknown = candidate?.message?.content;
          if (typeof content === "string") {
            content = content.replace(/<think(?:ing)?>[\s\S]*?<\/think(?:ing)?>/gi, "").trim();
          }
          if (
            typeof content === "string" &&
            content &&
            !/<think(?:ing)?>/i.test(content) &&
            json.choices?.[0]?.finish_reason !== "length"
          ) {
            state.activeKeyId = key.id;
            state.activeModel = model.id;
            return result(
              200,
              model,
              Response.json({
                choices: [{ message: { content } }],
                usage: json.usage,
              }),
            );
          }
          response = new Response(null, { status: 502 });
        }
      } catch {
        response = new Response(null, { status: 504 });
      }
      const status = response.status;
      const retryAfter = response.headers.get("retry-after");
      await response.body?.cancel().catch(() => undefined);
      if (status === 401) {
        invalidKeys.push(key.id);
        cool("key:" + key.id, 600_000);
        break;
      }
      if (status === 429) {
        cool("key:" + key.id, retryDelay(retryAfter, 60_000));
        break;
      }
      if (status === 402) {
        cool("trial", retryDelay(retryAfter, 300_000));
        return result(402);
      }
      if (status === 404 || status === 410) cool(modelBlock, 600_000);
      else if (status === 403) cool(pairBlock, 60_000);
      else if (status === 408 || (status >= 500 && status <= 599))
        cool(modelBlock, retryDelay(retryAfter, 30_000));
      else return result(status);
    }
    if (attempts >= 4 || now() >= deadline) break;
  }
  const keysCooling = keys.length > 0 && keys.every((key) => blocked("key:" + key.id));
  if (options.image && !hasCompatibleModel && !keysCooling) return result(422);
  const until = Math.min(...Object.values(state.cooldowns));
  const response = new Response(null, {
    status: keysCooling ? 429 : 503,
    headers: Number.isFinite(until)
      ? { "retry-after": String(Math.max(1, Math.ceil((until - now()) / 1000))) }
      : undefined,
  });
  return result(response.status, null, response);
}
