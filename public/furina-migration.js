(() => {
  "use strict";

  const TARGET_CONVERSATIONS = "furina:v3:conversations";
  const TARGET_ACTIVE = "furina:v3:active";
  const MIGRATION_STATUS = "furina:v3:legacy-migration";

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
      status: failed ? "failed" : input.status || (role === "assistant" ? "sent" : "read"),
      imageDataUrl: typeof input.imageDataUrl === "string" ? input.imageDataUrl : undefined,
      failedPayload: failed && role === "user" ? String(input.failedPayload || input.content || "").slice(0, 8_000) : undefined,
    };
  }

  function normalizeConversation(conversation) {
    const input = conversation && typeof conversation === "object" ? conversation : {};
    return {
      id: typeof input.id === "string" && input.id ? input.id.slice(0, 120) : `migrated-${Date.now()}-${Math.random()}`,
      title: typeof input.title === "string" && input.title ? input.title.slice(0, 70) : "Percakapan lama",
      messages: Array.isArray(input.messages) ? input.messages.slice(-1000).map(normalizeMessage) : [],
      updatedAt: Number(input.updatedAt) || Number(input.createdAt) || Date.now(),
      pinned: Boolean(input.pinned),
    };
  }

  function mergeConversations(current, legacy) {
    const merged = new Map();
    [...current, ...legacy].forEach((conversation) => {
      const normalized = normalizeConversation(conversation);
      const previous = merged.get(normalized.id);
      if (!previous || normalized.updatedAt >= previous.updatedAt) merged.set(normalized.id, normalized);
    });
    return [...merged.values()]
      .sort((left, right) => Number(right.pinned) - Number(left.pinned) || right.updatedAt - left.updatedAt)
      .slice(0, 120);
  }

  function migrate() {
    const bridge = globalThis.FurinaMigration;
    if (!bridge?.getLegacyConversations) return;

    let raw = "";
    try {
      raw = bridge.getLegacyConversations();
    } catch {
      return;
    }
    if (!raw) return;

    const legacyPayload = safeParse(raw, null);
    if (!legacyPayload || !Array.isArray(legacyPayload.conversations)) return;

    const current = safeParse(localStorage.getItem(TARGET_CONVERSATIONS), []);
    const legacy = legacyPayload.conversations;
    const merged = mergeConversations(Array.isArray(current) ? current : [], legacy);
    const currentActive = String(localStorage.getItem(TARGET_ACTIVE) || "");
    const legacyActive = String(legacyPayload.activeId || "");
    const selectedActive = merged.some((conversation) => conversation.id === currentActive)
      ? currentActive
      : merged.some((conversation) => conversation.id === legacyActive)
        ? legacyActive
        : merged[0]?.id || "";

    try {
      localStorage.setItem(TARGET_CONVERSATIONS, JSON.stringify(merged));
      if (selectedActive) localStorage.setItem(TARGET_ACTIVE, selectedActive);
      localStorage.setItem(MIGRATION_STATUS, JSON.stringify({
        migratedAt: new Date().toISOString(),
        imported: legacy.length,
        total: merged.length,
      }));
      bridge.consumeLegacyConversations?.();
    } catch {
      // Keep the native staging file intact so migration can be retried safely.
      try {
        localStorage.setItem(MIGRATION_STATUS, JSON.stringify({
          failedAt: new Date().toISOString(),
          reason: "storage-quota",
        }));
      } catch {}
    }
  }

  migrate();
})();
