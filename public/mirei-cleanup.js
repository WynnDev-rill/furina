(() => {
  const marker = "mirei:legacy-cache-cleaned:v1";
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
        Promise.all(keys.filter((key) => /furina|offline|stage/i.test(key)).map((key) => caches.delete(key))),
      ),
    );
  }

  Promise.allSettled(tasks).finally(() => localStorage.setItem(marker, "1"));
})();
