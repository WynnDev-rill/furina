(() => {
  const root = document.documentElement;

  function syncEnvironment() {
    root.classList.toggle("mirei-native", Boolean(window.MireiNative));
    root.classList.toggle("mirei-offline", navigator.onLine === false);

    const section = document.querySelector("main section");
    root.classList.toggle(
      "mirei-chat-open",
      Boolean(section && section.children && section.children.length > 1),
    );
  }

  function growComposer(target) {
    if (!(target instanceof HTMLTextAreaElement)) return;
    target.style.height = "auto";
    target.style.height = `${Math.min(Math.max(target.scrollHeight, 48), 112)}px`;
  }

  syncEnvironment();

  document.addEventListener("input", (event) => growComposer(event.target), true);
  document.addEventListener("focusin", (event) => {
    if (event.target instanceof HTMLTextAreaElement) {
      root.classList.add("mirei-composer-focus");
      growComposer(event.target);
    }
  });
  document.addEventListener("focusout", (event) => {
    if (event.target instanceof HTMLTextAreaElement) {
      root.classList.remove("mirei-composer-focus");
    }
  });

  window.addEventListener("online", syncEnvironment);
  window.addEventListener("offline", syncEnvironment);

  const observer = new MutationObserver(() => {
    window.requestAnimationFrame(syncEnvironment);
  });
  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  } else {
    document.addEventListener(
      "DOMContentLoaded",
      () => observer.observe(document.body, { childList: true, subtree: true }),
      { once: true },
    );
  }

  // One-time removal of obsolete offline/service-worker caches from older builds.
  const marker = "mirei:legacy-cache-cleaned:v3";
  if (localStorage.getItem(marker) === "1") return;

  const tasks = [];
  if ("serviceWorker" in navigator) {
    tasks.push(
      navigator.serviceWorker.getRegistrations().then((registrations) =>
        Promise.all(registrations.map((registration) => registration.unregister())),
      ),
    );
  }
  if ("caches" in window) {
    tasks.push(
      caches.keys().then((keys) =>
        Promise.all(
          keys
            .filter((key) => /furina|offline|stage/i.test(key))
            .map((key) => caches.delete(key)),
        ),
      ),
    );
  }

  Promise.allSettled(tasks).finally(() => localStorage.setItem(marker, "1"));
})();
