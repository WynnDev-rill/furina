import assert from "node:assert/strict";
import test from "node:test";
import { sourceFunction } from "./source-function.mjs";

const route = "../src/routes/index.tsx";
function chatFixture({ aiFails = false, writeFails = false, assistantFails = false } = {}) {
  const account = "00000000-0000-4000-8000-000000000001";
  let conversations = [{ id: "thread", title: "Conversation", messages: [], updatedAt: 1 }];
  const stored = new Map();
  const errors = [];
  let aiCalls = 0;
  let storedAtAiStart = [];
  const noop = () => {};
  const deps = {
    activeConvo: conversations[0],
    sendLock: { current: false },
    authReady: true,
    userId: account,
    syncing: false,
    clearingChat: false,
    syncFailed: false,
    editingMessage: null,
    pendingImage: null,
    authUser: { id: account },
    replyTo: undefined,
    name: "Furina",
    persona: "",
    language: "id",
    conversations,
    ratings: {},
    feedbackExamples: () => [],
    setConversations: (update) => {
      conversations = update(conversations);
    },
    setSending: noop,
    setInput: noop,
    setReplyTo: noop,
    setEditingMessage: noop,
    setPendingImage: noop,
    accountRef: { current: account },
    upsertSingleConversation: async () => {},
    upsertSingleMessage: async (_uid, _thread, message) => {
      if (writeFails || (assistantFails && message.role === "assistant"))
        throw new Error("offline");
      stored.set(message.id, { ...message });
    },
    chat: async () => {
      aiCalls++;
      storedAtAiStart = [...stored.values()];
      if (aiFails) throw new Error("AI unavailable");
      return { reply: "Hello", bubbles: ["Hello"] };
    },
    toast: { error: (message) => errors.push(message), warning: (message) => errors.push(message) },
    localStorage: { setItem: noop },
    lastActivityKey: "activity",
    proactiveFiredRef: { current: false },
    preGenerateAudio: noop,
    maybeSummarize: noop,
    userMsgCountRef: { current: 0 },
    compactMemFn: async () => {},
    updateStyleFn: async () => {},
  };
  return {
    send: sourceFunction(route, "sendMessage", deps),
    stored,
    errors,
    messages: () => conversations[0].messages,
    aiCalls: () => aiCalls,
    storedAtAiStart: () => storedAtAiStart,
  };
}

test("stores the user turn before requesting AI", async () => {
  const f = chatFixture();
  await f.send("Hello");
  assert.ok(
    f.storedAtAiStart().some((m) => m.role === "user"),
    "user message must survive a reload while AI is running",
  );
  assert.equal(f.stored.size, 2);
  assert.equal(f.messages().at(-1).role, "assistant");
});

test("AI failure preserves a failed user turn in cloud storage", async () => {
  const f = chatFixture({ aiFails: true });
  await f.send("Hello");
  assert.equal(f.stored.size, 1);
  assert.equal([...f.stored.values()][0].status, "failed");
});

test("a failed initial write prevents an untracked AI request", async () => {
  const f = chatFixture({ writeFails: true });
  await f.send("Hello");
  assert.equal(f.aiCalls(), 0);
  assert.equal(f.messages()[0].status, "failed");
});

test("assistant save failure warns without marking the answered user turn failed", async () => {
  const f = chatFixture({ assistantFails: true });
  await f.send("Hello");
  assert.equal(f.messages()[0].status, "read");
  assert.equal(f.messages().at(-1).content, "Hello");
  assert.ok(f.errors.some((message) => /tersimpan|tersinkron/i.test(message)));
});

test("message writes propagate database errors to their caller", async () => {
  const save = sourceFunction(route, "upsertSingleMessage", {
    supabase: { from: () => ({ upsert: async () => ({ error: new Error("offline") }) }) },
    console: { warn: () => {} },
  });
  await assert.rejects(save("owner", "thread", { id: "message", at: 1 }), /offline/);
});
