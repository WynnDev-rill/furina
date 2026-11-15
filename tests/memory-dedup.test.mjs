import assert from "node:assert/strict";
import test from "node:test";
import { combineMemoryText, memoryTextKey } from "../src/lib/memory-dedup.ts";

test("consolidation removes exact matches and keeps unique details intact", () => {
  assert.equal(memoryTextKey("  Earl   GREY "), "earl grey");
  const input = [
    "Suka teh. Earl Grey biasanya diminum tanpa gula.",
    "Suka teh. Minum teh pada jam 16.30.",
    "Alergi susu.",
  ];
  assert.equal(
    combineMemoryText(input),
    "Suka teh.\nEarl Grey biasanya diminum tanpa gula.\nMinum teh pada jam 16.30.\nAlergi susu.",
  );
});

test("consolidation refuses to truncate details to fit", () => {
  assert.equal(combineMemoryText(["a".repeat(450), "b".repeat(450)]), null);
});
