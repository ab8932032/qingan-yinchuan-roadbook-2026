const CACHE_VERSION = "qinggan-roadbook-v1";
const CORE_CACHE = `${CACHE_VERSION}-core`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./scripts/amap-config.js",
  "./assets/app-icon.svg",
  "./assets/app-icon-180.png",
  "./assets/app-icon-192.png",
  "./assets/app-icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CORE_CACHE)
      .then((cache) => cache.addAll(CORE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith("qinggan-roadbook-") && ![CORE_CACHE, RUNTIME_CACHE].includes(key))
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

const cacheResponse = async (cacheName, request, response) => {
  if (!response || (!response.ok && response.type !== "opaque")) return response;
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  return response;
};

const networkFirstPage = async (request) => {
  try {
    const response = await fetch(request);
    return cacheResponse(CORE_CACHE, request, response);
  } catch (_) {
    return (await caches.match(request, { ignoreSearch: true })) ||
      (await caches.match("./index.html"));
  }
};

const cacheFirstMedia = async (request) => {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    return cacheResponse(RUNTIME_CACHE, request, response);
  } catch (_) {
    return new Response("", { status: 504, statusText: "Offline" });
  }
};

const staleWhileRevalidate = async (request) => {
  const cached = await caches.match(request);
  const update = fetch(request)
    .then((response) => cacheResponse(RUNTIME_CACHE, request, response))
    .catch(() => null);
  return cached || (await update) || new Response("", { status: 504, statusText: "Offline" });
};

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request));
    return;
  }

  if (request.destination === "image") {
    event.respondWith(cacheFirstMedia(request));
    return;
  }

  if (["style", "font"].includes(request.destination)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  const url = new URL(request.url);
  const scopePath = new URL(self.registration.scope).pathname;
  const relativePath = url.pathname.startsWith(scopePath) ? url.pathname.slice(scopePath.length) : null;
  const corePath = relativePath === "" ? "./" : `./${relativePath}`;
  if (url.origin === self.location.origin && relativePath !== null && CORE_ASSETS.includes(corePath)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
