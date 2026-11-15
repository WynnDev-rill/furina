import assert from "node:assert/strict";
import test from "node:test";
import { historyAfter } from "../src/lib/memory-policy.ts";

test("forget cuts off old and unversioned transcript context while allowing fresh turns", () => {
  const cutoff = "2026-11-15T13:00:00.000Z";
  const at = Date.parse(cutoff);
  const messages = [{ text: "legacy" }, { at: at - 1 }, { at }, { at: at + 1 }];
  assert.deepEqual(historyAfter(messages, cutoff), [{ at: at + 1 }]);
  assert.equal(historyAfter(messages, null), messages);
});
