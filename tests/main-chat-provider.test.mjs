import assert from "node:assert/strict";
import test from "node:test";
import { mainChatProvider } from "../src/lib/main-chat-provider.ts";

test("retired NVIDIA preferences cannot route main chat or enable Lovable automatically", () => {
  assert.deepEqual(
    mainChatProvider(
      { chat_provider: "nvidia", use_nvidia_chat: true, use_gemini: true, lovable_chat: false },
      true,
      true,
    ),
    {
      personalGeminiEnabled: true,
      lovableChat: false,
    },
  );
  assert.deepEqual(
    mainChatProvider(
      { chat_provider: "nvidia", use_nvidia_chat: true, lovable_chat: false },
      true,
      true,
    ),
    {
      personalGeminiEnabled: false,
      lovableChat: false,
    },
  );
});
test("main chat preserves account, age and enabled-provider policy", () => {
  assert.deepEqual(mainChatProvider(null, false, false), {
    personalGeminiEnabled: false,
    lovableChat: true,
  });
  for (const [signedIn, eligible] of [
    [false, true],
    [true, false],
  ]) {
    assert.deepEqual(
      mainChatProvider({ use_gemini: true, lovable_chat: false }, signedIn, eligible),
      {
        personalGeminiEnabled: false,
        lovableChat: false,
      },
    );
  }
});
