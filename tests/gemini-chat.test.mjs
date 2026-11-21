import assert from "node:assert/strict";
import test from "node:test";
import { requestGeminiCompletion } from "../src/lib/gemini-chat.ts";

const messages = [
  { role: "system", content: "Jawab dalam bahasa Indonesia." },
  { role: "user", content: "Halo." },
  { role: "assistant", content: "Halo juga." },
  {
    role: "user",
    content: [
      { type: "text", text: "Apa ini?" },
      { type: "image_url", image_url: { url: "data:image/jpeg;base64,YQ==" } },
    ],
  },
];

test("native Gemini preserves persona, history, image, text and token usage", async () => {
  const response = await requestGeminiCompletion(
    "synthetic",
    messages,
    Date.now() + 5000,
    async (url, init) => {
      assert.match(url, /gemini-3\.8-flash:generateContent$/);
      assert.equal(init.redirect, "manual");
      assert.equal(init.headers["x-goog-api-key"], "synthetic");
      assert.deepEqual(JSON.parse(init.body), {
        systemInstruction: { parts: [{ text: "Jawab dalam bahasa Indonesia." }] },
        contents: [
          { role: "user", parts: [{ text: "Halo." }] },
          { role: "model", parts: [{ text: "Halo juga." }] },
          {
            role: "user",
            parts: [{ text: "Apa ini?" }, { inlineData: { mimeType: "image/jpeg", data: "YQ==" } }],
          },
        ],
        generationConfig: { thinkingConfig: { thinkingLevel: "LOW" } },
      });
      return Response.json({
        candidates: [
          {
            content: {
              parts: [
                { text: "private reasoning", thought: true },
                { text: "Ini " },
                { text: "gambar." },
              ],
            },
          },
        ],
        usageMetadata: { totalTokenCount: 19 },
      });
    },
  );
  assert.deepEqual(await response.json(), {
    choices: [{ message: { content: "Ini gambar." } }],
    usage: { total_tokens: 19 },
  });
});

test("Gemini transport failures and overload switch models with the same key", async () => {
  for (const unavailable of [
    async () => {
      throw new DOMException("timed out", "TimeoutError");
    },
    async () => new Response(null, { status: 503 }),
  ]) {
    const models = [];
    const result = await requestGeminiCompletion(
      "synthetic",
      messages,
      Date.now() + 5000,
      async (url, init) => {
        models.push(url.match(/models\/(.*):generateContent$/)[1]);
        assert.equal(init.headers["x-goog-api-key"], "synthetic");
        if (models.length === 1) return unavailable();
        assert.equal(
          JSON.parse(init.body).generationConfig.thinkingConfig.thinkingLevel,
          "MINIMAL",
        );
        return Response.json({
          candidates: [{ content: { parts: [{ text: "Balasan cadangan" }] } }],
        });
      },
    );
    assert.equal(result.status, 200);
    assert.deepEqual(models, ["gemini-3.8-flash", "gemini-3.6-flash"]);
  }
});

test("Gemini quota, credential and safety responses do not trigger model retry", async () => {
  for (const [expected, upstream] of [
    [429, () => new Response(null, { status: 429 })],
    [403, () => new Response(null, { status: 403 })],
    [422, () => Response.json({ promptFeedback: { blockReason: "SAFETY" } })],
  ]) {
    let attempts = 0;
    const response = await requestGeminiCompletion(
      "synthetic",
      messages,
      Date.now() + 5000,
      async () => {
        attempts++;
        return upstream();
      },
    );
    assert.equal(attempts, 1);
    assert.equal(response.status, expected);
  }
});

test("a blocked Gemini candidate never exposes partial text or retries", async () => {
  for (const feedback of [
    { finishReason: "SAFETY" },
    { finishReason: "RECITATION" },
    { blockReason: "SAFETY" },
  ]) {
    let calls = 0;
    const response = await requestGeminiCompletion(
      "synthetic",
      messages,
      Date.now() + 5000,
      async () => {
        calls++;
        return Response.json({
          promptFeedback: { blockReason: feedback.blockReason },
          candidates: [
            {
              finishReason: feedback.finishReason,
              content: { parts: [{ text: "partial blocked reply" }] },
            },
          ],
        });
      },
    );
    assert.equal(response.status, 422);
    assert.equal(calls, 1);
    assert.equal(await response.text(), "");
  }
});
