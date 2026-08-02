(() => {
  "use strict";

  const ROOT_CLASS = "furina-enhanced-ui";
  let localDrawer = null;

  function bridgeNetworkAvailable() {
    try {
      if (window.FurinaNetwork?.isOnline) return Boolean(window.FurinaNetwork.isOnline());
    } catch {}
    return null;
  }

  function repairWebViewOnlineState() {
    const nativeValue = bridgeNetworkAvailable();
    if (nativeValue == null) return;
    try {
      const descriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, "onLine");
      if (descriptor?.get?.__furinaPatched) return;
      const originalGetter = descriptor?.get;
      const getter = function () {
        const current = bridgeNetworkAvailable();
        return current == null ? (originalGetter ? originalGetter.call(this) : true) : current;
      };
      getter.__furinaPatched = true;
      Object.defineProperty(Navigator.prototype, "onLine", { configurable: true, enumerable: true, get: getter });
      window.dispatchEvent(new Event(nativeValue ? "online" : "offline"));
    } catch {}
  }

  function hideBottomNavigation() {
    document.querySelectorAll("nav.absolute.inset-x-0.bottom-0, .bottom-nav").forEach((nav) => {
      nav.setAttribute("aria-hidden", "true");
      nav.classList.add("furina-bottom-nav-removed");
    });
  }

  function enhanceHostedUi() {
    document.querySelectorAll("header.absolute.inset-x-0.top-0 > div").forEach((node) => node.classList.add("furina-top-shell"));
    document.querySelectorAll("aside.absolute.inset-y-0.left-0").forEach((node) => node.classList.add("furina-drawer"));
    document.querySelectorAll("main.absolute.inset-x-0").forEach((node) => node.classList.add("furina-page"));
    document.querySelectorAll("div.flex.flex-col.items-start, div.flex.flex-col.items-end").forEach((node, index) => {
      node.classList.add("furina-message-enter");
      node.style.setProperty("--furina-delay", `${Math.min(index, 8) * 25}ms`);
    });
    document.querySelectorAll("div.absolute.inset-x-0[class*='bottom-[82px]']").forEach((node) => {
      node.classList.add("furina-composer-dock");
    });
  }

  function closeLocalDrawer() {
    localDrawer?.classList.remove("open");
  }

  function createLocalDrawer() {
    if (localDrawer || !document.querySelector(".bottom-nav") || document.querySelector("aside")) return;
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
      if (button.matches("[data-close],.furina-local-backdrop")) return closeLocalDrawer();
      const target = button.dataset.target;
      if (!target) return;
      document.querySelector(`.nav-btn[data-target='${target}']`)?.click();
      closeLocalDrawer();
    });
    document.body.appendChild(drawer);
    localDrawer = drawer;

    const menu = document.getElementById("menu-button");
    if (menu && menu.dataset.furinaDrawerBound !== "1") {
      menu.dataset.furinaDrawerBound = "1";
      menu.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        drawer.classList.add("open");
      }, true);
    }
  }

  function enhance() {
    document.documentElement.classList.add(ROOT_CLASS);
    hideBottomNavigation();
    enhanceHostedUi();
    createLocalDrawer();
  }

  const observer = new MutationObserver(enhance);
  function boot() {
    repairWebViewOnlineState();
    enhance();
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener("focus", repairWebViewOnlineState);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) repairWebViewOnlineState();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
