import assert from "node:assert/strict";
import test from "node:test";
import {
  isInvalidGeminiKey,
  normalizeGeminiKey,
  openGeminiKey,
  protectGeminiKey,
  useGeminiKeys,
} from "../src/lib/gemini-key.ts";

test("the save path accepts Google authorization and standard keys without altering the token", () => {
  const authorizationKey = "AQ.synthetic-gemini-auth-key-test";
  const standardKey = "AIza_synthetic-standard-key-test";
  assert.equal(normalizeGeminiKey(" \u200b" + authorizationKey + "\n"), authorizationKey);
  assert.equal(normalizeGeminiKey(standardKey), standardKey);
  for (const malformed of [
    "AQ.short",
    "Bearer " + authorizationKey,
    authorizationKey + "\r\nkey",
    "x".repeat(257),
  ]) {
    assert.equal(normalizeGeminiKey(malformed), null);
  }
});

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

test("Gemini key rotation tries the next key after a 429 quota response", async () => {
  const attempts = [];
  const response = await useGeminiKeys(
    ["first", "second"],
    async (key) => {
      attempts.push(key);
      return key === "first" ? { status: 429 } : { status: 200 };
    },
    async () => false,
    async () => assert.fail(),
  );
  assert.deepEqual(attempts, ["first", "second"]);
  assert.equal(response.status, 200);
});

test("Gemini rotation returns the last quota response after all keys are limited", async () => {
  const attempts = [];
  const response = await useGeminiKeys(
    ["first", "second"],
    async (key) => {
      attempts.push(key);
      return { status: 429, key };
    },
    async () => false,
    async () => assert.fail(),
  );
  assert.deepEqual(attempts, ["first", "second"]);
  assert.equal(response.status, 429);
  assert.equal(response.key, "second");
});

test("general access and server errors do not rotate Gemini keys", async () => {
  for (const status of [403, 503]) {
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

test("an unreadable saved credential does not block remaining keys or become revoked", async () => {
  const attempts = [];
  const response = await useGeminiKeys(
    ["unreadable", "working"],
    async (key) => {
      attempts.push(key);
      return key === "unreadable" ? null : { status: 200 };
    },
    async () => false,
    async () => assert.fail("local unreadability does not mean Google revoked the key"),
  );
  assert.equal(response.status, 200);
  assert.deepEqual(attempts, ["unreadable", "working"]);
});
