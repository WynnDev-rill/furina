import assert from "node:assert/strict";
import test from "node:test";
import { routeNvidiaChat } from "../src/lib/nvidia-chat-routing.ts";
const a = { id: "minimaxai/minimax-m3.1-flash", label: "MiniMax", vision: true };
const b = { id: "nvidia/nemotron-3-ultra-550b-a55b", label: "Nemotron", vision: false };
const empty = () => ({ activeModel: null, activeKeyId: null, cooldowns: {} });
const keys = [
  { id: "key-a", models: [a, b] },
  { id: "key-b", models: [a, b] },
];
const reply = (text = "Halo.") =>
  Response.json({ choices: [{ message: { content: text } }], usage: { total_tokens: 25 } });

test("a healthy active model and key are kept even when ranked lower", async () => {
  const result = await routeNvidiaChat({
    keys,
    state: { ...empty(), activeModel: b.id, activeKeyId: "key-b" },
    request: async (key, model) => {
      assert.equal(key.id, "key-b");
      assert.equal(model.id, b.id);
      return reply();
    },
  });
  assert.equal(result.attempts, 1);
  assert.equal(result.model.id, b.id);
  assert.equal((await result.response.json()).choices[0].message.content, "Halo.");
});
test("rate limited keys cool down using Retry-After and rotate without duplicating a response", async () => {
  const calls = [];
  const result = await routeNvidiaChat({
    keys,
    state: empty(),
    now: () => 1000,
    request: async (key, model) => {
      calls.push([key.id, model.id]);
      return key.id === "key-a"
        ? new Response(null, { status: 429, headers: { "retry-after": "120" } })
        : reply();
    },
  });
  assert.deepEqual(calls, [
    ["key-a", a.id],
    ["key-b", a.id],
  ]);
  assert.equal(result.state.cooldowns["key:key-a"], 121000);
  assert.equal((await result.response.json()).choices.length, 1);
});
test("unavailable and removed models rotate while preserving the useful key", async () => {
  for (const status of [500, 502, 503, 504, 404, 410]) {
    const result = await routeNvidiaChat({
      keys,
      state: empty(),
      request: async (_key, model) =>
        model.id === a.id ? new Response(null, { status }) : reply(),
    });
    assert.equal(result.model.id, b.id);
    assert.equal(result.state.activeKeyId, "key-a");
    assert.equal(result.attempts, 2);
  }
});
test("transport timeouts rotate to a different model", async () => {
  const result = await routeNvidiaChat({
    keys,
    state: empty(),
    request: async (_key, model) => {
      if (model.id === a.id) throw new DOMException("timeout", "TimeoutError");
      return reply();
    },
  });
  assert.equal(result.model.id, b.id);
});
test("rejected credentials are flagged without leaking or returning their contents", async () => {
  const result = await routeNvidiaChat({
    keys,
    state: empty(),
    request: async (key) =>
      key.id === "key-a" ? new Response("private credential detail", { status: 401 }) : reply(),
  });
  assert.deepEqual(result.invalidKeys, ["key-a"]);
  assert.equal(result.state.activeKeyId, "key-b");
  assert.doesNotMatch(await result.response.text(), /private/);
});
test("cooldowns survive a new request and no network call is made when all keys are cooling", async () => {
  const state = { ...empty(), cooldowns: { "key:key-a": 90000, "key:key-b": 90000 } };
  const result = await routeNvidiaChat({
    keys,
    state,
    now: () => 1000,
    request: async () => assert.fail("cooling key must not be called"),
  });
  assert.equal(result.response.status, 429);
  assert.equal(result.attempts, 0);
  assert.ok(Number(result.response.headers.get("retry-after")) > 0);
});
test("input and safety failures never fan out to another key or model", async () => {
  for (const status of [400, 422]) {
    const result = await routeNvidiaChat({
      keys,
      state: empty(),
      request: async () => new Response(null, { status }),
    });
    assert.equal(result.attempts, 1);
    assert.equal(result.response.status, status);
  }
});
test("exhausted trial credits never fall through to a paid provider", async () => {
  const result = await routeNvidiaChat({
    keys,
    state: empty(),
    request: async () => new Response(null, { status: 402 }),
  });
  assert.equal(result.response.status, 402);
  assert.equal(result.attempts, 1);
});
test("empty or thinking-only successful replies fail over without exposing reasoning", async () => {
  for (const content of [null, "", "<think>private reasoning</think>", "<think>unfinished"]) {
    const result = await routeNvidiaChat({
      keys,
      state: empty(),
      request: async (_key, model) => (model.id === a.id ? reply(content) : reply()),
    });
    assert.equal(result.model.id, b.id);
    assert.equal((await result.response.json()).choices[0].message.content, "Halo.");
  }
});
test("reasoning blocks are stripped from visible content", async () => {
  const result = await routeNvidiaChat({
    keys,
    state: empty(),
    request: async () => reply("<think>private</think>Halo."),
  });
  assert.equal((await result.response.json()).choices[0].message.content, "Halo.");
});
test("image turns never silently use a text-only model", async () => {
  const result = await routeNvidiaChat({
    keys: [{ id: "key", models: [b] }],
    state: empty(),
    image: true,
    request: async () => assert.fail("image dropped"),
  });
  assert.equal(result.response.status, 422);
  assert.equal(result.attempts, 0);
});
test("active models withdrawn from the verified catalog are not retried", async () => {
  const result = await routeNvidiaChat({
    keys: [{ id: "key", models: [a] }],
    state: { ...empty(), activeModel: b.id },
    request: async (_key, model) => {
      assert.equal(model.id, a.id);
      return reply();
    },
  });
  assert.equal(result.model.id, a.id);
});
test("fallback attempts have a hard bound", async () => {
  const many = Array.from({ length: 20 }, (_, i) => ({ id: "key" + i, models: [a, b] }));
  const result = await routeNvidiaChat({
    keys: many,
    state: empty(),
    request: async () => new Response(null, { status: 403 }),
  });
  assert.equal(result.attempts, 4);
  assert.equal(result.response.status, 503);
});

