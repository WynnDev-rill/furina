import assert from "node:assert/strict";
import test from "node:test";
import { sourceFunction } from "./source-function.mjs";
import { routeNvidiaChat } from "../src/lib/nvidia-chat-routing.ts";
import { fetchAllPages } from "../src/lib/record-pagination.ts";
const model = { id: "minimaxai/minimax-m3.1-flash", label: "MiniMax", vision: true };
const backup = { id: "nvidia/nemotron-3-ultra-550b-a55b", label: "Nemotron", vision: false };
const messages = [
  { role: "system", content: "Furina persona + saved SmartClip memory + age context" },
  { role: "user", content: "Remember our phone project?" },
];
function fixture({
  discovery,
  cooling = false,
  status = 200,
  image = false,
  keyCount = 2,
  afterRequest,
  decrypt,
} = {}) {
  const persisted = [];
  const requests = [];
  const invalid = [];
  const usedKeys = [];
  const preferences = { user_id: "owner", chat_provider: "nvidia", use_nvidia_chat: true };
  const rows = [
    { id: "a", encrypted_value: "cipher-a", user_id: "owner", enabled: true, invalid: false },
    { id: "b", encrypted_value: "cipher-b", user_id: "owner", enabled: true, invalid: false },
  ];
  for (let i = 2; i < keyCount; i++)
    rows.push({
      id: "key" + i,
      encrypted_value: "cipher" + i,
      user_id: "owner",
      enabled: true,
      invalid: false,
    });
  const query = (table) => {
    let filtered = table === "furina_ai_preferences" ? [preferences] : rows;
    let patch;
    return {
      select() {
        return this;
      },
      eq(k, v) {
        filtered = filtered.filter((row) => row[k] === v);
        return this;
      },
      order() {
        return this;
      },
      range() {
        return Promise.resolve({ data: filtered, error: null });
      },
      maybeSingle() {
        return Promise.resolve({ data: filtered[0] ?? null, error: null });
      },
      update(value) {
        patch = value;
        invalid.push(value);
        return this;
      },
      then(resolve) {
        if (patch) filtered.forEach((row) => Object.assign(row, patch));
        return Promise.resolve({ data: [], error: null }).then(resolve);
      },
    };
  };
  const load = sourceFunction("../src/lib/nvidia-chat.server.ts", "requestNvidiaChat", {
    supabaseAdmin: {
      from: query,
      rpc: async (_name, args) => {
        persisted.push(args);
        return { error: null };
      },
    },
    checkNvidiaChatEligibility: sourceFunction(
      "../src/lib/nvidia-chat.server.ts",
      "checkNvidiaChatEligibility",
      { supabaseAdmin: { from: query } },
    ),
    loadNvidiaChatState: async () => ({
      state: {
        activeModel: null,
        activeKeyId: null,
        cooldowns: cooling ? { "key:a": Date.now() + 60000, "key:b": Date.now() + 60000 } : {},
      },
    }),
    fetchAllPages,
    openGeminiKey: async (cipher, owner, secret) => {
      assert.equal(owner, "owner");
      assert.equal(secret, "synthetic-secret");
      return decrypt ? decrypt(cipher) : cipher;
    },
    encryptionSecret: () => "synthetic-secret",
    discoverNvidiaChatModels: discovery ?? (async () => [model, backup]),
    clearNvidiaChatAccess: () => {},
    routeNvidiaChat,
    NVIDIA: "https://integrate.api.nvidia.com/v1",
    fetch: async (url, init) => {
      assert.equal(url, "https://integrate.api.nvidia.com/v1/chat/completions");
      assert.equal(init.redirect, "manual");
      requests.push(JSON.parse(init.body));
      usedKeys.push(init.headers.Authorization);
      afterRequest?.();
      return init.body.includes(model.id) && status !== 200
        ? new Response(null, { status })
        : Response.json({ choices: [{ message: { content: "Hello." } }] });
    },
  });
  return {
    run: () =>
      load(
        "owner",
        image
          ? [
              ...messages,
              {
                role: "user",
                content: [{ type: "image_url", image_url: { url: "data:image/png;base64,YQ==" } }],
              },
            ]
          : messages,
      ),
    rows,
    preferences,
    usedKeys,
    requests,
    persisted,
    invalid,
  };
}
test("all fallback models get exactly the same persona, memory, history and context", async () => {
  const f = fixture({ status: 503 });
  const result = await f.run();
  assert.equal(result.model, backup.id);
  assert.equal(f.requests.length, 2);
  for (const request of f.requests) {
    assert.deepEqual(request.messages, messages);
    assert.equal(request.stream, false);
    assert.deepEqual(request.chat_template_kwargs, { enable_thinking: false });
  }
  assert.equal(f.persisted[0].model_id, backup.id);
});
test("NVIDIA access rejection on one key can rotate to another key", async () => {
  const f = fixture({
    discovery: async (_key, id) => {
      if (id === "a") throw Object.assign(new Error("NVIDIA rejected key"), { status: 401 });
      return [model];
    },
  });
  const result = await f.run();
  assert.equal(result.response.status, 200);
  assert.equal(f.invalid.length, 1);
});
test("model discovery rate limits preserve cooldown and try another eligible key", async () => {
  const f = fixture({
    discovery: async (_key, id) => {
      if (id === "a")
        throw Object.assign(new Error("rate limited"), { status: 429, retryAfter: 120000 });
      return [model];
    },
  });
  const result = await f.run();
  assert.equal(result.response.status, 200);
  assert.ok(f.persisted[0].blocked_until["key:a"] > Date.now());
});
test("unverified free catalog errors never send any inference request", async () => {
  const f = fixture({
    discovery: async () => {
      throw new Error("free catalog unavailable");
    },
  });
  await assert.rejects(f.run(), /catalog/);
  assert.equal(f.requests.length, 0);
});
test("cooling keys make no discovery or inference requests even for images", async () => {
  const f = fixture({
    cooling: true,
    image: true,
    discovery: async () => assert.fail("must respect persisted cooldown"),
  });
  const result = await f.run();
  assert.equal(result.response.status, 429);
  assert.equal(f.requests.length, 0);
});

