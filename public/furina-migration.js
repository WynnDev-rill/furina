(() => {
  "use strict";

  const TARGET_CONVERSATIONS = "furina:v4:conversations";
  const TARGET_ACTIVE = "furina:v4:active";
  const LEGACY_CONVERSATIONS = ["furina:v3:conversations", "furina-offline:v3:conversations", "furina-local:conversations:v1"];
  const LEGACY_ACTIVE = ["furina:v3:active", "furina-offline:v3:active"];

  function safeParse(value, fallback) {
    try {
      const parsed = JSON.parse(value);
      return parsed == null ? fallback : parsed;
    } catch {
      return fallback;
    }
  }

  function normalizeMessage(message) {
    const input = message && typeof message === "object" ? message : {};
    const role = input.role === "assistant" ? "assistant" : "user";
    const failed = input.status === "failed" || Boolean(input.error);
    return {
      id: typeof input.id === "string" && input.id ? input.id.slice(0, 120) : `migrated-${Date.now()}-${Math.random()}`,
      role,
      content: typeof input.content === "string" ? input.content.slice(0, 32_000) : "",
      at: Number(input.at) || Date.now(),
      status: failed ? "failed" : role === "assistant" ? "sent" : "read",
      imageDataUrl: typeof input.imageDataUrl === "string" ? input.imageDataUrl : undefined,
      failedPayload: failed && role === "user" ? String(input.failedPayload || input.content || "").slice(0, 8_000) : undefined,
    };
  }

  function normalizeConversations(value) {
    if (!Array.isArray(value)) return [];
    return value.slice(0, 120).map((conversation) => {
      const input = conversation && typeof conversation === "object" ? conversation : {};
      return {
        id: typeof input.id === "string" && input.id ? input.id.slice(0, 120) : `conversation-${Date.now()}-${Math.random()}`,
        title: typeof input.title === "string" && input.title ? input.title.slice(0, 70) : "Percakapan baru",
        updatedAt: Number(input.updatedAt) || Date.now(),
        pinned: Boolean(input.pinned),
        messages: Array.isArray(input.messages) ? input.messages.slice(-1000).map(normalizeMessage) : [],
      };
    });
  }

  if (localStorage.getItem(TARGET_CONVERSATIONS)) return;

  for (const key of LEGACY_CONVERSATIONS) {
    const conversations = normalizeConversations(safeParse(localStorage.getItem(key), []));
    if (!conversations.length) continue;
    localStorage.setItem(TARGET_CONVERSATIONS, JSON.stringify(conversations));
    for (const activeKey of LEGACY_ACTIVE) {
      const activeId = localStorage.getItem(activeKey);
      if (activeId && conversations.some((conversation) => conversation.id === activeId)) {
        localStorage.setItem(TARGET_ACTIVE, activeId);
        break;
      }
    }
    break;
  }
})();
