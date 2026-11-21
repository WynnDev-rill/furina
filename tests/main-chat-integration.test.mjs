import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { sourceServerHandler } from "./source-function.mjs";
import { mainChatProvider } from "../src/lib/main-chat-provider.ts";
import { requestWithProviderFallback } from "../src/lib/model-fallback.ts";
import { historyAfter } from "../src/lib/memory-policy.ts";
import { recallContext, recallQuery } from "../src/lib/memory-recall.ts";
import { emptyIdentity, identityPrompt } from "../src/lib/identity-core.ts";
import { birthdayInstructions, splitBirthdayReply, localCalendar } from "../src/lib/birth-date.ts";
const source = readFileSync(new URL("../src/lib/furina.functions.ts", import.meta.url), "utf8");
const persona = source.split("const DEFAULT_PERSONA = `")[1].split("`;")[0];
async function call(provider, status = 200) {
  let captured;
  let usage = 0;
  let gateway = 0;
  const response = () =>
    Response.json(
      {
        choices: [{ message: { content: "Aku ingat.<<<SPLIT>>>Kita mengujinya satu per satu." } }],
        usage: { total_tokens: 30 },
      },
      { status },
    );
  const deps = {
    mainChatProvider,
    requireFurinaIdentity: async () => {},
    getRequest: () =>
      new Request("https://test.invalid", { headers: { authorization: "Bearer synthetic" } }),
    readMemoryPolicy: async () => ({ use_saved: true, use_history: true, history_after: null }),
    profileContext: async () => ({
      profile: null,
      birthday: { age: 21 },
      prompt: "Konteks usia dewasa.",
    }),
    loadIdentity: async () => ({ state: emptyIdentity() }),
    readAiPreferences: async () => ({
      chat_provider: provider,
      use_nvidia_chat: true,
      use_gemini: true,
      lovable_chat: false,
      lovable_background: false,
    }),
    historyAfter,
    continuationRequest: () => ({ mode: "related", terms: [] }),
    recallQuery,
    shouldConsiderRecent: () => false,
    recallContext,
    localCalendar,
    supabaseAdmin: {
      rpc: async () => ({
        data: [
          {
            id: "saved-note",
            source: "saved",
            content: "SmartClip diuji satu per satu di ponsel.",
            occurred_at: null,
          },
        ],
        error: null,
      }),
      from: () => {
        const q = {
          select() {
            return q;
          },
          eq() {
            return q;
          },
          order() {
            return q;
          },
          limit: async () => ({ data: [] }),
        };
        return q;
      },
    },
    birthdayInstructions,
    splitBirthdayReply,
    identityPrompt,
    DEFAULT_PERSONA: persona,
    CHARACTER_ID: "furina",
    realtimeContextString: () => "Waktu uji tetap.",
    computeTimeCtx: () => ({ hari: "Rabu", periode: "pagi", hour: 8, weekend: false }),
    feedbackPrompt: () => "",
    requestGeminiChat: async (_id, messages) => {
      captured = messages;
      return response();
    },
    requestWithProviderFallback,
    recordChatUsage: async () => {
      usage++;
    },
    requestWithChatModelFallback: async () => {
      gateway++;
      assert.fail("paid fallback");
    },
  };
  const handler = sourceServerHandler("../src/lib/furina.functions.ts", "chatWithFurina", deps);
  const input = {
    userId: "owner",
    messages: [
      { role: "user", content: "Proyekku SmartClip.", at: 1000 },
      { role: "assistant", content: "Kita periksa perlahan.", at: 1001 },
      { role: "user", content: "Kamu ingat SmartClip?", at: 1002 },
    ],
    characterName: "Furina",
    language: "id",
    systemPersona: "Tetap singkat.",
    replay: false,
    responseFeedback: [],
    clientNow: 1003,
    tz: "UTC",
    imageDataUrl: "data:image/png;base64,YQ==",
    quote: { id: "quote", role: "assistant", excerpt: "Kita periksa perlahan." },
  };
  const result = await handler({ data: input });
  return { result, captured, usage, gateway };
}
test("main handler uses the same full Furina persona, saved memory, quote, history, image and age context for existing Gemini settings and retired NVIDIA preferences", async () => {
  const gemini = await call("gemini");
  const nvidia = await call("nvidia");
  assert.deepEqual(nvidia.captured, gemini.captured);
  assert.match(nvidia.captured[0].content, /Kamu adalah Furina/);
  assert.match(nvidia.captured[0].content, /SmartClip diuji satu per satu di ponsel/);
  assert.match(nvidia.captured[0].content, /Konteks usia dewasa/);
  assert.deepEqual(nvidia.captured.at(-1).content[1], {
    type: "image_url",
    image_url: { url: "data:image/png;base64,YQ==" },
  });
  assert.match(nvidia.captured.at(-1).content[0].text, /Kita periksa perlahan/);
  assert.equal(nvidia.usage, 1);
  assert.equal(nvidia.gateway, 0);
  assert.equal(nvidia.result.aiProvider, "gemini");
  assert.equal(nvidia.result.aiModel, null);
  assert.equal(nvidia.result.bubbles.length, 2);
});
