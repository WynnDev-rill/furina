import assert from "node:assert/strict";
import test from "node:test";
import { sourceServerHandler } from "./source-function.mjs";
import { NVIDIA, NVIDIA_TEXT, NVIDIA_EMBEDDING } from "../src/lib/nvidia-ai.server.ts";

function setup(status = 200, malformed = false, failureEndpoint = null, vectorLength = 2048) {
  const calls = [];
  let saved = 0;
  const handler = sourceServerHandler("../src/lib/ai-usage.functions.ts", "addNvidiaKey", {
    NVIDIA,
    NVIDIA_TEXT,
    NVIDIA_EMBEDDING,
    requireFurinaIdentity: async () => {},
    fetch: async (url, init) => {
      calls.push({ url, init });
      if (url.endsWith("/models"))
        return Response.json({ data: [{ id: NVIDIA_TEXT }, { id: NVIDIA_EMBEDDING }] });
      if (status !== 200 && (!failureEndpoint || url.endsWith(failureEndpoint)))
        return new Response(null, { status });
      if (malformed) return Response.json({});
      return url.endsWith("/embeddings")
        ? Response.json({ data: [{ embedding: Array(vectorLength).fill(0.1) }] })
        : Response.json({ choices: [{ message: { content: "OK" } }] });
    },
    protectGeminiKey: async () => ({ box: "encrypted", fingerprint: "synthetic" }),
    encryptionSecret: () => "test",
    supabaseAdmin: {
      from: () => ({
        upsert: async () => {
          saved++;
          return {};
        },
      }),
    },
  });
  return {
    calls,
    saved: () => saved,
    run: () => handler({ data: { userId: "owner", key: "nvapi-synthetic" } }),
  };
}
test("public model listing cannot authorize saving an invalid/quota-blocked NVIDIA background key", async () => {
  for (const status of [401, 403, 402, 404, 429, 503]) {
    const fixture = setup(status);
    await assert.rejects(fixture.run());
    assert.equal(fixture.saved(), 0);
  }
});
test("NVIDIA background keys must pass bounded authenticated text and embedding probes", async () => {
  const fixture = setup();
  await fixture.run();
  const probes = fixture.calls.filter(({ url }) => !url.endsWith("/models"));
  assert.equal(probes.length, 2);
  for (const { init } of probes) {
    assert.equal(init.method, "POST");
    assert.equal(init.redirect, "manual");
    assert.equal(init.headers.Authorization, "Bearer nvapi-synthetic");
    assert.ok(init.signal instanceof AbortSignal);
    const body = JSON.parse(init.body);
    if (body.model === NVIDIA_TEXT) {
      assert.deepEqual(body.chat_template_kwargs, { enable_thinking: false });
      assert.ok(body.max_tokens <= 32);
    }
  }
  assert.equal(fixture.saved(), 1);
});
test("malformed successful NVIDIA probes do not validate a key", async () => {
  const fixture = setup(200, true);
  await assert.rejects(fixture.run());
  assert.equal(fixture.saved(), 0);
});

test("NVIDIA embedding access is required even after a successful text probe", async () => {
  for (const status of [401, 403, 402, 404, 429, 503]) {
    const fixture = setup(status, false, "/embeddings");
    await assert.rejects(fixture.run());
    assert.equal(fixture.calls.length, 2);
    assert.equal(fixture.saved(), 0);
  }
});
test("NVIDIA validation rejects embeddings incompatible with memory storage", async () => {
  for (const size of [0, 1, 1536, 2047, 2049]) {
    const fixture = setup(200, false, null, size);
    await assert.rejects(fixture.run());
    assert.equal(fixture.saved(), 0);
  }
});
