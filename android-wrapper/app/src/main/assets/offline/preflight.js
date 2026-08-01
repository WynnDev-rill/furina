(() => {
  "use strict";

  const LEGACY_CONVERSATIONS_KEY = "furina-offline:v3:conversations";
  const LEGACY_ACTIVE_KEY = "furina-offline:v3:active";
  const OLDER_CONVERSATIONS_KEY = "furina-local:conversations:v1";
  const MAX_IMAGE_DATA_LENGTH = 6_000_000;
  const IMAGE_DATA_PATTERN = /^data:image\/(?:png|jpe?g|webp);base64,[a-z0-9+/=\r\n]+$/i;

  globalThis.FurinaLegacyStageReady = false;

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
        createdAt: Number(safeConversation.createdAt) || Date.now(),
        updatedAt: Number(safeConversation.updatedAt) || Date.now(),
        messages: Array.isArray(safeConversation.messages)
          ? safeConversation.messages.slice(-1000).map((message) => {
              const safeMessage = message && typeof message === "object" ? message : {};
              return {
                ...safeMessage,
                id: typeof safeMessage.id === "string" ? safeMessage.id.slice(0, 120) : "",
                role: safeMessage.role === "assistant" ? "assistant" : "user",
                content: typeof safeMessage.content === "string" ? safeMessage.content.slice(0, 32_000) : "",
                at: Number(safeMessage.at) || Date.now(),
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

  function readLegacyConversations() {
    for (const key of [LEGACY_CONVERSATIONS_KEY, OLDER_CONVERSATIONS_KEY]) {
      try {
        const stored = localStorage.getItem(key);
        if (!stored) continue;
        const conversations = sanitizeConversations(JSON.parse(stored));
        if (conversations.length) return conversations;
      } catch {
        // Try the next known legacy key.
      }
    }
    return [];
  }

  function stageLegacyData() {
    try {
      const conversations = readLegacyConversations();
      const activeId = String(localStorage.getItem(LEGACY_ACTIVE_KEY) || "").slice(0, 120);
      const payload = JSON.stringify({
        version: 1,
        stagedAt: new Date().toISOString(),
        activeId,
        conversations,
      });
      if (globalThis.FurinaMigration?.stageLegacyConversations) {
        globalThis.FurinaMigration.stageLegacyConversations(payload);
      }
    } catch {
      // A failed migration must not block the emergency local shell.
    } finally {
      globalThis.FurinaLegacyStageReady = true;
    }
  }

  try {
    const stored = localStorage.getItem(OLDER_CONVERSATIONS_KEY);
    if (stored) localStorage.setItem(OLDER_CONVERSATIONS_KEY, JSON.stringify(sanitizeConversations(JSON.parse(stored))));
  } catch {
    localStorage.removeItem(OLDER_CONVERSATIONS_KEY);
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

  stageLegacyData();

  // Keep the same Japanese voice controls available in the emergency local shell.
  const voiceScript = document.createElement("script");
  voiceScript.src = "voice.js";
  voiceScript.async = false;
  document.head.appendChild(voiceScript);
})();
