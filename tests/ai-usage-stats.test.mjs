import assert from "node:assert/strict";
import test from "node:test";
import {
  formatResetCountdown,
  getUsageSharePercent,
  nextJakartaMonthReset,
} from "../src/lib/ai-usage-stats.ts";

test("usage shares stay in the 1–100 range when activity is recorded", () => {
  assert.equal(getUsageSharePercent(30, 100), 30);
  assert.equal(getUsageSharePercent(1, 1000), 1);
  assert.equal(getUsageSharePercent(120, 100), 100);
});

test("usage share is unavailable when no activity is recorded", () => {
  assert.equal(getUsageSharePercent(0, 0), null);
});

test("monthly reset is midnight Jakarta time on the next month", () => {
  const reset = nextJakartaMonthReset(new Date("2026-11-16T00:05:00.000Z"));
  assert.equal(reset.toISOString(), "2026-11-30T17:00:00.000Z");
});

test("reset countdown reports remaining time without exceeding the reset", () => {
  assert.equal(
    formatResetCountdown("2026-11-16T01:05:00.000Z", Date.parse("2026-11-16T00:05:00.000Z")),
    "1 jam 0 menit",
  );
  assert.equal(
    formatResetCountdown("2026-11-16T00:04:00.000Z", Date.parse("2026-11-16T00:05:00.000Z")),
    "0 menit",
  );
});