import assert from "node:assert/strict";
import test from "node:test";
import { recoverMessageStatuses } from "../src/lib/message-status.ts";

test("an answered pending turn recovers as read after a transient status-write failure", () => {
  const messages = [{ role: "user", status: "sending" }, { role: "assistant" }];
  assert.equal(recoverMessageStatuses(messages)[0].status, "read");
  assert.equal(messages[0].status, "sending");
});

test("an interrupted user turn without an answer becomes retryable", () => {
  for (const status of ["sending", "sent"]) {
    assert.equal(recoverMessageStatuses([{ role: "user", status }])[0].status, "failed");
  }
});

test("another user turn does not count as an answer and settled statuses stay unchanged", () => {
  const messages = [
    { role: "user", status: "sending" },
    { role: "user", status: "read" },
    { role: "assistant", status: "sent" },
    { role: "user", status: "failed" },
  ];
  assert.deepEqual(
    recoverMessageStatuses(messages).map((m) => m.status),
    ["failed", "read", "sent", "failed"],
  );
});
