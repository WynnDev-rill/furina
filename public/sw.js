const CACHE_NAME = "furina-unified-shell-v1";
const PRECACHE = [
  "/",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/furina-voice.js",
  "/furina-sw-register.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await Promise.allSettled(PRECACHE.map((url) => cache.add(new Request(url, { cache: "reload" }))));
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

function shouldBypass(url) {
  return url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/_server/") ||
    url.pathname.includes("__server") ||
    url.pathname.endsWith("/update.json") ||
    url.pathname.endsWith("/Furina.apk");
}

async function networkAndCache(request, fallbackToRoot) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    if (request.mode === "navigate" && response.ok) await cache.put("/", response.clone());
    return response;
  } catch (error) {
    const exact = await cache.match(request, { ignoreSearch: true });
    if (exact) return exact;
    if (fallbackToRoot) {
      const root = await cache.match("/");
      if (root) return root;
    }
    throw error;
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || shouldBypass(url)) return;

  if (request.mode === "navigate") {
    event.respondWith(networkAndCache(request, true));
    return;
  }

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) {
      event.waitUntil(fetch(request).then((response) => {
        if (response.ok) return cache.put(request, response.clone());
        return undefined;
      }).catch(() => undefined));
      return cached;
    }
    return networkAndCache(request, false);
  })());
});
