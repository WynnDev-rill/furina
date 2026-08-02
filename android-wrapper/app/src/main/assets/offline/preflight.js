(() => {
  "use strict";

  const TARGET_CONVERSATIONS = "furina-offline:v4:conversations";
  const TARGET_ACTIVE = "furina-offline:v4:active";
  const LEGACY_KEYS = [
    "furina-offline:v3:conversations",
    "furina-local:conversations:v1",
    "furina:v3:conversations",
  ];
  const LEGACY_ACTIVE_KEYS = [
    "furina-offline:v3:active",
    "furina:v3:active",
  ];
  const MAX_IMAGE_DATA_LENGTH = 6_000_000;
  const IMAGE_DATA_PATTERN = /^data:image\/(?:png|jpe?g|webp);base64,[a-z0-9+/=\r\n]+$/i;

  function safeImageDataUrl(value) {
    if (typeof value !== "string" || value.length > MAX_IMAGE_DATA_LENGTH) return "";
    return IMAGE_DATA_PATTERN.test(value) ? value.replace(/[\r\n]/g, "") : "";
  }

  function sanitizeConversations(value) {
    if (!Array.isArray(value)) return [];
    return value.slice(0, 120).map((conversation) => {
      const safeConversation = conversation && typeof conversation === "object" ? conversation : {};
      return {
        id: typeof safeConversation.id === "string" && safeConversation.id ? safeConversation.id.slice(0, 120) : `migrated-${Date.now()}-${Math.random()}`,
        title: typeof safeConversation.title === "string" ? safeConversation.title.slice(0, 120) : "Percakapan baru",
        createdAt: Number(safeConversation.createdAt) || Date.now(),
        updatedAt: Number(safeConversation.updatedAt) || Date.now(),
        pinned: Boolean(safeConversation.pinned),
        messages: Array.isArray(safeConversation.messages)
          ? safeConversation.messages.slice(-1000).map((message) => {
              const safeMessage = message && typeof message === "object" ? message : {};
              const role = safeMessage.role === "assistant" ? "assistant" : "user";
              const failed = safeMessage.status === "failed" || Boolean(safeMessage.error);
              return {
                id: typeof safeMessage.id === "string" && safeMessage.id ? safeMessage.id.slice(0, 120) : `message-${Date.now()}-${Math.random()}`,
                role,
                content: typeof safeMessage.content === "string" ? safeMessage.content.slice(0, 32_000) : "",
                at: Number(safeMessage.at) || Date.now(),
                status: failed ? "failed" : role === "assistant" ? "sent" : "read",
                imageDataUrl: safeImageDataUrl(safeMessage.imageDataUrl),
                failedPayload: failed && role === "user" ? String(safeMessage.failedPayload || safeMessage.content || "").slice(0, 8_000) : undefined,
              };
            })
          : [],
      };
    });
  }

  function migrateLocalHistory() {
    if (localStorage.getItem(TARGET_CONVERSATIONS)) return;
    for (const key of LEGACY_KEYS) {
      try {
        const stored = localStorage.getItem(key);
        if (!stored) continue;
        const conversations = sanitizeConversations(JSON.parse(stored));
        if (!conversations.length) continue;
        localStorage.setItem(TARGET_CONVERSATIONS, JSON.stringify(conversations));
        for (const activeKey of LEGACY_ACTIVE_KEYS) {
          const activeId = localStorage.getItem(activeKey);
          if (activeId && conversations.some((conversation) => conversation.id === activeId)) {
            localStorage.setItem(TARGET_ACTIVE, activeId);
            break;
          }
        }
        break;
      } catch {
        // Continue with the next known local format.
      }
    }
  }

  function sanitizeBackup(value) {
    if (!value || typeof value !== "object" || value.app !== "Furina") return value;
    return {
      ...value,
      version: 4,
      activeId: typeof value.activeId === "string" ? value.activeId.slice(0, 120) : "",
      conversations: sanitizeConversations(value.conversations),
    };
  }

  if (typeof Blob !== "undefined" && typeof Blob.prototype.text === "function") {
    const originalText = Blob.prototype.text;
    Blob.prototype.text = async function sanitizedText() {
      const raw = await originalText.call(this);
      try {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.app === "Furina") return JSON.stringify(sanitizeBackup(parsed));
      } catch {
        // The app will show its normal invalid-backup message.
      }
      return raw;
    };
  }

  Object.defineProperty(globalThis, "FurinaBackupSanitizer", {
    value: Object.freeze({ safeImageDataUrl, sanitizeConversations, sanitizeBackup }),
    configurable: false,
    enumerable: false,
    writable: false,
  });

  migrateLocalHistory();
})();
