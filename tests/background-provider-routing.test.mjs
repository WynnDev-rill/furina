import assert from "node:assert/strict";
import test from "node:test";
import { requestBackgroundChain } from "../src/lib/background-provider-routing.ts";

function providers(statuses, enabled, calls) {
  return ["OpenRouter", "NVIDIA", "Lovable"].map((name, index) => ({
    name,
    enabled: enabled[index],
    request: async () => {
      calls.push(name);
      return new Response(null, { status: statuses[index] });
    },
  }));
}

test("OpenRouter credit exhaustion sends background work to NVIDIA first", async () => {
  const calls = [];
  const result = await requestBackgroundChain(
    providers([402, 200, 200], [true, true, true], calls),
  );
  assert.deepEqual(calls, ["OpenRouter", "NVIDIA"]);
  assert.equal(result.provider, "NVIDIA");
  assert.deepEqual(result.failures, [{ name: "OpenRouter", status: 402 }]);
});

test("Lovable is the final fallback only when enabled", async () => {
  for (const enabled of [false, true]) {
    const calls = [];
    const result = await requestBackgroundChain(
      providers([429, 503, 200], [true, true, enabled], calls),
    );
    assert.deepEqual(
      calls,
      enabled ? ["OpenRouter", "NVIDIA", "Lovable"] : ["OpenRouter", "NVIDIA"],
    );
    assert.equal(result.provider, enabled ? "Lovable" : null);
    assert.equal(result.response.status, enabled ? 200 : 503);
  }
});

test("disabled OpenRouter and Lovable are skipped when NVIDIA is selected", async () => {
  const calls = [];
  const result = await requestBackgroundChain(
    providers([200, 200, 200], [false, true, false], calls),
  );
  assert.deepEqual(calls, ["NVIDIA"]);
  assert.equal(result.provider, "NVIDIA");
});
