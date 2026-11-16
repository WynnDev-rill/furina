export const CHAT_MODEL_FALLBACK_ORDER = [
  "google/gemini-3.8-flash",
  "google/gemini-3-flash-preview",
  "openai/gpt-5.4-mini",
] as const;

export type ChatModel = (typeof CHAT_MODEL_FALLBACK_ORDER)[number];

export type ChatProvider = "gemini" | "lovable";

export function isChatProviderFallbackStatus(status: number): boolean {
  return status === 429 || status === 402;
}

export function isGeminiUnavailable(status: number) {
  return status === 500 || status === 502 || status === 503 || status === 504;
}

export async function requestWithProviderFallback(
  personalGeminiEnabled: boolean,
  requestGemini: () => Promise<Response | null>,
  requestLovable: () => Promise<Response>,
): Promise<{ response: Response; provider: ChatProvider }> {
  if (personalGeminiEnabled) {
    const gemini = await requestGemini();
    const unavailable = !!gemini && isGeminiUnavailable(gemini.status);
    if (gemini && !unavailable && !isChatProviderFallbackStatus(gemini.status)) {
      return { response: gemini, provider: "gemini" };
    }
    const lovable = await requestLovable().catch((error) => {
      if (unavailable && gemini) return gemini;
      throw error;
    });
    if (unavailable && gemini && !lovable.ok) return { response: gemini, provider: "gemini" };
    return { response: lovable, provider: "lovable" };
  }

  return { response: await requestLovable(), provider: "lovable" };
}

function retryDelayMs(response: Response, retryIndex: number): number {
  const retryAfter = response.headers.get("retry-after");
  if (response.status === 429 && retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds >= 0) return Math.min(1000, seconds * 1000);

    const retryAt = Date.parse(retryAfter);
    if (Number.isFinite(retryAt)) return Math.min(1000, Math.max(0, retryAt - Date.now()));
  }

  return 250 * 2 ** retryIndex + Math.floor(Math.random() * 250);
}

export async function requestWithChatModelFallback(
  request: (model: ChatModel) => Promise<Response>,
): Promise<{ response: Response; model: ChatModel }> {
  for (const [index, model] of CHAT_MODEL_FALLBACK_ORDER.entries()) {
    const response = await request(model);
    if ((response.status !== 429 && response.status !== 503) || index === CHAT_MODEL_FALLBACK_ORDER.length - 1) {
      return { response, model };
    }

    await response.body?.cancel().catch(() => undefined);
    await new Promise((resolve) => setTimeout(resolve, retryDelayMs(response, index)));
  }

  throw new Error("Chat model fallback order is empty");
}