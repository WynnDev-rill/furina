(() => {
  "use strict";

  const CONVERSATIONS_KEY = "furina-local:conversations:v1";
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
        ...safeConversation,
        id: typeof safeConversation.id === "string" ? safeConversation.id.slice(0, 120) : "",
        title: typeof safeConversation.title === "string" ? safeConversation.title.slice(0, 120) : "Percakapan baru",
        messages: Array.isArray(safeConversation.messages)
          ? safeConversation.messages.slice(0, 2000).map((message) => {
              const safeMessage = message && typeof message === "object" ? message : {};
              return {
                ...safeMessage,
                id: typeof safeMessage.id === "string" ? safeMessage.id.slice(0, 120) : "",
                role: safeMessage.role === "assistant" ? "assistant" : "user",
                content: typeof safeMessage.content === "string" ? safeMessage.content.slice(0, 32_000) : "",
                imageDataUrl: safeImageDataUrl(safeMessage.imageDataUrl),
                source: safeMessage.source === "lovable" ? "lovable" : "offline",
              };
            })
          : [],
      };
    });
  }

  function sanitizeBackup(value) {
    if (!value || typeof value !== "object") return value;
    if (Array.isArray(value)) return sanitizeConversations(value);
    if (value.app !== "Furina" || Number(value.version) !== 1) return value;

    const settings = value.settings && typeof value.settings === "object" ? value.settings : {};
    return {
      ...value,
      activeId: typeof value.activeId === "string" ? value.activeId.slice(0, 120) : "",
      conversations: sanitizeConversations(value.conversations),
      settings: {
        name: typeof settings.name === "string" ? settings.name.slice(0, 40) : "Furina",
        persona: typeof settings.persona === "string" ? settings.persona.slice(0, 6000) : "",
        language: ["auto", "id", "en", "ja"].includes(settings.language) ? settings.language : "auto",
      },
    };
  }

  try {
    const stored = localStorage.getItem(CONVERSATIONS_KEY);
    if (stored) localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(sanitizeConversations(JSON.parse(stored))));
  } catch {
    localStorage.removeItem(CONVERSATIONS_KEY);
  }

  if (typeof Blob !== "undefined" && typeof Blob.prototype.text === "function") {
    const originalText = Blob.prototype.text;
    Blob.prototype.text = async function sanitizedText() {
      const raw = await originalText.call(this);
      try {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.app === "Furina" && Number(parsed.version) === 1) {
          return JSON.stringify(sanitizeBackup(parsed));
        }
      } catch {
        // The application will display its normal invalid-backup error.
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
})();
