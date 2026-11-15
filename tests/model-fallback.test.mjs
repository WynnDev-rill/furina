import assert from "node:assert/strict";
import test from "node:test";
import { CHAT_MODEL_FALLBACK_ORDER, requestWithChatModelFallback } from "../src/lib/model-fallback.ts";

test("chat fallback starts with Gemini 3.8 Flash and uses the requested order", () => {
  assert.deepEqual(CHAT_MODEL_FALLBACK_ORDER, [
    "google/gemini-3.8-flash",
    "google/gemini-3-flash-preview",
    "openai/gpt-5.4-mini",
  ]);
});

test("chat fallback advances only after 429 or 503 and stops on success", async () => {
  const calledModels = [];
  const result = await requestWithChatModelFallback(async (model) => {
    calledModels.push(model);
    if (calledModels.length === 1) return new Response("limited", { status: 429 });
    if (calledModels.length === 2) return new Response("unavailable", { status: 503 });
    return new Response("ok", { status: 200 });
  });

  assert.deepEqual(calledModels, CHAT_MODEL_FALLBACK_ORDER);
  assert.equal(result.model, "openai/gpt-5.4-mini");
  assert.equal(result.response.status, 200);
});

test("chat fallback stops after the first response outside 429 and 503", async () => {
  for (const status of [400, 401, 403, 404, 500, 502]) {
    const calledModels = [];
    const result = await requestWithChatModelFallback(async (model) => {
      calledModels.push(model);
      return new Response("terminal", { status });
    });

    assert.deepEqual(calledModels, ["google/gemini-3.8-flash"]);
    assert.equal(result.response.status, status);
  }
});

test("chat fallback does not advance for non-retryable statuses", async () => {
  const calledModels = [];
  const result = await requestWithChatModelFallback(async (model) => {
    calledModels.push(model);
    return new Response("blocked", { status: 402 });
  });

  assert.deepEqual(calledModels, ["google/gemini-3.8-flash"]);
  assert.equal(result.model, "google/gemini-3.8-flash");
  assert.equal(result.response.status, 402);
});

test("chat fallback returns the final retryable response after exhausting models", async () => {
  const calledModels = [];
  const result = await requestWithChatModelFallback(async (model) => {
    calledModels.push(model);
    return new Response("busy", { status: 503 });
  });

  assert.deepEqual(calledModels, CHAT_MODEL_FALLBACK_ORDER);
  assert.equal(result.model, "openai/gpt-5.4-mini");
  assert.equal(result.response.status, 503);
});