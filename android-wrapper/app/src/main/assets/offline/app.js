(() => {
  "use strict";

  const HOME_URL = "https://furina-pi.vercel.app/";
  const STORAGE = {
    conversations: "furina-offline:v3:conversations",
    active: "furina-offline:v3:active",
    draft: "furina-offline:v3:draft",
    shared: "furina:shared-state:v1",
  };
  const DEFAULT_PROFILE = {
    name: "Furina",
    systemPrompt: "Kamu adalah Furina, companion pribadi yang ekspresif, cerdas, hangat, dan punya pendapat sendiri. Balas secara alami dalam bahasa pengguna.",
    memoryInstruction: "Gunakan memori berikut hanya jika relevan dan jangan membacakan daftar memori.",
    defaultGreeting: "Halo… akhirnya kamu datang juga. Ceritakan apa saja.",
  };
  const DEFAULT_SHARED = { version: 1, name: "Furina", persona: "", language: "auto", memories: [] };
  const DEFAULT_STATUS = {
    mode: "online",
    source: "lovable",
    activeModelId: "",
    installed: false,
    busy: false,
    supportsImage: false,
    multimodalReady: false,
    canUseOffline: false,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const uid = () => globalThis.crypto && typeof globalThis.crypto.randomUUID === "function"
    ? globalThis.crypto.randomUUID()
    : `furina-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const now = () => Date.now();

  let profile = DEFAULT_PROFILE;
  let shared = DEFAULT_SHARED;
  let nativeStatus = DEFAULT_STATUS;
  let conversations = [];
  let activeId = "";
  let currentScreen = "chat";
  let pendingImage = null;
  let activeRequest = null;
  let responseTimeout = null;
  let toastTimer = null;

  const elements = {};

  function bridge() {
    return globalThis.FurinaNative && typeof globalThis.FurinaNative.getStatus === "function"
      ? globalThis.FurinaNative
      : null;
  }

  function safeParse(value, fallback) {
    try {
      const parsed = JSON.parse(value);
      return parsed == null ? fallback : parsed;
    } catch {
      return fallback;
    }
  }

  function clip(value, max) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    return text.length > max ? `${text.slice(0, max - 1).trimEnd()}…` : text;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
  }

  function normalizeShared(raw) {
    const input = raw && typeof raw === "object" ? raw : {};
    const language = ["auto", "id", "en", "ja"].includes(input.language) ? input.language : "auto";
    const seen = new Set();
    const memories = Array.isArray(input.memories)
      ? input.memories
          .map((memory) => clip(memory, 240))
          .filter((memory) => memory.length >= 3 && !seen.has(memory.toLowerCase()) && seen.add(memory.toLowerCase()))
          .slice(-80)
      : [];
    return {
      version: 1,
      name: clip(input.name || profile.name || "Furina", 40) || "Furina",
      persona: String(input.persona || "").slice(0, 6000),
      language,
      memories,
    };
  }

  function newConversation() {
    const timestamp = now();
    return { id: uid(), title: "Percakapan baru", createdAt: timestamp, updatedAt: timestamp, messages: [] };
  }

  function normalizeConversations(raw) {
    if (!Array.isArray(raw)) return [];
    return raw
      .filter((item) => item && typeof item === "object")
      .map((item) => ({
        id: typeof item.id === "string" && item.id ? item.id : uid(),
        title: typeof item.title === "string" && item.title ? item.title.slice(0, 70) : "Percakapan baru",
        createdAt: Number(item.createdAt) || now(),
        updatedAt: Number(item.updatedAt) || now(),
        messages: Array.isArray(item.messages)
          ? item.messages.slice(-1000).map((message) => ({
              id: typeof message.id === "string" && message.id ? message.id : uid(),
              role: message.role === "assistant" ? "assistant" : "user",
              content: typeof message.content === "string" ? message.content.slice(0, 32000) : "",
              at: Number(message.at) || now(),
              imageDataUrl: typeof message.imageDataUrl === "string" ? message.imageDataUrl : "",
              error: Boolean(message.error),
            }))
          : [],
      }))
      .sort((left, right) => right.updatedAt - left.updatedAt)
      .slice(0, 120);
  }

  function activeConversation() {
    let conversation = conversations.find((item) => item.id === activeId);
    if (!conversation) {
      conversation = newConversation();
      conversations.unshift(conversation);
      activeId = conversation.id;
    }
    return conversation;
  }

  function persistConversations() {
    conversations.sort((left, right) => right.updatedAt - left.updatedAt);
    try {
      localStorage.setItem(STORAGE.conversations, JSON.stringify(conversations));
      localStorage.setItem(STORAGE.active, activeId);
    } catch {
      showToast("Penyimpanan chat penuh. Hapus beberapa chat bergambar atau ekspor data.");
    }
  }

  function persistShared() {
    shared = normalizeShared(shared);
    localStorage.setItem(STORAGE.shared, JSON.stringify(shared));
    const api = bridge();
    if (api && typeof api.saveSharedState === "function") {
      try { api.saveSharedState(JSON.stringify(shared)); } catch {}
    }
  }

  function showToast(message) {
    clearTimeout(toastTimer);
    elements.toast.textContent = String(message || "");
    elements.toast.classList.add("show");
    toastTimer = setTimeout(() => elements.toast.classList.remove("show"), 3200);
  }

  function relativeTime(timestamp) {
    const difference = Math.max(0, now() - Number(timestamp || 0));
    if (difference < 60000) return "baru saja";
    if (difference < 3600000) return `${Math.floor(difference / 60000)} m`;
    if (difference < 86400000) return `${Math.floor(difference / 3600000)} j`;
    if (difference < 604800000) return `${Math.floor(difference / 86400000)} h`;
    return new Date(timestamp).toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
  }

  function titleFromMessage(text, hasImage) {
    return clip(text, 42) || (hasImage ? "Percakapan gambar" : "Percakapan baru");
  }

  function addMessage(conversation, message) {
    conversation.messages.push({
      id: message.id || uid(),
      role: message.role === "assistant" ? "assistant" : "user",
      content: String(message.content || ""),
      at: Number(message.at) || now(),
      imageDataUrl: message.imageDataUrl || "",
      error: Boolean(message.error),
    });
    conversation.updatedAt = now();
    if (conversation.title === "Percakapan baru" && message.role === "user") {
      conversation.title = titleFromMessage(message.content, Boolean(message.imageDataUrl));
    }
    persistConversations();
  }

  function renderMessages() {
    const conversation = activeConversation();
    const hasMessages = conversation.messages.length > 0;
    elements.emptyChat.classList.toggle("hidden", hasMessages);
    elements.messages.classList.toggle("hidden", !hasMessages);
    elements.messages.innerHTML = conversation.messages.map((message) => {
      const image = message.imageDataUrl ? `<img src="${message.imageDataUrl}" alt="Gambar percakapan" />` : "";
      const content = escapeHtml(message.content).replace(/\n/g, "<br>");
      return `<article class="message ${message.role}${message.error ? " error" : ""}" data-message-id="${escapeHtml(message.id)}">${image}${content || (message.role === "assistant" ? "…" : "")}<span class="message-meta">${message.role === "assistant" ? (message.error ? "Gagal" : "AI offline") : new Date(message.at).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}</span></article>`;
    }).join("");
    if (activeRequest && !activeRequest.receivedToken) {
      const node = document.querySelector(`[data-message-id="${activeRequest.assistantMessageId}"]`);
      if (node) node.classList.add("typing");
    }
    requestAnimationFrame(() => { elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight; });
  }

  function renderHistory() {
    const query = elements.historySearch.value.trim().toLowerCase();
    const matches = conversations.filter((conversation) => {
      if (!query) return true;
      return `${conversation.title} ${conversation.messages.map((message) => message.content).join(" ")}`.toLowerCase().includes(query);
    });
    elements.historyList.innerHTML = matches.length ? matches.map((conversation) => {
      const last = conversation.messages[conversation.messages.length - 1];
      return `<article class="history-item" data-history-id="${escapeHtml(conversation.id)}"><div><strong>${escapeHtml(conversation.title)}</strong><p>${escapeHtml((last?.content || "Belum ada pesan").slice(0, 90))}</p><div class="history-tools"><button class="tiny" data-action="open">Buka</button><button class="tiny" data-action="rename">Ubah nama</button><button class="tiny" data-action="delete">Hapus</button></div></div><time>${relativeTime(conversation.updatedAt)}</time></article>`;
    }).join("") : `<article class="card"><p>Tidak ada percakapan yang cocok.</p></article>`;
  }

  function renderDashboard() {
    const allMessages = conversations.flatMap((conversation) => conversation.messages);
    elements.statConversations.textContent = String(conversations.filter((item) => item.messages.length).length);
    elements.statMessages.textContent = String(allMessages.length);
    elements.statMemories.textContent = String(shared.memories.length);
    const offline = nativeStatus.mode === "offline" && nativeStatus.installed;
    elements.dashboardMode.textContent = offline ? "AI Offline aktif" : nativeStatus.installed ? "Model offline siap" : "Belum ada model aktif";
    elements.dashboardModeDetail.textContent = offline ? "Percakapan diproses langsung di perangkat." : "Lovable AI tersedia melalui mode online.";
  }

  function renderModelStatus() {
    const installed = Boolean(nativeStatus.installed);
    const offline = nativeStatus.mode === "offline" && installed;
    elements.modelBadge.textContent = offline ? "AKTIF OFFLINE" : installed ? "TERPASANG" : "BELUM TERPASANG";
    elements.modelTitle.textContent = installed ? (nativeStatus.activeModelId || "Model lokal siap") : "Belum ada model aktif";
    elements.modelDescription.textContent = installed
      ? offline ? "Jawaban diproses langsung di perangkat tanpa jaringan." : "Model tersedia dan dapat diaktifkan kapan saja."
      : "Buka pengelola model untuk mengunduh salah satu model AI offline.";
    elements.activateOffline.disabled = !nativeStatus.canUseOffline || offline;
    elements.deactivateModel.disabled = !installed;
    elements.visionStatus.textContent = nativeStatus.multimodalReady
      ? "Chat gambar offline siap digunakan."
      : nativeStatus.supportsImage
        ? (nativeStatus.imageDisabledReason || "Paket vision belum siap.")
        : "Model aktif hanya mendukung teks. Qwen3.5 diperlukan untuk gambar.";
  }

  function renderSettings() {
    elements.characterName.value = shared.name;
    elements.persona.value = shared.persona;
    elements.language.value = shared.language;
    elements.characterTitle.textContent = shared.name;
    elements.memoryList.innerHTML = shared.memories.length ? shared.memories.slice().reverse().map((memory) => `<article class="history-item memory-item"><div><p>${escapeHtml(memory)}</p></div><button class="tiny" data-memory="${escapeHtml(memory)}">Hapus</button></article>`).join("") : `<div class="notice">Belum ada memori bersama. Aplikasi juga akan menangkap beberapa fakta pribadi secara otomatis dari chat.</div>`;
  }

  function renderStatus() {
    const offline = nativeStatus.mode === "offline" && nativeStatus.installed;
    elements.modeLabel.textContent = offline ? "AI offline" : nativeStatus.installed ? "Model lokal siap" : "Belum ada model offline";
    elements.welcomeCopy.textContent = offline
      ? "Model lokal siap. Persona dan memori bersama diproses langsung di perangkat."
      : "Unduh model lokal untuk mengobrol tanpa jaringan, atau buka Lovable AI untuk mode online.";
    elements.welcomeOffline.disabled = !nativeStatus.canUseOffline;
    renderDashboard();
    renderModelStatus();
    renderSettings();
  }

  function renderAll() {
    renderMessages();
    renderHistory();
    renderStatus();
  }

  function readNativeStatus() {
    const api = bridge();
    if (!api) {
      nativeStatus = DEFAULT_STATUS;
      renderStatus();
      return;
    }
    try { nativeStatus = { ...DEFAULT_STATUS, ...safeParse(api.getStatus(), {}) }; } catch { nativeStatus = DEFAULT_STATUS; }
    renderStatus();
  }

  function readSharedState() {
    const local = normalizeShared(safeParse(localStorage.getItem(STORAGE.shared), DEFAULT_SHARED));
    const api = bridge();
    if (api && typeof api.getSharedState === "function") {
      try { shared = normalizeShared(safeParse(api.getSharedState(), local)); } catch { shared = local; }
    } else {
      shared = local;
    }
    persistShared();
  }

  function switchScreen(screen) {
    currentScreen = screen;
    $$(".screen").forEach((node) => node.classList.toggle("active", node.dataset.screen === screen));
    $$(".nav-btn").forEach((node) => node.classList.toggle("active", node.dataset.target === screen));
    if (screen === "history") renderHistory();
    if (screen === "dashboard") renderDashboard();
    if (screen === "models") readNativeStatus();
    if (screen === "settings") renderSettings();
  }

  function createConversation() {
    if (activeRequest) return showToast("Hentikan jawaban yang sedang dibuat terlebih dahulu.");
    const conversation = newConversation();
    conversations.unshift(conversation);
    activeId = conversation.id;
    pendingImage = null;
    renderImagePreview();
    persistConversations();
    renderAll();
    switchScreen("chat");
    elements.input.focus();
  }

  function openConversation(id) {
    if (activeRequest) return showToast("Tunggu jawaban selesai sebelum berpindah chat.");
    if (!conversations.some((conversation) => conversation.id === id)) return;
    activeId = id;
    persistConversations();
    renderMessages();
    switchScreen("chat");
  }

  function deleteConversation(id) {
    const target = conversations.find((conversation) => conversation.id === id);
    if (!target || !confirm(`Hapus “${target.title}”?`)) return;
    conversations = conversations.filter((conversation) => conversation.id !== id);
    if (!conversations.length) conversations = [newConversation()];
    if (activeId === id) activeId = conversations[0].id;
    persistConversations();
    renderAll();
  }

  function renameConversation(id) {
    const target = conversations.find((conversation) => conversation.id === id);
    if (!target) return;
    const value = prompt("Nama percakapan", target.title);
    if (!value || !value.trim()) return;
    target.title = value.trim().slice(0, 70);
    target.updatedAt = now();
    persistConversations();
    renderHistory();
  }

  function openOnline() {
    if (!navigator.onLine) return showToast("Tidak ada jaringan. Gunakan model offline.");
    try { bridge()?.useOnlineAi(); } catch {}
    localStorage.setItem(STORAGE.draft, elements.input.value || "");
    location.href = HOME_URL;
  }

  function activateOffline() {
    const api = bridge();
    if (!api || typeof api.useOfflineAi !== "function") return showToast("AI offline hanya tersedia di APK Android.");
    try {
      if (!api.useOfflineAi()) {
        showToast("Unduh dan pilih model offline terlebih dahulu.");
        api.openModelManager();
        return false;
      }
      readNativeStatus();
      showToast("AI Offline aktif.");
      switchScreen("chat");
      return true;
    } catch {
      showToast("Mode offline tidak dapat diaktifkan.");
      return false;
    }
  }

  function deactivateModel() {
    const api = bridge();
    if (!api || !confirm("Lepas model aktif tanpa menghapus file model?")) return;
    try { api.deactivateOfflineModel(); readNativeStatus(); showToast("Model dilepas. File model tetap tersimpan."); } catch { showToast("Model tidak dapat dilepas."); }
  }

  function openModelManager() {
    const api = bridge();
    if (api) api.openModelManager();
    else showToast("Pengelola model hanya tersedia di APK Android.");
  }

  function extractMemoryCandidates(text) {
    const cleaned = clip(text, 240);
    if (cleaned.length < 8) return [];
    const durable = [
      /\b(?:aku|saya)\s+(?:suka|menyukai|lebih suka|tidak suka|benci|tinggal|punya|memiliki|biasanya|sedang membangun|sedang mengerjakan|ingin|berencana|menargetkan)\b/i,
      /\b(?:nama(?:ku| saya)|aku bernama|saya bernama|targetku|tujuanku|proyekku|hobiku)\b/i,
    ];
    return durable.some((pattern) => pattern.test(cleaned)) ? [cleaned] : [];
  }

  function mergeMemories(text) {
    const candidates = extractMemoryCandidates(text);
    if (!candidates.length) return;
    shared = normalizeShared({ ...shared, memories: [...shared.memories, ...candidates] });
    persistShared();
  }

  function relevantMemories(query) {
    const terms = new Set(query.toLowerCase().split(/[^a-z0-9À-ÿ]+/i).filter((term) => term.length >= 3));
    return shared.memories.map((memory, index) => ({ memory, index, score: memory.toLowerCase().split(/[^a-z0-9À-ÿ]+/i).reduce((score, term) => score + (terms.has(term) ? 1 : 0), 0) })).sort((left, right) => right.score - left.score || right.index - left.index).slice(0, 20).map((entry) => entry.memory);
  }

  function buildSystemPrompt(query) {
    const memories = relevantMemories(query);
    const parts = [profile.systemPrompt];
    if (shared.persona.trim()) parts.push(`PERSONA TAMBAHAN:\n${shared.persona.trim()}`);
    if (shared.language === "id") parts.push("Selalu balas dalam bahasa Indonesia.");
    if (shared.language === "en") parts.push("Always reply in English.");
    if (shared.language === "ja") parts.push("常に日本語で返答してください。");
    if (memories.length) parts.push(`${profile.memoryInstruction}\n${memories.map((memory) => `- ${memory}`).join("\n")}`);
    return parts.join("\n\n").slice(0, 16000);
  }

  function stopGeneration() {
    if (!activeRequest) return;
    try { bridge()?.cancelGeneration(); } catch {}
    finishRequestWithError("Jawaban dihentikan.");
  }

  function finishRequestWithError(message) {
    if (!activeRequest) return;
    clearTimeout(responseTimeout);
    const conversation = conversations.find((item) => item.id === activeRequest.conversationId);
    const response = conversation?.messages.find((item) => item.id === activeRequest.assistantMessageId);
    if (response) {
      response.content = response.content.trim() ? `${response.content}\n\n${message}` : message;
      response.error = true;
      conversation.updatedAt = now();
    }
    activeRequest = null;
    elements.send.textContent = "➤";
    persistConversations();
    renderMessages();
    readNativeStatus();
  }

  function completeRequest() {
    if (!activeRequest) return;
    clearTimeout(responseTimeout);
    const conversation = conversations.find((item) => item.id === activeRequest.conversationId);
    const response = conversation?.messages.find((item) => item.id === activeRequest.assistantMessageId);
    if (response && !response.content.trim()) response.content = "Model selesai tanpa menghasilkan teks. Coba pesan yang lebih singkat.";
    if (conversation) conversation.updatedAt = now();
    activeRequest = null;
    elements.send.textContent = "➤";
    persistConversations();
    renderMessages();
    readNativeStatus();
  }

  function sendMessage() {
    if (activeRequest) return stopGeneration();
    const text = elements.input.value.trim();
    if (!text && !pendingImage) return;
    readNativeStatus();
    if (nativeStatus.mode !== "offline" || !nativeStatus.installed) {
      if (confirm("Model offline belum aktif. Buka Lovable AI online?")) openOnline();
      return;
    }
    if (pendingImage && !nativeStatus.multimodalReady) return showToast(nativeStatus.imageDisabledReason || "Model aktif belum siap membaca gambar.");
    const api = bridge();
    if (!api || typeof api.generate !== "function") return showToast("Runtime AI Offline tidak tersedia.");

    const conversation = activeConversation();
    const imageDataUrl = pendingImage ? pendingImage.dataUrl : "";
    const userText = text || "Jelaskan gambar ini.";
    addMessage(conversation, { role: "user", content: userText, imageDataUrl });
    mergeMemories(userText);

    const assistantMessageId = uid();
    addMessage(conversation, { id: assistantMessageId, role: "assistant", content: "" });
    const requestId = uid();
    activeRequest = { requestId, conversationId: conversation.id, assistantMessageId, receivedToken: false };
    const messages = conversation.messages.filter((message) => message.id !== assistantMessageId && !message.error).slice(-18).map((message) => ({ role: message.role, content: message.content }));
    const request = JSON.stringify({ requestId, messages, systemPrompt: buildSystemPrompt(userText), maxTokens: imageDataUrl ? 640 : 512, contextSize: imageDataUrl ? 6144 : 4096, temperature: 0.8 });

    elements.input.value = "";
    localStorage.removeItem(STORAGE.draft);
    pendingImage = null;
    renderImagePreview();
    resizeComposer();
    elements.send.textContent = "■";
    renderMessages();
    responseTimeout = setTimeout(() => { try { api.cancelGeneration(); } catch {} finishRequestWithError("Model membutuhkan waktu terlalu lama dan dihentikan."); }, 600000);
    try {
      if (imageDataUrl && typeof api.generateWithImage === "function") api.generateWithImage(request, imageDataUrl);
      else api.generate(request);
    } catch (error) {
      finishRequestWithError(error instanceof Error ? error.message : "Model offline gagal dimulai.");
    }
  }

  function handleToken(detail) {
    if (!activeRequest || !detail || detail.requestId !== activeRequest.requestId) return;
    const conversation = conversations.find((item) => item.id === activeRequest.conversationId);
    const response = conversation?.messages.find((item) => item.id === activeRequest.assistantMessageId);
    if (!response) return;
    response.content += String(detail.token || "");
    response.error = false;
    activeRequest.receivedToken = true;
    conversation.updatedAt = now();
    renderMessages();
  }

  function renderImagePreview() {
    elements.imagePreview.classList.toggle("show", Boolean(pendingImage));
    if (pendingImage) {
      elements.imagePreviewImg.src = pendingImage.dataUrl;
      elements.imagePreviewName.textContent = pendingImage.name || "Gambar";
    } else {
      elements.imagePreviewImg.removeAttribute("src");
      elements.imagePreviewName.textContent = "Gambar";
    }
  }

  function compressImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Gambar tidak dapat dibaca."));
      reader.onload = () => {
        const image = new Image();
        image.onerror = () => reject(new Error("Format gambar tidak didukung."));
        image.onload = () => {
          const maximum = 1280;
          const ratio = Math.min(1, maximum / Math.max(image.naturalWidth, image.naturalHeight));
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round(image.naturalWidth * ratio));
          canvas.height = Math.max(1, Math.round(image.naturalHeight * ratio));
          const context = canvas.getContext("2d", { alpha: false });
          context.fillStyle = "#fff";
          context.fillRect(0, 0, canvas.width, canvas.height);
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        };
        image.src = String(reader.result);
      };
      reader.readAsDataURL(file);
    });
  }

  async function handleImage(file) {
    if (!file) return;
    if (!file.type.startsWith("image/")) return showToast("Pilih file gambar.");
    if (file.size > 12 * 1024 * 1024) return showToast("Gambar maksimal 12 MB.");
    try { pendingImage = { dataUrl: await compressImage(file), name: file.name || "Gambar" }; renderImagePreview(); } catch (error) { showToast(error instanceof Error ? error.message : "Gambar gagal diproses."); }
  }

  function resizeComposer() {
    elements.input.style.height = "auto";
    elements.input.style.height = `${Math.min(125, Math.max(42, elements.input.scrollHeight))}px`;
    localStorage.setItem(STORAGE.draft, elements.input.value || "");
  }

  function addMemory() {
    const memory = clip(elements.memoryInput.value, 240);
    if (memory.length < 3) return;
    shared = normalizeShared({ ...shared, memories: [...shared.memories, memory] });
    elements.memoryInput.value = "";
    persistShared();
    renderSettings();
  }

  function exportData() {
    const backup = { app: "Furina", version: 3, exportedAt: new Date().toISOString(), conversations, activeId, shared };
    const blob = new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" });
    const file = new File([blob], `furina-backup-${new Date().toISOString().slice(0, 10)}.json`, { type: "application/json" });
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ title: "Backup Furina", files: [file] }).catch(() => {});
      return;
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = file.name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  async function importData(file) {
    if (!file) return;
    try {
      const backup = JSON.parse(await file.text());
      if (!backup || backup.app !== "Furina") throw new Error("Format backup tidak dikenali.");
      const imported = normalizeConversations(backup.conversations);
      if (!imported.length) throw new Error("Backup tidak berisi percakapan.");
      if (!confirm("Impor akan mengganti data lokal saat ini. Lanjutkan?")) return;
      conversations = imported;
      activeId = imported.some((item) => item.id === backup.activeId) ? backup.activeId : imported[0].id;
      shared = normalizeShared(backup.shared);
      persistConversations();
      persistShared();
      renderAll();
      switchScreen("chat");
      showToast("Backup berhasil dipulihkan.");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Backup gagal diimpor.");
    } finally {
      elements.importInput.value = "";
    }
  }

  function clearLocalHistory() {
    if (!confirm("Hapus seluruh riwayat percakapan lokal? Model dan memori bersama tidak ikut dihapus.")) return;
    conversations = [newConversation()];
    activeId = conversations[0].id;
    persistConversations();
    renderAll();
    switchScreen("chat");
  }

  function cacheElements() {
    Object.assign(elements, {
      modeLabel: $("#mode-label"), characterTitle: $("#character-title"), messages: $("#messages"), emptyChat: $("#empty-chat"), chatScroll: $("#chat-scroll"), input: $("#message-input"), send: $("#send-message"), imageInput: $("#image-input"), imagePreview: $("#image-preview"), imagePreviewImg: $("#image-preview-img"), imagePreviewName: $("#image-preview-name"), historySearch: $("#history-search"), historyList: $("#history-list"), toast: $("#toast"), welcomeCopy: $("#welcome-copy"), welcomeOffline: $("#welcome-offline"), dashboardMode: $("#dashboard-mode"), dashboardModeDetail: $("#dashboard-mode-detail"), statConversations: $("#stat-conversations"), statMessages: $("#stat-messages"), statMemories: $("#stat-memories"), modelBadge: $("#model-badge"), modelTitle: $("#model-title"), modelDescription: $("#model-description"), activateOffline: $("#activate-offline"), deactivateModel: $("#deactivate-model"), visionStatus: $("#vision-status"), characterName: $("#character-name"), persona: $("#offline-persona"), language: $("#offline-language"), memoryInput: $("#memory-input"), memoryList: $("#memory-list"), importInput: $("#import-input"),
    });
  }

  function bindEvents() {
    $$(".nav-btn").forEach((button) => button.addEventListener("click", () => switchScreen(button.dataset.target)));
    $("#menu-button").addEventListener("click", () => switchScreen("settings"));
    $("#new-chat").addEventListener("click", createConversation);
    $("#history-new").addEventListener("click", createConversation);
    $("#quick-new").addEventListener("click", createConversation);
    ["#open-online", "#welcome-online", "#dashboard-online", "#models-online", "#settings-online"].forEach((selector) => $(selector).addEventListener("click", openOnline));
    ["#welcome-offline", "#dashboard-offline", "#activate-offline"].forEach((selector) => $(selector).addEventListener("click", activateOffline));
    $("#deactivate-model").addEventListener("click", deactivateModel);
    $("#manage-models").addEventListener("click", openModelManager);
    $("#quick-models").addEventListener("click", openModelManager);
    $("#quick-history").addEventListener("click", () => switchScreen("history"));
    $("#quick-export").addEventListener("click", exportData);
    $("#export-data").addEventListener("click", exportData);
    $("#import-data").addEventListener("click", () => elements.importInput.click());
    elements.importInput.addEventListener("change", (event) => importData(event.target.files?.[0]));
    $("#clear-local").addEventListener("click", clearLocalHistory);
    $("#add-memory").addEventListener("click", addMemory);
    elements.memoryInput.addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); addMemory(); } });
    elements.memoryList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-memory]");
      if (!button) return;
      shared.memories = shared.memories.filter((memory) => memory !== button.dataset.memory);
      persistShared();
      renderSettings();
    });

    elements.send.addEventListener("click", sendMessage);
    elements.input.addEventListener("input", resizeComposer);
    elements.input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendMessage(); } });
    $("#pick-image").addEventListener("click", () => elements.imageInput.click());
    elements.imageInput.addEventListener("change", (event) => { handleImage(event.target.files?.[0]); event.target.value = ""; });
    $("#remove-image").addEventListener("click", () => { pendingImage = null; renderImagePreview(); });

    elements.historySearch.addEventListener("input", renderHistory);
    elements.historyList.addEventListener("click", (event) => {
      const row = event.target.closest("[data-history-id]");
      if (!row) return;
      const action = event.target.closest("[data-action]")?.dataset.action || "open";
      if (action === "open") openConversation(row.dataset.historyId);
      else if (action === "rename") renameConversation(row.dataset.historyId);
      else if (action === "delete") deleteConversation(row.dataset.historyId);
    });

    elements.characterName.addEventListener("input", () => { shared.name = elements.characterName.value.slice(0, 40); persistShared(); elements.characterTitle.textContent = shared.name || "Furina"; });
    elements.persona.addEventListener("input", () => { shared.persona = elements.persona.value.slice(0, 6000); persistShared(); });
    elements.language.addEventListener("change", () => { shared.language = elements.language.value; persistShared(); });

    window.addEventListener("furina-native-token", (event) => handleToken(event.detail));
    window.addEventListener("furina-native-complete", (event) => { if (activeRequest && event.detail?.requestId === activeRequest.requestId) completeRequest(); });
    window.addEventListener("furina-native-error", (event) => { if (activeRequest && event.detail?.requestId === activeRequest.requestId) finishRequestWithError(event.detail.error || "Model offline gagal merespons."); });
    window.addEventListener("furina-ai-mode-changed", (event) => { nativeStatus = { ...nativeStatus, ...(event.detail || {}) }; renderStatus(); });
    window.addEventListener("furina-shared-state-changed", (event) => { shared = normalizeShared(event.detail); localStorage.setItem(STORAGE.shared, JSON.stringify(shared)); renderSettings(); });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) { readNativeStatus(); readSharedState(); } });
  }

  async function boot() {
    cacheElements();
    try {
      const response = await fetch("../furina-profile.json");
      if (response.ok) profile = { ...DEFAULT_PROFILE, ...(await response.json()) };
    } catch {}
    readSharedState();
    conversations = normalizeConversations(safeParse(localStorage.getItem(STORAGE.conversations), []));
    if (!conversations.length) conversations = [newConversation()];
    activeId = localStorage.getItem(STORAGE.active) || conversations[0].id;
    if (!conversations.some((conversation) => conversation.id === activeId)) activeId = conversations[0].id;
    bindEvents();
    const draft = localStorage.getItem(STORAGE.draft);
    if (draft) elements.input.value = draft;
    resizeComposer();
    readNativeStatus();
    renderAll();
    setInterval(() => { if (!document.hidden && !activeRequest) readNativeStatus(); }, 2500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
