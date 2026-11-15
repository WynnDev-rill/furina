import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import {
  ageInstructions,
  birthdayContext,
  localCalendar,
  parseBirthDate,
} from "../src/lib/birth-date.ts";
import { branchPrefix, messageQuote } from "../src/lib/message-quote.ts";

test("age changes at local midnight and rejects invalid or future dates", () => {
  const instant = new Date("2026-11-15T17:00:00Z");
  const today = localCalendar(instant, "Asia/Jakarta");
  assert.deepEqual(birthdayContext("2008-11-16", today), { age: 18, year: 2026, daysUntil: 0 });
  assert.equal(birthdayContext("2008-11-16", localCalendar(instant, "UTC")).age, 17);
  assert.equal(parseBirthDate("2000-02-30", today), null);
  assert.equal(parseBirthDate("2026-11-17", today), null);
  assert.equal(birthdayContext("2008-02-29", new Date("2026-02-28")).daysUntil, 0);
  assert.match(ageInstructions(), /jangan mendorong ketergantungan/i);
  assert.match(ageInstructions(17), /remaja/i);
  assert.match(ageInstructions(18), /tidak membuka akses/i);
  assert.match(ageInstructions(21), /21 tahun.*jawab dengan angka ini/i);
  assert.match(ageInstructions(), /jangan menebak angkanya/i);
});

test("a conversation branch has fresh IDs and only preserves the prefix", () => {
  const original = { id: randomUUID(), role: "assistant", content: "Sumber kutipan" };
  const quoted = {
    id: randomUUID(),
    replyTo: messageQuote.parse({
      id: original.id,
      role: original.role,
      excerpt: original.content,
    }),
  };
  const [copy, linked] = branchPrefix([original, quoted, { id: randomUUID() }], 2, randomUUID);
  assert.notEqual(copy.id, original.id);
  assert.notEqual(linked.id, quoted.id);
  assert.equal(linked.replyTo.id, copy.id);
  assert.equal(quoted.replyTo.id, original.id);
});
