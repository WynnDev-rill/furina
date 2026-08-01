(() => {
  const STORAGE_KEY = "furina:stage2:view";
  const labels = {
    chat: "Chat",
    history: "Riwayat",
    dashboard: "Dashboard",
    model: "Model",
    settings: "Pengaturan",
  };

  const state = { view: localStorage.getItem(STORAGE_KEY) || "chat" };

  function byAria(label) {
    return [...document.querySelectorAll("button")].find((el) => el.getAttribute("aria-label") === label);
  }

  function clickExisting(label) {
    const target = byAria(label) || [...document.querySelectorAll("button")].find((el) => el.textContent?.trim() === label);
    target?.click();
  }

  function currentConversations() {
    try {
      return JSON.parse(localStorage.getItem("furina:conversations") || "[]");
    } catch {
      return [];
    }
  }

  function activeModel() {
    try {
      return localStorage.getItem("furina_model_manager:active_model") || "Belum dipilih";
    } catch {
      return "Belum dipilih";
    }
  }

  function closeOverlay() {
    document.getElementById("furina-stage2-overlay")?.remove();
    state.view = "chat";
    localStorage.setItem(STORAGE_KEY, "chat");
    updateNav();
  }

  function createShell(title, body) {
    document.getElementById("furina-stage2-overlay")?.remove();
    const overlay = document.createElement("section");
    overlay.id = "furina-stage2-overlay";
    overlay.className = "furina-stage2-overlay";
    overlay.innerHTML = `
      <div class="furina-stage2-panel">
        <header class="furina-stage2-panel-header">
          <div>
            <p class="furina-stage2-eyebrow">Furina</p>
            <h1>${title}</h1>
          </div>
          <button class="furina-stage2-close" aria-label="Tutup">×</button>
        </header>
        <div class="furina-stage2-panel-body">${body}</div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector(".furina-stage2-close")?.addEventListener("click", closeOverlay);
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeOverlay();
    });
    return overlay;
  }

  function historyView() {
    const convos = currentConversations().sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    const groups = convos.reduce((acc, convo) => {
      const age = Date.now() - (convo.updatedAt || 0);
      const key = age < 86400000 ? "Hari ini" : age < 604800000 ? "7 hari terakhir" : "Lebih lama";
      (acc[key] ||= []).push(convo);
      return acc;
    }, {});
    const rows = Object.entries(groups).map(([group, items]) => `
      <section class="furina-stage2-history-group">
        <h2>${group}</h2>
        ${items.map((item) => {
          const preview = item.messages?.at(-1)?.content || "Belum ada pesan";
          const time = new Date(item.updatedAt || Date.now()).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
          return `<button class="furina-stage2-history-item" data-conversation="${item.id}">
            <span class="furina-stage2-history-icon">✦</span>
            <span class="furina-stage2-history-copy"><strong>${escapeHtml(item.title || "Percakapan baru")}</strong><small>${escapeHtml(preview.slice(0, 72))}</small></span>
            <time>${time}</time>
          </button>`;
        }).join("")}
      </section>`).join("");

    const overlay = createShell("Riwayat Percakapan", `
      <div class="furina-stage2-search"><span>⌕</span><input id="furina-stage2-search-input" placeholder="Cari percakapan…" /></div>
      <div class="furina-stage2-filters"><button class="active">Semua</button><button>Chat</button><button>Gambar</button><button>Disematkan</button></div>
      <div id="furina-stage2-history-list">${rows || '<div class="furina-stage2-empty">Belum ada riwayat percakapan.</div>'}</div>`);

    overlay.querySelectorAll("[data-conversation]").forEach((button) => {
      button.addEventListener("click", () => {
        localStorage.setItem("furina:activeConvoId", button.dataset.conversation);
        closeOverlay();
        location.reload();
      });
    });
    overlay.querySelector("#furina-stage2-search-input")?.addEventListener("input", (event) => {
      const q = event.target.value.toLowerCase();
      overlay.querySelectorAll(".furina-stage2-history-item").forEach((item) => {
        item.hidden = !item.textContent.toLowerCase().includes(q);
      });
    });
  }

  function dashboardView() {
    const convos = currentConversations();
    const model = activeModel();
    const overlay = createShell("Dashboard", `
      <div class="furina-stage2-dashboard-grid">
        <article class="furina-stage2-card furina-stage2-card-accent">
          <span class="furina-stage2-card-icon">✦</span>
          <div><small>Mode AI aktif</small><strong>${escapeHtml(model === "Belum dipilih" ? "Lovable AI" : model)}</strong><p>Siap digunakan untuk percakapan.</p></div>
        </article>
        <article class="furina-stage2-card"><small>Riwayat</small><strong>${convos.length}</strong><p>Percakapan tersimpan</p></article>
        <article class="furina-stage2-card"><small>Model lokal</small><strong>${model === "Belum dipilih" ? 0 : 1}</strong><p>Model sedang aktif</p></article>
      </div>
      <section class="furina-stage2-section">
        <h2>Aksi cepat</h2>
        <div class="furina-stage2-actions">
          <button data-action="new">＋<span>Chat baru</span></button>
          <button data-action="image">▧<span>Kirim gambar</span></button>
          <button data-action="models">⬡<span>Kelola model</span></button>
          <button data-action="history">◴<span>Lihat riwayat</span></button>
        </div>
      </section>
      <section class="furina-stage2-section">
        <h2>Aktivitas terbaru</h2>
        ${convos.slice(0, 3).map((c) => `<div class="furina-stage2-activity"><span>✦</span><div><strong>${escapeHtml(c.title || "Percakapan baru")}</strong><small>${new Date(c.updatedAt || Date.now()).toLocaleString("id-ID")}</small></div></div>`).join("") || '<div class="furina-stage2-empty">Aktivitas akan muncul setelah kamu mulai berbicara.</div>'}
      </section>`);

    overlay.querySelector('[data-action="new"]')?.addEventListener("click", () => { closeOverlay(); clickExisting("Percakapan baru"); });
    overlay.querySelector('[data-action="image"]')?.addEventListener("click", () => { closeOverlay(); document.querySelector('input[type="file"][accept*="image"]')?.click(); });
    overlay.querySelector('[data-action="models"]')?.addEventListener("click", () => { closeOverlay(); openModels(); });
    overlay.querySelector('[data-action="history"]')?.addEventListener("click", historyView);
  }

  function settingsView() {
    closeOverlay();
    clickExisting("Pengaturan");
  }

  function openModels() {
    closeOverlay();
    if (window.FurinaNative?.openModelManager) window.FurinaNative.openModelManager();
    else alert("Pengelola model hanya tersedia di APK Android Furina.");
  }

  function setView(view) {
    state.view = view;
    localStorage.setItem(STORAGE_KEY, view);
    updateNav();
    if (view === "chat") closeOverlay();
    if (view === "history") historyView();
    if (view === "dashboard") dashboardView();
    if (view === "model") openModels();
    if (view === "settings") settingsView();
  }

  function updateNav() {
    document.querySelectorAll(".furina-stage2-nav button").forEach((button) => {
      button.classList.toggle("active", button.dataset.view === state.view);
    });
  }

  function mountNav() {
    if (document.querySelector(".furina-stage2-nav")) return;
    const nav = document.createElement("nav");
    nav.className = "furina-stage2-nav";
    nav.innerHTML = [
      ["chat", "◉", "Chat"],
      ["history", "◴", "Riwayat"],
      ["dashboard", "▦", "Dashboard"],
      ["model", "⬡", "Model"],
      ["settings", "⚙", "Pengaturan"],
    ].map(([view, icon, label]) => `<button data-view="${view}"><span>${icon}</span><small>${label}</small></button>`).join("");
    document.body.appendChild(nav);
    nav.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-view]");
      if (button) setView(button.dataset.view);
    });
    updateNav();
  }

  function simplifyChatHeader() {
    const root = document.querySelector("#root") || document.body;
    root.classList.add("furina-stage2-active");
    const header = root.querySelector("header");
    if (header) header.classList.add("furina-stage2-chat-header");
    const chip = header?.querySelector(".glass-chip");
    if (chip) {
      const title = chip.querySelector("span:nth-child(2)");
      if (title) title.textContent = "Furina";
      chip.querySelectorAll("span").forEach((span, index) => { if (index > 1) span.style.display = "none"; });
    }
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  }

  function boot() {
    mountNav();
    simplifyChatHeader();
    const observer = new MutationObserver(() => simplifyChatHeader());
    observer.observe(document.body, { subtree: true, childList: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
