import assert from "node:assert/strict";
import test from "node:test";
import {
  continuationRequest,
  continuityPrompt,
  recentThreadsAmbiguous,
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

test("recent topics preserve distinctions between missing, ambiguous, and known context", () => {
  const top = {
    title: "SmartClip",
    last_at: "2026-11-16T03:00:00Z",
    turns: [{ role: "user", text: "Tes ekspor belum selesai." }],
  };
  const simultaneous = { title: "Furina", last_at: "2026-11-16T02:30:00Z", turns: [] };
  const older = { ...simultaneous, last_at: "2026-11-15T23:00:00Z" };
  assert.equal(recentThreadsAmbiguous([top, simultaneous]), true);
  assert.equal(recentThreadsAmbiguous([top, older]), false);
  assert.match(continuityPrompt([top, simultaneous], "resume"), /tanyakan pilihan/);
  assert.match(continuityPrompt([top, older], "resume"), /Tes ekspor belum selesai/);
  assert.match(continuityPrompt([], "resume"), /tanyakan topiknya/);
  assert.equal(continuityPrompt([], "related"), "");
});
