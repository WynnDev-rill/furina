import assert from "node:assert/strict";
import test from "node:test";
import { mainChatProvider } from "../src/lib/main-chat-provider.ts";
test("NVIDIA selection excludes both Gemini and paid gateway fallback", () => {
  assert.deepEqual(
    mainChatProvider(
      { chat_provider: "nvidia", use_nvidia_chat: true, use_gemini: true, lovable_chat: true },
      true,
      true,
    ),
    { nvidia: true, personalGeminiEnabled: false, lovableChat: false },
  );
});
test("disabled NVIDIA and missing age eligibility do not silently fall through", () => {
  assert.throws(
    () =>
      mainChatProvider(
        { chat_provider: "nvidia", use_nvidia_chat: false, lovable_chat: true },
        true,
        true,
      ),
    /NVIDIA/,
  );
  assert.throws(
    () => mainChatProvider({ chat_provider: "nvidia", use_nvidia_chat: true }, true, false),
    /18/,
  );
});
test("old rows and guests preserve the existing Gemini and Lovable policy", () => {
  assert.deepEqual(mainChatProvider(null, false, false), {
    nvidia: false,
    personalGeminiEnabled: false,
    lovableChat: true,
  });
  assert.deepEqual(mainChatProvider({ use_gemini: true, lovable_chat: false }, true, true), {
    nvidia: false,
    personalGeminiEnabled: true,
    lovableChat: false,
  });
  assert.deepEqual(
    mainChatProvider(
      { chat_provider: "gemini", use_nvidia_chat: true, use_gemini: true },
      true,
      true,
    ),
    { nvidia: false, personalGeminiEnabled: true, lovableChat: true },
  );
});
