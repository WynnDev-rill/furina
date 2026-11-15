import assert from "node:assert/strict";
import test from "node:test";
import {
  isInvalidGeminiKey,
  openGeminiKey,
  protectGeminiKey,
  useGeminiKeys,
} from "../src/lib/gemini-key.ts";

test("encrypted credentials use a fresh nonce and are bound to the owner", async () => {
  const key = "test-credential";
  const first = await protectGeminiKey(key, "alice", "server secret");
  const second = await protectGeminiKey(key, "alice", "server secret");
  const other = await protectGeminiKey(key, "bob", "server secret");
  assert.notEqual(first.box, second.box);
  assert.equal(first.fingerprint, second.fingerprint);
  assert.notEqual(first.fingerprint, other.fingerprint);
  assert.ok(!first.box.includes(key));
  assert.equal(await openGeminiKey(first.box, "alice", "server secret"), key);
  await assert.rejects(openGeminiKey(first.box, "bob", "server secret"));
  await assert.rejects(openGeminiKey(first.box, "alice", "another secret"));
});

test("rotation skips a credential Gemini confirms is invalid", async () => {
  const revoked = [];
  const attempts = [];
  const response = await useGeminiKeys(
    ["first", "second"],
    async (key) => {
      attempts.push(key);
      return key === "first"
        ? { status: 403, reason: "API_KEY_REVOKED" }
        : { status: 200, reason: "" };
    },
    async ({ status, reason }) => isInvalidGeminiKey(status, reason),
    async (key) => {
      revoked.push(key);
    },
  );
  assert.equal(response.status, 200);
  assert.deepEqual(attempts, ["first", "second"]);
  assert.deepEqual(revoked, ["first"]);
});

test("provider quota and general access errors do not rotate keys", async () => {
  for (const status of [429, 403, 503]) {
    const response = await useGeminiKeys(
      ["first", "second"],
      async (key) => {
        assert.equal(key, "first");
        return { status };
      },
      async (result) => isInvalidGeminiKey(result.status, "Permission denied"),
      async () => assert.fail(),
    );
    assert.equal(response.status, status);
  }
});
