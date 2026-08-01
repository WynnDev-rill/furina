(() => {
  const MODE_KEY = "furina:aiMode";
  const RESPONSE_META_KEY = "furina:responseSources";
  const FALLBACK_STATUS = {
    mode: localStorage.getItem(MODE_KEY) || "online",
    source: "lovable",
    activeModelId: "",
    installed: false,
    busy: false,
    supportsImage: false,
    multimodalReady: false,
    canUseOffline: false,
  };

  let status = { ...FALLBACK_STATUS };
  const pending = new Map();

  function native() {
    return window.FurinaNative && typeof window.FurinaNative.getStatus === "function"
      ? window.FurinaNative
      : null;
  }

  function readStatus() {
    try {
      const bridge = native();
      if (bridge) status = { ...FALLBACK_STATUS, ...JSON.parse(bridge.getStatus()) };
      else status = { ...status, mode: localStorage.getItem(MODE_KEY) || "online", source: "lovable" };
    } catch {
      status = { ...FALLBACK_STATUS };
    }
    localStorage.setItem(MODE_KEY, status.mode || "online");
    window.dispatchEvent(new CustomEvent("furina-ai-status", { detail: { ...status } }));
    refreshModeCards();
    return { ...status };
  }

  function useOnline() {
    const bridge = native();
    if (bridge?.useOnlineAi) bridge.useOnlineAi();
    localStorage.setItem(MODE_KEY, "online");
    status = { ...status, mode: "online", source: "lovable" };
    readStatus();
    return true;
  }

  function useOffline() {
    const bridge = native();
    if (!bridge?.useOfflineAi) {
      alert("Mode offline hanya tersedia di APK Android Furina.");
      return false;
    }
    const ok = bridge.useOfflineAi();
    if (!ok) {
      alert("Unduh dan aktifkan model offline terlebih dahulu.");
      return false;
    }
    localStorage.setItem(MODE_KEY, "offline");
    readStatus();
    return true;
  }

  function deactivateOffline() {
    const bridge = native();
    if (bridge?.deactivateOfflineModel) bridge.deactivateOfflineModel();
    localStorage.setItem(MODE_KEY, "online");
    status = { ...status, mode: "online", source: "lovable", activeModelId: "", installed: false };
    readStatus();
    return true;
  }

  function generateOffline({ messages, imageDataUrl, conversationId }) {
    return new Promise((resolve, reject) => {
      const bridge = native();
      if (!bridge) return reject(new Error("Runtime offline hanya tersedia di APK Android."));
      const current = readStatus();
      if (current.mode !== "offline") return reject(new Error("Mode offline belum diaktifkan."));
      if (!current.installed) return reject(new Error("Model offline belum terpasang."));

      const requestId = crypto.randomUUID();
      pending.set(requestId, { text: "", resolve, reject, startedAt: Date.now() });
      const payload = JSON.stringify({
        requestId,
        conversationId: conversationId || "local",
        messages: Array.isArray(messages) ? messages.slice(-20) : [],
        maxTokens: 768,
        temperature: 0.75,
      });
      try {
        if (imageDataUrl) bridge.generateWithImage(payload, imageDataUrl);
        else bridge.generate(payload);
      } catch (error) {
        pending.delete(requestId);
        reject(error instanceof Error ? error : new Error("Model offline gagal dimulai."));
      }
    });
  }

  function rememberSource(messageId, source, modelId) {
    try {
      const map = JSON.parse(localStorage.getItem(RESPONSE_META_KEY) || "{}");
      map[messageId] = { source, modelId: modelId || null, at: Date.now() };
      const entries = Object.entries(map).sort((a, b) => b[1].at - a[1].at).slice(0, 1000);
      localStorage.setItem(RESPONSE_META_KEY, JSON.stringify(Object.fromEntries(entries)));
    } catch {}
  }

  window.addEventListener("furina-native-token", (event) => {
    const item = pending.get(event.detail?.requestId);
    if (!item) return;
    item.text += event.detail?.token || "";
    window.dispatchEvent(new CustomEvent("furina-offline-token", {
      detail: { requestId: event.detail.requestId, token: event.detail?.token || "" },
    }));
  });

  window.addEventListener("furina-native-complete", (event) => {
    const requestId = event.detail?.requestId;
    const item = pending.get(requestId);
    if (!item) return;
    pending.delete(requestId);
    rememberSource(requestId, "offline", status.activeModelId);
    item.resolve({
      requestId,
      reply: item.text.trim(),
      source: "offline",
      modelId: status.activeModelId,
      elapsedMs: Date.now() - item.startedAt,
    });
  });

  window.addEventListener("furina-native-error", (event) => {
    const requestId = event.detail?.requestId;
    const item = pending.get(requestId);
    if (!item) return;
    pending.delete(requestId);
    item.reject(new Error(event.detail?.error || "Model offline gagal merespons."));
  });

  window.addEventListener("furina-ai-mode-changed", (event) => {
    status = { ...status, ...(event.detail || {}) };
    localStorage.setItem(MODE_KEY, status.mode || "online");
    refreshModeCards();
  });

  function exportLocalData() {
    const keys = [
      "furina:conversations", "furina:activeConvoId", "furina:name", "furina:persona",
      "furina:lang", "furina:ttsSpeed", "furina:ttsProvider", "furina:vvSpeaker",
      "furina:vvTranslate", "furina:theme", "furina:preGenAudio", MODE_KEY,
      RESPONSE_META_KEY,
    ];
    const data = { version: 1, exportedAt: new Date().toISOString(), values: {} };
    keys.forEach((key) => {
      const value = localStorage.getItem(key);
      if (value !== null) data.values[key] = value;
    });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `furina-backup-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function importLocalData(file) {
    return file.text().then((text) => {
      const backup = JSON.parse(text);
      if (!backup || backup.version !== 1 || typeof backup.values !== "object") {
        throw new Error("Format cadangan Furina tidak valid.");
      }
      Object.entries(backup.values).forEach(([key, value]) => {
        if (key.startsWith("furina:") && typeof value === "string") localStorage.setItem(key, value);
      });
      location.reload();
    });
  }

  function modeLabel() {
    if (status.mode === "offline" && status.installed) return "AI lokal siap";
    return "Lovable AI";
  }

  function refreshModeCards() {
    document.querySelectorAll("[data-furina-mode-label]").forEach((node) => {
      node.textContent = modeLabel();
    });
    document.querySelectorAll("[data-furina-mode=online]").forEach((node) => {
      node.classList.toggle("active", status.mode !== "offline");
    });
    document.querySelectorAll("[data-furina-mode=offline]").forEach((node) => {
      node.classList.toggle("active", status.mode === "offline");
      node.toggleAttribute("disabled", !status.canUseOffline);
    });
  }

  function enhanceDashboard() {
    const body = document.querySelector("#furina-stage2-overlay .furina-stage2-panel-body");
    if (!body || body.querySelector(".furina-stage3-mode-card")) return;
    const card = document.createElement("section");
    card.className = "furina-stage2-section furina-stage3-mode-card";
    card.innerHTML = `
      <h2>Sumber AI</h2>
      <p class="furina-stage3-current">Saat ini: <strong data-furina-mode-label>${modeLabel()}</strong></p>
      <div class="furina-stage3-mode-actions">
        <button data-furina-mode="online">Lovable AI</button>
        <button data-furina-mode="offline">AI Offline</button>
        <button data-furina-deactivate>Lepas model aktif</button>
      </div>
      <p class="furina-stage3-help">Pilihan ini disimpan di perangkat. Nama model tidak ditampilkan di layar percakapan.</p>`;
    body.prepend(card);
    card.querySelector('[data-furina-mode="online"]')?.addEventListener("click", useOnline);
    card.querySelector('[data-furina-mode="offline"]')?.addEventListener("click", useOffline);
    card.querySelector("[data-furina-deactivate]")?.addEventListener("click", () => {
      if (confirm("Lepas model offline aktif tanpa menghapus file model?")) deactivateOffline();
    });
    refreshModeCards();
  }

  function addBackupActions() {
    const settings = [...document.querySelectorAll("[role=dialog], section")].find((el) =>
      el.textContent?.includes("Pengaturan") && el.textContent?.includes("Akun")
    );
    if (!settings || settings.querySelector(".furina-stage3-backup")) return;
    const box = document.createElement("div");
    box.className = "furina-stage3-backup";
    box.innerHTML = `
      <strong>Cadangan lokal</strong>
      <span>Simpan riwayat dan pengaturan sebelum memasang ulang aplikasi.</span>
      <div><button data-export>Ekspor data</button><button data-import>Impor data</button></div>
      <input data-import-file type="file" accept="application/json" hidden />`;
    settings.appendChild(box);
    box.querySelector("[data-export]")?.addEventListener("click", exportLocalData);
    const input = box.querySelector("[data-import-file]");
    box.querySelector("[data-import]")?.addEventListener("click", () => input.click());
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      try { await importLocalData(file); } catch (error) { alert(error.message || "Impor gagal."); }
    });
  }

  const observer = new MutationObserver(() => {
    enhanceDashboard();
    addBackupActions();
  });

  window.FurinaAI = {
    getStatus: readStatus,
    useOnline,
    useOffline,
    deactivateOffline,
    generateOffline,
    rememberSource,
    exportLocalData,
    importLocalData,
  };

  function boot() {
    readStatus();
    observer.observe(document.body, { subtree: true, childList: true });
    window.dispatchEvent(new CustomEvent("furina-ai-ready", { detail: { ...status } }));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
