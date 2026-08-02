(() => {
  "use strict";

  let localDrawer = null;

  function hideBottomNavigation() {
    document.querySelectorAll(".bottom-nav").forEach((nav) => {
      nav.setAttribute("aria-hidden", "true");
      nav.classList.add("furina-bottom-nav-removed");
    });
  }

  function enhanceUi() {
    document.documentElement.classList.add("furina-enhanced-ui");
    document.querySelectorAll(".message").forEach((node, index) => {
      node.classList.add("furina-message-enter");
      node.style.setProperty("--furina-delay", `${Math.min(index, 8) * 25}ms`);
    });
  }

  function closeDrawer() {
    localDrawer?.classList.remove("open");
  }

  function createDrawer() {
    if (localDrawer) return;
    const drawer = document.createElement("div");
    drawer.className = "furina-local-drawer";
    drawer.innerHTML = `
      <button class="furina-local-backdrop" aria-label="Tutup menu"></button>
      <aside class="furina-local-panel" aria-label="Menu Furina">
        <div class="furina-local-head"><div><small>FURINA</small><strong>Companion Pribadimu</strong></div><button data-close aria-label="Tutup">×</button></div>
        <div class="furina-local-links">
          <button data-target="chat">Chat</button>
          <button data-target="history">Riwayat</button>
          <button data-target="dashboard">Dashboard</button>
          <button data-target="models">Model AI</button>
          <button data-target="settings">Pengaturan</button>
        </div>
      </aside>`;
    drawer.addEventListener("click", (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      if (button.matches("[data-close],.furina-local-backdrop")) return closeDrawer();
      const target = button.dataset.target;
      if (!target) return;
      document.querySelector(`.nav-btn[data-target='${target}']`)?.click();
      closeDrawer();
    });
    document.body.appendChild(drawer);
    localDrawer = drawer;

    const menu = document.getElementById("menu-button");
    if (menu && menu.dataset.furinaDrawerBound !== "1") {
      menu.dataset.furinaDrawerBound = "1";
      menu.setAttribute("aria-label", "Buka menu");
      menu.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        drawer.classList.add("open");
      }, true);
    }
  }

  function enhance() {
    hideBottomNavigation();
    enhanceUi();
    createDrawer();
  }

  const observer = new MutationObserver(enhance);
  function boot() {
    enhance();
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
