const CACHE_NAME = "furina-offline-shell-v4";
const FIXED_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/furina-migration.js",
  "/furina-ui.js",
  "/furina-ui.css",
  "/furina-sw-register.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.allSettled(FIXED_ASSETS.map(async (asset) => {
      const response = await fetch(new Request(asset, { cache: "reload", credentials: "same-origin" }));
      if (response.ok) await cache.put(asset, response);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((name) => name.startsWith("furina-") && name !== CACHE_NAME).map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return cached;

    try {
      const response = await fetch(request);
      if (response.ok) await cache.put(request, response.clone());
      return response;
    } catch (error) {
      if (request.mode === "navigate") {
        const root = await cache.match("/");
        if (root) return root;
      }
      throw error;
    }
  })());
});
