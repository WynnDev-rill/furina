import { isGeminiUnavailable } from "./model-fallback.ts";

export const GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta";
const GEMINI_MODELS = [
  { id: "gemini-3.8-flash", thinkingLevel: "LOW", timeout: 12_000 },
  { id: "gemini-3.6-flash", thinkingLevel: "MINIMAL", timeout: 16_000 },
] as const;

type ChatPart = { type: "text"; text: string } | { type: "image_url"; image_url: { url: string } };

export type GeminiChatMessage = {
  role: "system" | "user" | "assistant";
  content: string | ChatPart[];
};

type GeminiPart = { text: string } | { inlineData: { mimeType: string; data: string } };

function toGeminiContent(messages: GeminiChatMessage[]) {
  const system: GeminiPart[] = [];
  const contents: { role: "user" | "model"; parts: GeminiPart[] }[] = [];
  for (const { role, content } of messages) {
    const parts =
      typeof content === "string"
        ? [{ text: content }]
        : content.map((part) => {
            if (part.type === "text") return { text: part.text };
            const image = /^data:(image\/[\w.+-]+);base64,([A-Za-z0-9+/=]+)$/i.exec(
              part.image_url.url,
            );
            if (!image) throw new Error("Lampiran gambar tidak dapat dibaca.");
            return { inlineData: { mimeType: image[1], data: image[2] } };
          });
    if (role === "system") system.push(...parts);
    else contents.push({ role: role === "assistant" ? "model" : "user", parts });
  }
  return { systemInstruction: { parts: system }, contents };
}

type GeminiReply = {
  promptFeedback?: { blockReason?: string };
  candidates?: {
    finishReason?: string;
    content?: { parts?: { text?: string; thought?: boolean }[] };
  }[];
  usageMetadata?: { totalTokenCount?: number };
};

export async function requestGeminiCompletion(
  key: string,
  messages: GeminiChatMessage[],
  deadline: number,
  request = fetch,
): Promise<Response> {
  const input = toGeminiContent(messages);
  let last = new Response(null, { status: 504 });
  for (const model of GEMINI_MODELS) {
    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    await last.body?.cancel().catch(() => undefined);
    last = await request(`${GEMINI_BASE}/models/${model.id}:generateContent`, {
      method: "POST",
      redirect: "manual",
      signal: AbortSignal.timeout(Math.min(model.timeout, remaining)),
      headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
      body: JSON.stringify({
        ...input,
        generationConfig: { thinkingConfig: { thinkingLevel: model.thinkingLevel } },
      }),
    }).then(
      async (response) => {
        if (!response.ok) return response;
        const payload: GeminiReply | null = await response.json().catch(() => null);
        const candidate = payload?.candidates?.[0];
        const blocked =
          payload?.promptFeedback?.blockReason ||
          /SAFETY|RECITATION|PROHIBITED_CONTENT|BLOCKLIST|SPII|IMAGE_PROHIBITED_CONTENT/.test(
            candidate?.finishReason ?? "",
          );
        if (blocked) return new Response(null, { status: 422 });
        const content = candidate?.content?.parts
          ?.filter((part) => !part.thought && typeof part.text === "string")
          .map((part) => part.text)
          .join("");
        if (content?.trim()) {
          return Response.json({
            choices: [{ message: { content } }],
            usage: { total_tokens: payload?.usageMetadata?.totalTokenCount },
          });
        }
        return new Response(null, { status: 502 });
      },
      () => new Response(null, { status: 504 }),
    );
    if (!isGeminiUnavailable(last.status) && last.status !== 404) return last;
  }
  return last;
}

export async function validateGeminiModelAccess(key: string) {
  for (const [index, model] of GEMINI_MODELS.entries()) {
    const response = await fetch(`${GEMINI_BASE}/models/${model.id}`, {
      redirect: "manual",
      signal: AbortSignal.timeout(8000),
      headers: { "x-goog-api-key": key },
    }).catch(() => new Response(null, { status: 504 }));
    if (
      index === GEMINI_MODELS.length - 1 ||
      (response.status !== 404 && !isGeminiUnavailable(response.status))
    )
      return response;
    await response.body?.cancel().catch(() => undefined);
  }
  return new Response(null, { status: 504 });
}