test("long provider Retry-After cooldowns are not shortened", async () => {
  const result = await routeNvidiaChat({
    keys: [keys[0]],
    state: empty(),
    now: () => 1000,
    request: async () => new Response(null, { status: 429, headers: { "retry-after": "3600" } }),
  });
  assert.equal(result.state.cooldowns["key:key-a"], 3601000);
});

test("moderation stops the turn instead of retrying empty or partial filtered output", async () => {
  for (const message of [
    { content: null },
    { content: "partial filtered answer" },
    { content: null, refusal: "Cannot comply" },
  ]) {
    const result = await routeNvidiaChat({
      keys,
      state: empty(),
      request: async () =>
        Response.json({
          choices: [{ finish_reason: message.refusal ? "stop" : "content_filter", message }],
        }),
    });
    assert.equal(result.response.status, 422);
    assert.equal(result.attempts, 1);
  }
});
test("models for backup keys are discovered only when the current key needs failover", async () => {
  let lookups = 0;
  const result = await routeNvidiaChat({
    keys: [
      { id: "a", models: [] },
      { id: "b", models: [] },
    ],
    state: empty(),
    loadModels: async () => {
      lookups++;
      return [a];
    },
    request: async () => reply(),
  });
  assert.equal(result.response.status, 200);
  assert.equal(lookups, 1);
});
test("provider changes abort a pending fallback and disabled keys are skipped before inference", async () => {
  let checks = 0;
  const result = await routeNvidiaChat({
    keys,
    state: empty(),
    checkEligibility: async () => (++checks > 2 ? "provider-disabled" : "active"),
    request: async () => new Response(null, { status: 503 }),
  });
  assert.equal(result.response.status, 409);
  assert.equal(result.attempts, 1);
  const disabled = await routeNvidiaChat({
    keys,
    state: empty(),
    checkEligibility: async (key) => (key.id === "key-a" ? "key-disabled" : "active"),
    request: async (key) => {
      assert.equal(key.id, "key-b");
      return reply();
    },
  });
  assert.equal(disabled.response.status, 200);
});

test("HTTP request timeouts rotate models and provider busy cooldown honors Retry-After", async () => {
  for (const status of [408, 503]) {
    const result = await routeNvidiaChat({
      keys,
      state: empty(),
      now: () => 1000,
      request: async (_key, model) =>
        model.id === a.id
          ? new Response(null, { status, headers: { "retry-after": "300" } })
          : reply(),
    });
    assert.equal(result.response.status, 200);
    assert.equal(result.model.id, b.id);
    assert.ok(result.state.cooldowns["model:" + a.id] >= 301000);
  }
});
test("exhausted free trial is backed off across subsequent messages", async () => {
  const first = await routeNvidiaChat({
    keys,
    state: empty(),
    now: () => 1000,
    request: async () => new Response(null, { status: 402 }),
  });
  const second = await routeNvidiaChat({
    keys,
    state: first.state,
    now: () => 1001,
    request: async () => assert.fail("exhausted account must cool down"),
  });
  assert.equal(second.response.status, 402);
  assert.equal(second.attempts, 0);
});
