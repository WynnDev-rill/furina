import assert from "node:assert/strict";
import test from "node:test";
import {
  continuationRequest,
  continuityPrompt,
  recentThreadsAmbiguous,
  shouldConsiderRecent,
} from "../src/lib/chat-continuity.ts";

test("a vague follow-up resumes across threads only when the active chat lacks a topic", () => {
  assert.deepEqual(continuationRequest("Lanjut yang tadi ya", ["Halo!"]), {
    mode: "resume",
    terms: [],
  });
  assert.deepEqual(continuationRequest("Apa yang terakhir kita bahas?", ["Terima kasih ya"]), {
    mode: "resume",
    terms: [],
  });
  assert.deepEqual(continuationRequest("Where were we?", []), { mode: "resume", terms: [] });
  assert.deepEqual(continuationRequest("Gimana langkah berikutnya?", []), {
    mode: "resume",
    terms: [],
  });
  assert.deepEqual(
    continuationRequest("Sampai mana kita tadi?", ["Aku sedang membahas ekspor video"]),
    { mode: "active", terms: [] },
  );
  assert.deepEqual(continuationRequest("Lanjut proyek SmartClip", []), {
    mode: "related",
    terms: ["smartclip"],
  });
  assert.deepEqual(continuationRequest("Apa itu Embedding?", []), {
    mode: "related",
    terms: ["embedding"],
  });
});

test("fresh candidates can support natural questions without a shared keyword or trigger phrase", () => {
  const top = {
    id: "thread-a",
    title: "SmartClip",
    last_at: "2026-11-16T03:00:00Z",
    turns: [{ role: "user", text: "Tes ekspor belum selesai." }],
  };
  const another = {
    id: "thread-b",
    title: "Cara kerja",
    last_at: "2026-11-16T02:30:00Z",
    turns: [{ role: "user", text: "Aku lebih nyaman menguji satu fitur setiap sore." }],
  };
  assert.equal(shouldConsiderRecent("Perlu kubagi jadi dua tahap?"), true);
  assert.equal(shouldConsiderRecent("Selamat pagi Furina!"), false);
  assert.equal(shouldConsiderRecent("👍"), false);
  assert.equal(recentThreadsAmbiguous([top, another]), true);
  const context = continuityPrompt([], [top, another], "related");
  assert.match(context, /Tes ekspor belum selesai/);
  assert.match(context, /satu fitur setiap sore/);
  assert.match(context, /rujukan tersirat/);
  assert.match(context, /abaikan kandidat/);
  assert.match(context, /dua tafsiran yang sama kuat/);
  assert.doesNotMatch(context, /thread-a/);
  const mixed = continuityPrompt([top], [top, another], "related");
  assert.equal(mixed.split("Tes ekspor belum selesai").length, 2);
  assert.match(mixed, /"matchedTopic":true/);
  assert.match(mixed, /"matchedTopic":false/);
  assert.match(continuityPrompt([], [], "resume"), /tanyakan secara singkat/);
  assert.equal(continuityPrompt([], [], "related"), "");
});
