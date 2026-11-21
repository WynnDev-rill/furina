import assert from "node:assert/strict";
import test from "node:test";
import {
  CHAT_MODEL_FALLBACK_ORDER,
  isChatProviderFallbackStatus,
  requestWithChatModelFallback,
  requestWithProviderFallback,
} from "../src/lib/model-fallback.ts";

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

test("disabled personal Gemini is never called, including when Lovable hits its quota", async () => {
  for (const status of [200, 429, 402]) {
    const calls = [];
    const result = await requestWithProviderFallback(
      false,
      async () => {
        calls.push("gemini");
        return new Response("personal", { status: 200 });
      },
      async () => {
        calls.push("lovable");
        return new Response("limited", { status });
      },
    );
    assert.deepEqual(calls, ["lovable"]);
    assert.equal(result.provider, "lovable");
    assert.equal(result.response.status, status);
  }
});

test("Gemini direct preference reverses priority and falls back to Lovable only on 429 or 402", async () => {
  for (const status of [429, 402]) {
    const calls = [];
    const result = await requestWithProviderFallback(
      true,
      async () => {
        calls.push("gemini");
        return new Response("limited", { status });
      },
      async () => {
        calls.push("lovable");
        return new Response("ok", { status: 200 });
      },
    );
    assert.deepEqual(calls, ["gemini", "lovable"]);
    assert.equal(result.provider, "lovable");
  }
});

test("provider routing does not switch on unrelated errors", async () => {
  for (const status of [400, 401, 403, 404, 500, 503]) {
    assert.equal(isChatProviderFallbackStatus(status), false);
    const calls = [];
    const result = await requestWithProviderFallback(
      false,
      async () => {
        calls.push("gemini");
        return new Response("unused", { status: 200 });
      },
      async () => {
        calls.push("lovable");
        return new Response("terminal", { status });
      },
    );
    assert.deepEqual(calls, ["lovable"]);
    assert.equal(result.response.status, status);
  }
});

test("Gemini overload falls back to Lovable and preserves the Gemini cause if both are unavailable", async () => {
  for (const status of [500, 502, 503, 504]) {
    const gemini = new Response(null, { status });
    const recovered = await requestWithProviderFallback(
      true,
      async () => gemini,
      async () => new Response("ok"),
    );
    assert.equal(recovered.provider, "lovable");
    assert.equal(recovered.response.status, 200);
    const failed = await requestWithProviderFallback(
      true,
      async () => gemini,
      async () => new Response(null, { status: 402 }),
    );
    assert.equal(failed.provider, "gemini");
    assert.equal(failed.response, gemini);
  }
});

test("Gemini safety and access errors do not forward the chat to Lovable", async () => {
  for (const status of [400, 403, 422]) {
    const response = new Response(null, { status });
    const result = await requestWithProviderFallback(
      true,
      async () => response,
      async () => assert.fail("unexpected fallback"),
    );
    assert.equal(result.response, response);
  }
});

test("provider fallback releases only discarded responses", async () => {
  for (const gatewayStatus of [200, 503]) {
    const cancelled = [];
    const stream = (name) =>
      new ReadableStream({
        cancel() {
          cancelled.push(name);
        },
      });
    const gemini = new Response(stream("gemini"), { status: 503 });
    const gateway = new Response(stream("lovable"), { status: gatewayStatus });
    const result = await requestWithProviderFallback(
      true,
      async () => gemini,
      async () => gateway,
    );
    assert.equal(result.response, gatewayStatus === 200 ? gateway : gemini);
    assert.deepEqual(cancelled, [gatewayStatus === 200 ? "gemini" : "lovable"]);
    await result.response.body.cancel();
  }
});

test("a thrown gateway request releases quota responses and preserves unavailable Gemini causes", async () => {
  for (const status of [429, 503]) {
    let cancelled = false;
    const gemini = new Response(
      new ReadableStream({
        cancel() {
          cancelled = true;
        },
      }),
      { status },
    );
    const run = () =>
      requestWithProviderFallback(
        true,
        async () => gemini,
        async () => {
          throw new Error("transport");
        },
      );
    if (status === 429) {
      await assert.rejects(run(), /transport/);
      assert.equal(cancelled, true);
    } else {
      assert.equal((await run()).response, gemini);
      assert.equal(cancelled, false);
      await gemini.body.cancel();
    }
  }
});
