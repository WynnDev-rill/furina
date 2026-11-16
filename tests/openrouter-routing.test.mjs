import assert from "node:assert/strict";
import test from "node:test";
import { requestOpenRouter } from "../src/lib/openrouter-routing.ts";
import { requestWithProviderFallback } from "../src/lib/model-fallback.ts";

test("OpenRouter rotates quota-limited keys and flags rejected keys", async () => {
  const attempted = [];
  const invalid = [];
  const result = await requestOpenRouter(
    ["unreadable", "quota", "invalid", "active"],
    async (row) => row === "unreadable" ? null : row,
    async (key) => {
      attempted.push(key);
      return new Response(null, { status: { quota: 402, invalid: 401, active: 200 }[key] });
    },
    async (row) => { invalid.push(row); },
  );
  assert.deepEqual(attempted, ["quota", "invalid", "active"]);
  assert.deepEqual(invalid, ["invalid"]);
  assert.equal(result.status, 200);
});

test("OpenRouter stops on request errors that do not benefit from key rotation", async () => {
  let calls = 0;
  const result = await requestOpenRouter(["a", "b"], async (row) => row,
    async () => { calls++; return new Response(null, { status: 400 }); },
    async () => assert.fail("a request error must not invalidate a key"));
  assert.equal(calls, 1);
  assert.equal(result.status, 400);
});

test("Gemini-only chat never substitutes an inactive Lovable gateway", async () => {
  for (const status of [200, 402, 429, 503]) {
    const result = await requestWithProviderFallback(true, async () => new Response(null, { status }), null);
    assert.equal(result.provider, "gemini");
    assert.equal(result.response.status, status);
  }
});
