import assert from "node:assert/strict";
import test from "node:test";
import { sourceFunction } from "./source-function.mjs";
import { routeNvidiaChat } from "../src/lib/nvidia-chat-routing.ts";
const models = [{ id: "nvidia/nemotron-3.5-bolt-e4b", label: "Bolt", vision: false }];
function validator(status, calls) {
  return sourceFunction("../src/lib/nvidia-chat.server.ts", "validateNvidiaChatKey", {
    discoverNvidiaChatModels: async () => models,
    routeNvidiaChat,
    NVIDIA: "https://integrate.api.nvidia.com/v1",
    fetch: async (url, init) => {
      calls.push(url);
      assert.equal(url, "https://integrate.api.nvidia.com/v1/chat/completions");
      assert.equal(init.redirect, "manual");
      const body = JSON.parse(init.body);
      assert.ok(body.max_tokens <= 32);
      assert.deepEqual(body.messages, [{ role: "user", content: "Reply only OK." }]);
      return status === 200
        ? Response.json({ choices: [{ message: { content: "OK" } }] })
        : new Response(null, { status });
    },
  });
}
test("a public 200 model catalog cannot validate a rejected or quota-blocked NVIDIA key", async () => {
  for (const status of [401, 402, 429]) {
    const calls = [];
    await assert.rejects(validator(status, calls)("nvapi-synthetic"));
    assert.equal(calls.length, 1);
  }
});
test("saving credentials requires a tiny authenticated verified-free completion", async () => {
  const calls = [];
  assert.deepEqual(await validator(200, calls)("nvapi-synthetic"), models);
  assert.equal(calls.length, 1);
});
