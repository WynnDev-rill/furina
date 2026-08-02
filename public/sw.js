const CACHE_NAME = "furina-unified-shell-v3";
const FIXED_ASSETS = [
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/furina-migration.js",
  "/furina-ui.js",
  "/furina-ui.css",
  "/furina-voice.js",
  "/furina-sw-register.js",
];
const CACHEABLE_EXTENSION = /\.(?:js|mjs|css|png|jpe?g|webp|svg|gif|ico|woff2?|ttf)(?:[?#].*)?$/i;

function shouldBypass(url) {
  return url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/_server/") ||
    url.pathname.includes("__server") ||
    url.pathname.endsWith("/update.json") ||
    url.pathname.endsWith("/Furina.apk");
}

function sameOriginUrl(value, baseUrl) {
  try {
    const url = new URL(value, baseUrl);
    if (url.origin !== self.location.origin || shouldBypass(url)) return null;
    return url.href;
  } catch {
    return null;
  }
}

function discoverDependencies(text, baseUrl, contentType) {
  const found = new Set();
  const add = (value) => {
    const url = sameOriginUrl(String(value || "").trim(), baseUrl);
    if (url && CACHEABLE_EXTENSION.test(url)) found.add(url);
  };

  if (/text\/html/i.test(contentType)) {
    for (const match of text.matchAll(/(?:src|href)\s*=\s*["']([^"']+)["']/gi)) add(match[1]);
  }
  if (/text\/css/i.test(contentType)) {
    for (const match of text.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/gi)) add(match[1]);
    for (const match of text.matchAll(/@import\s+(?:url\()?\s*["']([^"']+)["']/gi)) add(match[1]);
  }
  if (/javascript|ecmascript/i.test(contentType)) {
    for (const match of text.matchAll(/["'`]([^"'`\s]+\.(?:js|mjs|css|png|jpe?g|webp|svg|gif|woff2?|ttf)(?:\?[^"'`\s]*)?)["'`]/gi)) add(match[1]);
  }
  return [...found];
}

async function fetchAndCacheTree(cache, value, visited, depth = 0) {
  const url = sameOriginUrl(value, self.location.origin);
  if (!url || visited.has(url) || visited.size >= 120) return;
  visited.add(url);

  try {
    const request = new Request(url, { cache: "reload", credentials: "same-origin" });
    const response = await fetch(request);
    if (!response.ok) return;
    await cache.put(request, response.clone());

    const contentType = response.headers.get("content-type") || "";
    if (depth >= 2 || !/(?:text\/html|text\/css|javascript|ecmascript)/i.test(contentType)) return;
    const text = await response.text();
    const dependencies = discoverDependencies(text, url, contentType);
    await Promise.allSettled(dependencies.map((dependency) => fetchAndCacheTree(cache, dependency, visited, depth + 1)));
  } catch {
    // One optional asset must not prevent the rest of the shell from installing.
  }
}

async function precacheShell() {
  const cache = await caches.open(CACHE_NAME);
  const visited = new Set();

  try {
    const rootRequest = new Request("/", { cache: "reload", credentials: "same-origin" });
    const rootResponse = await fetch(rootRequest);
    if (rootResponse.ok) {
      await cache.put("/", rootResponse.clone());
      const html = await rootResponse.text();
      const dependencies = discoverDependencies(html, self.location.origin, "text/html");
      await Promise.allSettled(dependencies.map((dependency) => fetchAndCacheTree(cache, dependency, visited)));
    }
  } catch {
    // A later online navigation will retry and populate the cache through fetch handling.
  }

  await Promise.allSettled(FIXED_ASSETS.map((asset) => fetchAndCacheTree(cache, asset, visited)));
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    await precacheShell();
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

async function networkAndCache(request, fallbackToRoot) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      if (request.mode === "navigate") {
        await cache.put("/", response.clone());
        const contentType = response.headers.get("content-type") || "";
        if (/text\/html/i.test(contentType)) {
          const html = await response.clone().text();
          const dependencies = discoverDependencies(html, request.url, contentType);
          Promise.allSettled(dependencies.map((dependency) => fetchAndCacheTree(cache, dependency, new Set()))).catch(() => undefined);
        }
      }
    }
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
      fetch(request).then(async (response) => {
        if (response.ok) await cache.put(request, response.clone());
      }).catch(() => undefined);
      return cached;
    }
    return networkAndCache(request, false);
  })());
});
