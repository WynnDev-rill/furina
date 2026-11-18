import assert from "node:assert/strict";
import test from "node:test";
import { sourceServerHandler } from "./source-function.mjs";
import { protectGeminiKey, openGeminiKey } from "../src/lib/gemini-key.ts";
import { fetchAllPages } from "../src/lib/record-pagination.ts";
const path = "../src/lib/nvidia-chat-settings.functions.ts";
function fixture({ authorized = true, age = 21, modelAccess = true } = {}) {
  const keys = [];
  const preferences = {};
  const query = (table) => {
    let rows = table === "furina_nvidia_chat_keys" ? keys : [];
    let columns = "*";
    let mutation;
    const builder = {
      select(value) {
        columns = value;
        return this;
      },
      eq(k, v) {
        rows = rows.filter((r) => r[k] === v);
        return this;
      },
      order() {
        return this;
      },
      upsert(row) {
        if (table === "furina_ai_preferences") Object.assign(preferences, row);
        else keys.push({ ...row, id: "key-a" });
        return Promise.resolve({ error: null });
      },
      update(patch) {
        mutation = () => rows.forEach((r) => Object.assign(r, patch));
        return this;
      },
      delete() {
        mutation = () => rows.forEach((r) => keys.splice(keys.indexOf(r), 1));
        return this;
      },
      range() {
        return Promise.resolve({
          error: null,
          data: rows.map((row) => Object.fromEntries(columns.split(",").map((k) => [k, row[k]]))),
        });
      },
      then(resolve) {
        mutation?.();
        return Promise.resolve({ error: null, count: rows.length }).then(resolve);
      },
    };
    return builder;
  };
  const deps = {
    supabaseAdmin: { from: query },
    requireFurinaIdentity: async () => {
      if (!authorized) throw new Error("unauthorized");
    },
    readAiPreferences: async () => preferences,
    profileContext: async () => ({ birthday: { age } }),
    loadNvidiaChatState: async () => ({ state: { activeModel: "model" }, notice: null }),
    fetchAllPages,
    encryptionSecret: () => "test-secret",
    protectGeminiKey,
    clearNvidiaChatAccess: () => {},
    validateNvidiaChatKey: async () => (modelAccess ? [{ id: "model" }] : []),
  };
  return { keys, preferences, handler: (name) => sourceServerHandler(path, name, deps) };
}
test("main-chat keys are encrypted, owner bound, masked on reads and independent of background activation", async () => {
  const f = fixture();
  const key = "nvapi-synthetic-only-for-tests";
  await f.handler("addNvidiaChatKey")({ data: { userId: "owner", key } });
  assert.notEqual(f.keys[0].encrypted_value, key);
  assert.equal(await openGeminiKey(f.keys[0].encrypted_value, "owner", "test-secret"), key);
  await assert.rejects(openGeminiKey(f.keys[0].encrypted_value, "other", "test-secret"));
  assert.equal(f.preferences.use_nvidia_chat, true);
  assert.equal(f.preferences.use_nvidia, undefined);
  const settings = await f.handler("getNvidiaChatKeySettings")({ data: { userId: "owner" } });
  assert.deepEqual(settings.keys, [{ id: "key-a", suffix: "ests", invalid: false, enabled: true }]);
  assert.doesNotMatch(JSON.stringify(settings), /encrypted_value|synthetic-only|test-secret/);
});
test("authentication is required for every NVIDIA main-chat mutation and read", async () => {
  const f = fixture({ authorized: false });
  for (const name of [
    "setChatProviderSelection",
    "getNvidiaChatKeySettings",
    "addNvidiaChatKey",
    "setNvidiaChatProvider",
    "setNvidiaChatKeyEnabled",
    "removeNvidiaChatKey",
  ])
    await assert.rejects(
      f.handler(name)({
        data: {
          userId: "owner",
          key: "nvapi-test",
          provider: "nvidia",
          enabled: true,
          id: "key-a",
        },
      }),
      /unauthorized/,
    );
  assert.equal(f.keys.length, 0);
  assert.deepEqual(f.preferences, {});
});
test("no model eligibility or age eligibility means no key is stored", async () => {
  for (const options of [{ age: 17 }, { modelAccess: false }]) {
    const f = fixture(options);
    await assert.rejects(
      f.handler("addNvidiaChatKey")({ data: { userId: "owner", key: "nvapi-test" } }),
    );
    assert.equal(f.keys.length, 0);
  }
});
test("disabling and removing a key only affects the verified owner's main-chat key", async () => {
  const f = fixture();
  f.keys.push(
    { id: "key-a", user_id: "owner", enabled: true, invalid: false },
    { id: "key-b", user_id: "other", enabled: true, invalid: false },
  );
  await f.handler("setNvidiaChatKeyEnabled")({
    data: { userId: "owner", id: "key-b", enabled: false },
  });
  assert.equal(f.keys[1].enabled, true);
  await f.handler("setNvidiaChatKeyEnabled")({
    data: { userId: "owner", id: "key-a", enabled: false },
  });
  assert.equal(f.keys[0].enabled, false);
  await assert.rejects(
    f.handler("setNvidiaChatProvider")({ data: { userId: "owner", enabled: true } }),
    /aktifkan/,
  );
  await f.handler("removeNvidiaChatKey")({ data: { userId: "owner", id: "key-b" } });
  assert.equal(f.keys.length, 2);
  await f.handler("removeNvidiaChatKey")({ data: { userId: "owner", id: "key-a" } });
  assert.equal(f.keys.length, 1);
});
test("switching provider changes only main-chat selection and preserves toggles", async () => {
  const f = fixture();
  f.preferences.use_gemini = true;
  f.preferences.use_nvidia = true;
  await f.handler("setChatProviderSelection")({ data: { userId: "owner", provider: "nvidia" } });
  assert.deepEqual(f.preferences, {
    user_id: "owner",
    chat_provider: "nvidia",
    use_gemini: true,
    use_nvidia: true,
  });
});

test("zero enabled valid keys is reported inactive instead of showing a stale active model", async () => {
  const f = fixture();
  f.preferences.use_nvidia_chat = true;
  f.keys.push({ id: "key-a", user_id: "owner", suffix: "test", enabled: false, invalid: false });
  const settings = await f.handler("getNvidiaChatKeySettings")({ data: { userId: "owner" } });
  assert.equal(settings.enabled, false);
  assert.equal(settings.model, null);
  assert.match(settings.notice, /key/i);
});
