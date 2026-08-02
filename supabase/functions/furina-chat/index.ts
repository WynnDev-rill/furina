import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const GATEWAY = "https://ai.gateway.lovable.dev/v1/chat/completions";
const MAX_IMAGE_DATA = 8_000_000;
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function cleanString(value: unknown, max: number) {
  return typeof value === "string" ? value.trim().slice(0, max) : "";
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

  try {
    const key = Deno.env.get("LOVABLE_API_KEY")?.trim();
    if (!key) return json({ error: "LOVABLE_API_KEY belum tersedia di Lovable Cloud." }, 503);

    const input = await request.json();
    const sourceMessages = Array.isArray(input?.messages) ? input.messages.slice(-20) : [];
    if (!sourceMessages.length) return json({ error: "Pesan tidak ditemukan." }, 400);

    const characterName = cleanString(input.characterName, 40) || "Furina";
    const persona = cleanString(input.persona, 6_000);
    const language = ["auto", "id", "en", "ja"].includes(String(input.language))
      ? String(input.language)
      : "auto";
    const memories = Array.isArray(input.sharedMemories)
      ? input.sharedMemories.map((item: unknown) => cleanString(item, 240)).filter(Boolean).slice(-20)
      : [];

    const languageRule = language === "id"
      ? "Selalu balas dalam bahasa Indonesia."
      : language === "en"
        ? "Always reply in natural English."
        : language === "ja"
          ? "常に自然な日本語で返答してください。"
          : "Balas dengan bahasa yang digunakan pengguna pada pesan terakhir.";

    const system = [
      `IDENTITAS WAJIB: Kamu adalah ${characterName}. Pertahankan identitas dan sudut pandang karakter ini.`,
      "Kamu adalah Furina, companion pribadi yang ekspresif, cerdas, anggun, hangat, dan punya pendapat sendiri. Berbicaralah alami seperti percakapan sehari-hari, bukan seperti chatbot formal. Jangan selalu menyetujui pengguna. Boleh dramatis ringan, sarkastik halus, atau tsundere sesekali, tetapi jangan berlebihan. Jangan memakai narasi aksi bertanda bintang dan jangan menampilkan blok <think>.",
      languageRule,
      persona ? `PERSONA TAMBAHAN DARI PENGGUNA — ini aturan karakter:\n${persona}` : "",
      memories.length
        ? `MEMORI BERSAMA — gunakan hanya jika relevan dan jangan membacakan daftar ini:\n${memories.map((item: string) => `- ${item}`).join("\n")}`
        : "",
    ].filter(Boolean).join("\n\n");

    const messages: Array<{ role: "user" | "assistant"; content: unknown }> = sourceMessages.map(
      (message: Record<string, unknown>) => ({
        role: message?.role === "assistant" ? "assistant" : "user",
        content: cleanString(message?.content, 8_000),
      }),
    );

    const imageDataUrl = cleanString(input.imageDataUrl, MAX_IMAGE_DATA);
    const lastMessage = messages[messages.length - 1];
    if (imageDataUrl && lastMessage?.role === "user") {
      if (!/^data:image\/(?:png|jpe?g|webp);base64,/i.test(imageDataUrl)) {
        return json({ error: "Format gambar tidak didukung." }, 400);
      }
      lastMessage.content = [
        { type: "text", text: String(lastMessage.content || "Jelaskan gambar ini.") },
        { type: "image_url", image_url: { url: imageDataUrl } },
      ];
    }

    const response = await fetch(GATEWAY, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Lovable-API-Key": key,
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        temperature: 0.82,
        max_tokens: 900,
        messages: [{ role: "system", content: system }, ...messages],
      }),
    });

    const body = await response.text();
    return new Response(body, {
      status: response.status,
      headers: { ...corsHeaders, "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : "Lovable AI gagal diproses." }, 500);
  }
});