test("failed key discovery itself has a hard attempt bound", async () => {
  let calls = 0;
  const f = fixture({
    keyCount: 20,
    discovery: async () => {
      calls++;
      throw Object.assign(new Error("limited"), { status: 429, retryAfter: 60000 });
    },
  });
  await f.run();
  assert.equal(calls, 4);
});

test("a key disabled during discovery is never used for inference", async () => {
  let f;
  f = fixture({
    discovery: async (_key, id) => {
      if (id === "a") f.rows[0].enabled = false;
      return [model];
    },
  });
  const result = await f.run();
  assert.equal(result.response.status, 200);
  assert.deepEqual(f.usedKeys, ["Bearer cipher-b"]);
});
test("a provider switch between attempts stops further NVIDIA dispatches", async () => {
  let f;
  f = fixture({
    status: 503,
    afterRequest: () => {
      f.preferences.chat_provider = "gemini";
    },
  });
  const result = await f.run();
  assert.equal(result.response.status, 409);
  assert.equal(f.requests.length, 1);
});

test("undecryptable old keys are quarantined so a later working key is reachable", async () => {
  const broken = new Set(["cipher-a", "cipher-b", "cipher2", "cipher3"]);
  const f = fixture({
    keyCount: 6,
    decrypt: async (cipher) => (broken.has(cipher) ? null : cipher),
  });
  await f.run();
  assert.equal(f.invalid.length, 4);
  const result = await f.run();
  assert.equal(result.response.status, 200);
  assert.deepEqual(f.usedKeys, ["Bearer cipher4"]);
});
test("an account without active keys receives an actionable activation error", async () => {
  const f = fixture();
  f.rows.forEach((row) => (row.enabled = false));
  await assert.rejects(f.run(), /Tidak ada API key NVIDIA percakapan yang aktif/);
  assert.equal(f.requests.length, 0);
});
