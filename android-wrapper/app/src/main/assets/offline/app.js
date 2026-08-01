(() => {
  "use strict";

  const HOME_URL = "https://furina-pi.vercel.app/";
  const STORAGE = {
    conversations: "furina-local:conversations:v1",
    active: "furina-local:active-conversation",
    settings: "furina-local:settings:v1",
    draft: "furina-local:draft",
  };
  const DEFAULT_PERSONA =
    "Kamu adalah Furina, teman percakapan yang ekspresif, cerdas, hangat, dan tetap memiliki pendapat sendiri. " +
    "Balas dalam bahasa yang digunakan pengguna. Jangan terdengar seperti asisten formal. Jangan mengaku sebagai manusia. " +
    "Untuk percakapan emosional, pahami perasaan pengguna tanpa selalu memberi nasihat atau selalu menyetujui mereka. " +
    "Jaga jawaban tetap alami dan sesuai panjang pesan pengguna.";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const uid = () => {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
    return `furina-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  };
  const now = () => Date.now();

  function safeParse(value, fallback) {
    try {
      const parsed = JSON.parse(value);
      return parsed == null ? fallback : parsed;
    } catch {
      return fallback;
    }
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function newConversation() {
    const timestamp = now();
    return {
      id: uid(),
      title: "Percakapan baru",
      createdAt: timestamp,
      updatedAt: timestamp,
      messages: [],
    };
  }

  function normalizeConversations(raw) {
    if (!Array.isArray(raw)) return [];
    return raw
      .filter((item) => item && typeof item === "object")
      .map((item) => ({
        id: typeof item.id === "string" && item.id ? item.id : uid(),
        title: typeof item.title === "string" && item.title ? item.title : "Percakapan baru",
        createdAt: Number(item.createdAt) || now(),
        updatedAt: Number(item.updatedAt) || now(),
        messages: Array.isArray(item.messages)
          ? item.messages.filter(Boolean).map((message) => ({
              id: typeof message.id === "string" && message.id ? message.id : uid(),
              role: message.role === "assistant" ? "assistant" : "user",
              content: typeof message.content === "string" ? message.content : "",
              at: Number(message.at) || now(),
              imageDataUrl: typeof message.imageDataUrl === "string" ? message.imageDataUrl : "",
              error: Boolean(message.error),
              source: typeof message.source === "string" ? message.source : "offline",
            }))
          : [],
      }))
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 120);
  }

  let conversations = normalizeConversations(safeParse(localStorage.getItem(STORAGE.conversations), []));
  if (!conversations.length) conversations = [newConversation()];
  let activeId = localStorage.getItem(STORAGE.active) || conversations[0].id;
  if (!conversations.some((conversation) => conversation.id === activeId)) activeId = conversations[0].id;

  let settings = {
    name: "Furina",
    persona: "",
    language: "auto",
    ...safeParse(localStorage.getItem(STORAGE.settings), {}),
  };
  let nativeStatus = {
    mode: "online",
    source: "lovable",
    activeModelId: "",
    installed: false,
    busy: false,
    supportsImage: false,
    multimodalReady: false,
    canUseOffline: false,
  };
  let currentScreen = "chat";
  let pendingImage = null;
  let activeRequest = null;
  let responseTimeout = null;
  let toastTimer = null;

  const elements = {
    modeLabel: $("#mode-label"),
    messages: $("#messages"),
    emptyChat: $("#empty-chat"),
    chatScroll: $("#chat-scroll"),
    input: $("#message-input"),
    send: $("#send-message"),
    imageInput: $("#image-input"),
    imagePreview: $("#image-preview"),
    imagePreviewImg: $("#image-preview-img"),
    imagePreviewName: $("#image-preview-name"),
    historySearch: $("#history-search"),
    historyList: $("#history-list"),
    toast: $("#toast"),
    characterName: $("#character-name"),
    persona: $("#offline-persona"),
    language: $("#offline-language"),
  };

  function bridge() {
    return globalThis.FurinaNative && typeof globalThis.FurinaNative.getStatus === "function"
      ? globalThis.FurinaNative
      : null;
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

  function persist() {
    conversations.sort((a, b) => b.updatedAt - a.updatedAt);
    try {
      localStorage.setItem(STORAGE.conversations, JSON.stringify(conversations));
      localStorage.setItem(STORAGE.active, activeId);
      localStorage.setItem(STORAGE.settings, JSON.stringify(settings));
    } catch (error) {
      showToast("Penyimpanan lokal hampir penuh. Hapus beberapa chat gambar atau ekspor data terlebih dahulu.");
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
    if (difference < 60_000) return "Baru saja";
    if (difference < 3_600_000) return `${Math.floor(difference / 60_000)} mnt`;
    if (difference < 86_400_000) return `${Math.floor(difference / 3_600_000)} jam`;
    if (difference < 604_800_000) return `${Math.floor(difference / 86_400_000)} hari`;
    return new Date(timestamp).toLocaleDateString("id-ID", { day: "2-digit", month: "short" });
  }

  function titleFromMessage(text, hasImage) {
    const cleaned = String(text || "").replace(/\s+/g, " ").trim();
    if (cleaned) return cleaned.slice(0, 44);
    return hasImage ? "Percakapan gambar" : "Percakapan baru";
  }

  function addMessage(conversation, message) {
    conversation.messages.push({
      id: message.id || uid(),
      role: message.role === "assistant" ? "assistant" : "user",
      content: String(message.content || ""),
      at: Number(message.at) || now(),
      imageDataUrl: message.imageDataUrl || "",
      error: Boolean(message.error),
      source: message.source || "offline",
    });
    conversation.updatedAt = now();
    if (conversation.title === "Percakapan baru" && message.role === "user") {
      conversation.title = titleFromMessage(message.content, Boolean(message.imageDataUrl));
    }
    persist();
  }

  function renderMessages() {
    const conversation = activeConversation();
    const hasMessages = conversation.messages.length > 0;
    elements.emptyChat.classList.toggle("hidden", hasMessages);
    elements.messages.classList.toggle("hidden", !hasMessages);

    elements.messages.innerHTML = conversation.messages.map((message) => {
      const image = message.imageDataUrl
        ? `<img src="${message.imageDataUrl}" alt="Gambar percakapan" />`
        : "";
      const content = escapeHtml(message.content).replace(/\n/g, "<br>");
      const className = `message ${message.role}${message.error ? " error" : ""}`;
      const metadata = message.role === "assistant"
        ? `<span class="message-meta">${message.error ? "Gagal" : "Tersimpan lokal"}</span>`
        : "";
      return `<article class="${className}" data-message-id="${escapeHtml(message.id)}">${image}${content || (message.role === "assistant" ? "…" : "")}${metadata}</article>`;
    }).join("");

    if (activeRequest) {
      const node = $(`[data-message-id="${CSS.escape(activeRequest.assistantMessageId)}"]`);
      if (node && !activeRequest.receivedToken) node.classList.add("typing");
    }
    requestAnimationFrame(() => {
      elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;
    });
  }

  function renderHistory() {
    const query = elements.historySearch.value.trim().toLowerCase();
    const matches = conversations.filter((conversation) => {
      if (!query) return true;
      const haystack = `${conversation.title} ${conversation.messages.map((message) => message.content).join(" ")}`.toLowerCase();
      return haystack.includes(query);
    });

    if (!matches.length) {
      elements.historyList.innerHTML = `<article class="card"><p>Tidak ada percakapan yang cocok.</p></article>`;
      return;
    }

    elements.historyList.innerHTML = matches.map((conversation) => {
      const last = conversation.messages[conversation.messages.length - 1];
      const preview = last ? (last.content || (last.imageDataUrl ? "Gambar" : "Belum ada pesan")) : "Belum ada pesan";
      return `<article class="history-item" data-history-id="${escapeHtml(conversation.id)}">
        <div>
          <strong>${escapeHtml(conversation.title)}</strong>
          <p>${escapeHtml(preview.slice(0, 90))}</p>
          <div class="history-tools">
            <button class="tiny" data-action="open">Buka</button>
            <button class="tiny" data-action="rename">Ubah nama</button>
            <button class="tiny" data-action="delete">Hapus</button>
          </div>
        </div>
        <time>${relativeTime(conversation.updatedAt)}</time>
      </article>`;
    }).join("");
  }

  function renderDashboard() {
    const allMessages = conversations.flatMap((conversation) => conversation.messages);
    $("#stat-conversations").textContent = String(conversations.filter((item) => item.messages.length).length);
    $("#stat-messages").textContent = String(allMessages.length);
    $("#stat-images").textContent = String(allMessages.filter((message) => message.imageDataUrl).length);

    const offline = nativeStatus.mode === "offline" && nativeStatus.installed;
    $("#dashboard-mode").textContent = offline ? "AI Offline siap" : "Lovable AI";
    $("#dashboard-mode-detail").textContent = offline
      ? "Percakapan diproses langsung di perangkat."
      : navigator.onLine
        ? "Personalisasi online tetap tersedia."
        : "Jaringan tidak tersedia; aktifkan model lokal untuk chat.";
    $("#dashboard-offline").disabled = !nativeStatus.canUseOffline;
  }

  function renderModelStatus() {
    const installed = Boolean(nativeStatus.installed);
    const offline = nativeStatus.mode === "offline" && installed;
    $("#model-badge").textContent = offline ? "AKTIF OFFLINE" : installed ? "TERPASANG" : "BELUM AKTIF";
    $("#model-title").textContent = installed ? "Model lokal siap" : "Belum ada model aktif";
    $("#model-description").textContent = installed
      ? offline
        ? "Jawaban chat lokal diproses tanpa mengirim percakapan ke server."
        : "Model tersedia di perangkat tetapi mode online sedang dipilih."
      : "Buka pengelola model untuk mengunduh dan memilih model AI offline.";
    $("#activate-offline").disabled = !nativeStatus.canUseOffline || offline;
    $("#deactivate-model").disabled = !installed;
    $("#vision-status").textContent = nativeStatus.multimodalReady
      ? "Chat gambar offline siap digunakan."
      : nativeStatus.supportsImage
        ? (nativeStatus.imageDisabledReason || "Paket vision belum siap.")
        : "Model aktif hanya mendukung teks. Qwen3.5 diperlukan untuk chat gambar offline.";
  }

  function renderSettings() {
    elements.characterName.value = settings.name || "Furina";
    elements.persona.value = settings.persona || "";
    elements.language.value = settings.language || "auto";
  }

  function renderStatus() {
    const offline = nativeStatus.mode === "offline" && nativeStatus.installed;
    elements.modeLabel.textContent = offline
      ? "AI lokal siap"
      : navigator.onLine
        ? "Lovable AI tersedia"
        : "Offline • pilih model lokal";
    $("#welcome-copy").textContent = offline
      ? "Model lokal siap. Pesan dan gambar yang didukung akan diproses langsung di perangkat ini."
      : "Aktifkan model lokal dari menu Model untuk mengobrol sepenuhnya offline, atau gunakan Lovable AI untuk pengalaman online yang sudah dipersonalisasi.";
    $("#welcome-offline").disabled = !nativeStatus.canUseOffline;
    renderDashboard();
    renderModelStatus();
  }

  function renderAll() {
    renderMessages();
    renderHistory();
    renderDashboard();
    renderModelStatus();
    renderSettings();
    renderStatus();
  }

  function readNativeStatus() {
    const api = bridge();
    if (!api) {
      nativeStatus = { ...nativeStatus, mode: "online", installed: false, canUseOffline: false, busy: false };
      renderStatus();
      return nativeStatus;
    }
    try {
      nativeStatus = { ...nativeStatus, ...safeParse(api.getStatus(), {}) };
    } catch {
      nativeStatus = { ...nativeStatus, busy: false };
    }
    renderStatus();
    return nativeStatus;
  }

  function switchScreen(screen) {
    currentScreen = screen;
    $$(".screen").forEach((node) => node.classList.toggle("active", node.dataset.screen === screen));
    $$(".nav-btn").forEach((node) => node.classList.toggle("active", node.dataset.target === screen));
    if (screen === "history") renderHistory();
    if (screen === "dashboard") renderDashboard();
    if (screen === "models") {
      readNativeStatus();
      renderModelStatus();
    }
  }

  function createConversation() {
    if (activeRequest) {
      showToast("Hentikan jawaban yang sedang dibuat terlebih dahulu.");
      return;
    }
    const conversation = newConversation();
    conversations.unshift(conversation);
    activeId = conversation.id;
    pendingImage = null;
    renderImagePreview();
    persist();
    renderAll();
    switchScreen("chat");
    elements.input.focus();
  }

  function openConversation(id) {
    if (activeRequest) {
      showToast("Tunggu jawaban selesai sebelum berpindah percakapan.");
      return;
    }
    if (!conversations.some((conversation) => conversation.id === id)) return;
    activeId = id;
    persist();
    renderMessages();
    switchScreen("chat");
  }

  function deleteConversation(id) {
    const target = conversations.find((conversation) => conversation.id === id);
    if (!target || !confirm(`Hapus “${target.title}”?`)) return;
    conversations = conversations.filter((conversation) => conversation.id !== id);
    if (!conversations.length) conversations = [newConversation()];
    if (activeId === id) activeId = conversations[0].id;
    persist();
    renderAll();
  }

  function renameConversation(id) {
    const target = conversations.find((conversation) => conversation.id === id);
    if (!target) return;
    const value = prompt("Nama percakapan", target.title);
    if (!value || !value.trim()) return;
    target.title = value.trim().slice(0, 60);
    target.updatedAt = now();
    persist();
    renderHistory();
  }

  function openOnline() {
    if (!navigator.onLine) {
      showToast("Tidak ada jaringan. Gunakan model offline atau coba lagi saat tersambung.");
      return;
    }
    try {
      const api = bridge();
      if (api && typeof api.useOnlineAi === "function") api.useOnlineAi();
    } catch {}
    localStorage.setItem(STORAGE.draft, elements.input.value || "");
    location.href = HOME_URL;
  }

  function activateOffline() {
    const api = bridge();
    if (!api || typeof api.useOfflineAi !== "function") {
      showToast("AI Offline hanya tersedia di APK Android Furina.");
      return false;
    }
    try {
      const success = Boolean(api.useOfflineAi());
      if (!success) {
        showToast("Unduh dan pilih model offline terlebih dahulu.");
        if (typeof api.openModelManager === "function") api.openModelManager();
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
    if (!api || typeof api.deactivateOfflineModel !== "function") return;
    if (!confirm("Lepas model aktif tanpa menghapus file model?")) return;
    try {
      api.deactivateOfflineModel();
      readNativeStatus();
      showToast("Model dilepas. File model tetap tersimpan.");
    } catch {
      showToast("Model tidak dapat dilepas.");
    }
  }

  function openModelManager() {
    const api = bridge();
    if (api && typeof api.openModelManager === "function") api.openModelManager();
    else showToast("Pengelola model hanya tersedia di APK Android.");
  }

  function buildSystemPrompt() {
    let promptText = settings.persona.trim() || DEFAULT_PERSONA;
    const name = (settings.name || "Furina").trim().slice(0, 40);
    if (name && name !== "Furina") promptText += `\nNama karakter yang digunakan dalam percakapan ini adalah ${name}.`;
    if (settings.language === "id") promptText += "\nSelalu balas dalam bahasa Indonesia.";
    if (settings.language === "en") promptText += "\nAlways reply in English.";
    if (settings.language === "ja") promptText += "\n常に日本語で返答してください。";
    return promptText.slice(0, 6000);
  }

  function stopGeneration() {
    if (!activeRequest) return;
    try {
      const api = bridge();
      if (api && typeof api.cancelGeneration === "function") api.cancelGeneration();
    } catch {}
    finishRequestWithError("Jawaban dihentikan.");
  }

  function finishRequestWithError(message) {
    if (!activeRequest) return;
    clearTimeout(responseTimeout);
    const conversation = conversations.find((item) => item.id === activeRequest.conversationId);
    const response = conversation && conversation.messages.find((item) => item.id === activeRequest.assistantMessageId);
    if (response) {
      if (!response.content.trim()) response.content = message;
      else response.content += `\n\n${message}`;
      response.error = true;
      conversation.updatedAt = now();
    }
    activeRequest = null;
    elements.send.textContent = "➤";
    elements.send.disabled = false;
    persist();
    renderMessages();
    readNativeStatus();
  }

  function completeRequest() {
    if (!activeRequest) return;
    clearTimeout(responseTimeout);
    const conversation = conversations.find((item) => item.id === activeRequest.conversationId);
    const response = conversation && conversation.messages.find((item) => item.id === activeRequest.assistantMessageId);
    if (response && !response.content.trim()) response.content = "Maaf, model selesai tanpa menghasilkan teks. Coba ulangi dengan kalimat yang lebih singkat.";
    if (conversation) conversation.updatedAt = now();
    activeRequest = null;
    elements.send.textContent = "➤";
    elements.send.disabled = false;
    persist();
    renderMessages();
    readNativeStatus();
  }

  function sendMessage() {
    if (activeRequest) {
      stopGeneration();
      return;
    }

    const text = elements.input.value.trim();
    if (!text && !pendingImage) return;
    readNativeStatus();

    if (nativeStatus.mode !== "offline" || !nativeStatus.installed) {
      if (confirm("Mode Lovable AI menggunakan aplikasi online yang sudah dipersonalisasi. Buka sekarang?")) openOnline();
      return;
    }
    if (pendingImage && !nativeStatus.multimodalReady) {
      showToast(nativeStatus.imageDisabledReason || "Model aktif belum siap membaca gambar.");
      return;
    }

    const api = bridge();
    if (!api || typeof api.generate !== "function") {
      showToast("Runtime AI Offline tidak tersedia.");
      return;
    }

    const conversation = activeConversation();
    const imageDataUrl = pendingImage ? pendingImage.dataUrl : "";
    addMessage(conversation, {
      role: "user",
      content: text || "Jelaskan gambar ini.",
      imageDataUrl,
      source: "offline",
    });

    const assistantMessageId = uid();
    addMessage(conversation, {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      source: "offline",
    });

    const requestId = uid();
    activeRequest = {
      requestId,
      conversationId: conversation.id,
      assistantMessageId,
      receivedToken: false,
    };

    const messages = conversation.messages
      .filter((message) => message.id !== assistantMessageId && !message.error)
      .slice(-20)
      .map((message) => ({ role: message.role, content: message.content }));
    const request = JSON.stringify({
      requestId,
      messages,
      systemPrompt: buildSystemPrompt(),
      maxTokens: 512,
      contextSize: pendingImage ? 6144 : 4096,
      temperature: 0.78,
    });

    elements.input.value = "";
    localStorage.removeItem(STORAGE.draft);
    pendingImage = null;
    renderImagePreview();
    resizeComposer();
    elements.send.textContent = "■";
    renderMessages();

    responseTimeout = setTimeout(() => {
      try { api.cancelGeneration(); } catch {}
      finishRequestWithError("Model membutuhkan waktu terlalu lama dan dihentikan.");
    }, 180_000);

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
    const response = conversation && conversation.messages.find((item) => item.id === activeRequest.assistantMessageId);
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
          const width = Math.max(1, Math.round(image.naturalWidth * ratio));
          const height = Math.max(1, Math.round(image.naturalHeight * ratio));
          const canvas = document.createElement("canvas");
          canvas.width = width;
          canvas.height = height;
          const context = canvas.getContext("2d", { alpha: false });
          context.fillStyle = "#ffffff";
          context.fillRect(0, 0, width, height);
          context.drawImage(image, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        };
        image.src = String(reader.result);
      };
      reader.readAsDataURL(file);
    });
  }

  async function handleImage(file) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      showToast("Pilih file gambar.");
      return;
    }
    if (file.size > 12 * 1024 * 1024) {
      showToast("Gambar terlalu besar. Maksimal 12 MB.");
      return;
    }
    try {
      const dataUrl = await compressImage(file);
      pendingImage = { dataUrl, name: file.name || "Gambar" };
      renderImagePreview();
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Gambar gagal diproses.");
    }
  }

  function resizeComposer() {
    elements.input.style.height = "auto";
    elements.input.style.height = `${Math.min(125, Math.max(42, elements.input.scrollHeight))}px`;
    localStorage.setItem(STORAGE.draft, elements.input.value || "");
  }

  function exportData() {
    const backup = {
      app: "Furina",
      version: 1,
      exportedAt: new Date().toISOString(),
      conversations,
      activeId,
      settings,
    };
    const blob = new Blob([JSON.stringify(backup, null, 2)], { type: "application/json" });
    const fileName = `furina-backup-${new Date().toISOString().slice(0, 10)}.json`;
    const file = new File([blob], fileName, { type: "application/json" });

    if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
      navigator.share({ title: "Backup Furina", files: [file] }).catch(() => {});
      return;
    }

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    showToast("Backup disiapkan. Periksa folder unduhan atau menu berbagi.");
  }

  async function importData(file) {
    if (!file) return;
    try {
      const backup = JSON.parse(await file.text());
      if (!backup || backup.app !== "Furina" || Number(backup.version) !== 1) throw new Error("Format backup tidak dikenali.");
      const imported = normalizeConversations(backup.conversations);
      if (!imported.length) throw new Error("Backup tidak berisi percakapan.");
      if (!confirm("Impor akan mengganti riwayat lokal saat ini. Lanjutkan?")) return;
      conversations = imported;
      activeId = imported.some((item) => item.id === backup.activeId) ? backup.activeId : imported[0].id;
      settings = { ...settings, ...(backup.settings || {}) };
      persist();
      renderAll();
      switchScreen("chat");
      showToast("Backup berhasil dipulihkan.");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Backup gagal diimpor.");
    } finally {
      $("#import-input").value = "";
    }
  }

  function clearLocalHistory() {
    if (!confirm("Hapus seluruh riwayat percakapan lokal? Model offline dan akun Lovable tidak ikut dihapus.")) return;
    conversations = [newConversation()];
    activeId = conversations[0].id;
    persist();
    renderAll();
    switchScreen("chat");
    showToast("Riwayat lokal dihapus.");
  }

  function bindEvents() {
    $$(".nav-btn").forEach((button) => button.addEventListener("click", () => switchScreen(button.dataset.target)));
    $("#new-chat").addEventListener("click", createConversation);
    $("#history-new").addEventListener("click", createConversation);
    $("#quick-new").addEventListener("click", createConversation);
    $("#open-online").addEventListener("click", openOnline);
    $("#welcome-online").addEventListener("click", openOnline);
    $("#dashboard-online").addEventListener("click", openOnline);
    $("#settings-online").addEventListener("click", openOnline);
    $("#welcome-offline").addEventListener("click", activateOffline);
    $("#dashboard-offline").addEventListener("click", activateOffline);
    $("#activate-offline").addEventListener("click", activateOffline);
    $("#deactivate-model").addEventListener("click", deactivateModel);
    $("#manage-models").addEventListener("click", openModelManager);
    $("#quick-models").addEventListener("click", openModelManager);
    $("#quick-history").addEventListener("click", () => switchScreen("history"));
    $("#quick-export").addEventListener("click", exportData);
    $("#export-data").addEventListener("click", exportData);
    $("#import-data").addEventListener("click", () => $("#import-input").click());
    $("#import-input").addEventListener("change", (event) => importData(event.target.files && event.target.files[0]));
    $("#clear-local").addEventListener("click", clearLocalHistory);

    elements.send.addEventListener("click", sendMessage);
    elements.input.addEventListener("input", resizeComposer);
    elements.input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
    $("#pick-image").addEventListener("click", () => elements.imageInput.click());
    elements.imageInput.addEventListener("change", (event) => {
      handleImage(event.target.files && event.target.files[0]);
      event.target.value = "";
    });
    $("#remove-image").addEventListener("click", () => {
      pendingImage = null;
      renderImagePreview();
    });

    elements.historySearch.addEventListener("input", renderHistory);
    elements.historyList.addEventListener("click", (event) => {
      const action = event.target.closest("[data-action]");
      const row = event.target.closest("[data-history-id]");
      if (!row) return;
      const id = row.dataset.historyId;
      if (!action || action.dataset.action === "open") openConversation(id);
      else if (action.dataset.action === "rename") renameConversation(id);
      else if (action.dataset.action === "delete") deleteConversation(id);
    });

    elements.characterName.addEventListener("input", () => {
      settings.name = elements.characterName.value.slice(0, 40);
      persist();
    });
    elements.persona.addEventListener("input", () => {
      settings.persona = elements.persona.value.slice(0, 6000);
      persist();
    });
    elements.language.addEventListener("change", () => {
      settings.language = elements.language.value;
      persist();
    });

    window.addEventListener("furina-native-token", (event) => handleToken(event.detail));
    window.addEventListener("furina-native-complete", (event) => {
      if (activeRequest && event.detail && event.detail.requestId === activeRequest.requestId) completeRequest();
    });
    window.addEventListener("furina-native-error", (event) => {
      if (activeRequest && event.detail && event.detail.requestId === activeRequest.requestId) {
        finishRequestWithError(event.detail.error || "Model offline gagal merespons.");
      }
    });
    window.addEventListener("furina-ai-mode-changed", (event) => {
      nativeStatus = { ...nativeStatus, ...(event.detail || {}) };
      renderStatus();
    });
    window.addEventListener("online", renderStatus);
    window.addEventListener("offline", renderStatus);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) readNativeStatus();
    });
  }

  function boot() {
    bindEvents();
    const draft = localStorage.getItem(STORAGE.draft);
    if (draft) elements.input.value = draft;
    resizeComposer();
    readNativeStatus();
    renderAll();
    setInterval(() => {
      if (!document.hidden && !activeRequest) readNativeStatus();
    }, 2500);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
