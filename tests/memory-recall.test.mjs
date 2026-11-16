import assert from "node:assert/strict";
import test from "node:test";
import { recallContext, recallQuery } from "../src/lib/memory-recall.ts";

test("finds Indonesian topic words, date cues and direct overview requests", () => {
  assert.deepEqual(recallQuery("Kamu masih ingat proyek SmartClip yang kita bahas kemarin?"), {
    terms: ["proyek", "smartclip"],
    overview: false,
    yesterday: true,
  });
  assert.deepEqual(recallQuery("Apa yang kamu ingat tentang aku?"), {
    terms: [],
    overview: true,
    yesterday: false,
  });
  assert.deepEqual(recallQuery("Apa yang kita bahas kemarin?"), {
    terms: [],
    overview: false,
    yesterday: true,
  });
});

test("reserves room for saved notes and conversation excerpts and deduplicates mixed search results", () => {
  const row = (id, source, content) => ({
    id,
    source,
    content,
    occurred_at: "2026-11-10T02:00:00Z",
  });
  const saved = row("a", "saved", "SmartClip memproses video di perangkat.");
  const oldText = row("b", "user", "Langkah berikutnya menguji pemotongan video.");
  const filler = Array.from({ length: 12 }, (_, i) => row(String(i), "learned", "Catatan " + i));
  const result = recallContext([saved, ...filler], [{ ...saved }, oldText]);
  assert.equal(result.split(saved.content).length, 2);
  assert.match(result, /Memori tersimpan/);
  assert.match(result, /Pesan lama pengguna/);
  assert.match(result, /Langkah berikutnya/);
  assert.doesNotMatch(result, /Catatan 5/);
});
