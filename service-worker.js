const CACHE_VERSION = "qinggan-roadbook-v22-music-retouch-20261024";
const CORE_CACHE = `${CACHE_VERSION}-core`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./roadbook-original.html",
  "./scripts/atlas-data.js",
  "./scripts/atlas.js",
  "./assets/atlas.css",
  "./assets/sandtable.svg",
  "./scripts/theater-data.js",
  "./scripts/theater-data.js?v=22",
  "./scripts/theater.js",
  "./assets/theater.css",
  "./assets/paper-theater.svg",
  "./assets/paper-portrait.svg",
  "./assets/focus.css",
  "./scripts/journey-archive.js",
  "./scripts/journey-plan.js",
  "./assets/place-popup.css",
  "./manifest.webmanifest",
  "./scripts/amap-config.js",
  "./scripts/display-mode.js",
  "./assets/display-mode.css",
  "./assets/editorial.css",
  "./assets/return-chapter.css",
  "./scripts/return-chapter.js",
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
    const response = await fetch(request, {cache:"no-store"});
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
  const runtime = await caches.open(RUNTIME_CACHE);
  const core = await caches.open(CORE_CACHE);
  const cached = (await runtime.match(request)) || (await core.match(request));
  const update = fetch(request)
    .then((response) => cacheResponse(RUNTIME_CACHE, request, response))
    .catch(() => null);
  return cached || (await update) || new Response("", { status: 504, statusText: "Offline" });
};

const networkFirstAsset = async (request) => {
  try {
    return await cacheResponse(CORE_CACHE, request, await fetch(request, {cache:"no-store"}));
  } catch (_) {
    return (await caches.match(request)) || new Response("", { status: 504, statusText: "Offline" });
  }
};

// Keep only complete video responses, then satisfy native-player byte ranges from that copy.
const filmWithRange = async (request) => {
  const cache = await caches.open(RUNTIME_CACHE);
  let response = await cache.match(request.url);
  if (!response) {
    try {
      response = await fetch(request.url);
      if (response.status !== 200) return response;
      await cache.put(request.url,response.clone());
    } catch (_) { return new Response("", {status:504,statusText:"Offline"}); }
  }
  const range = request.headers.get("range");
  if (!range) return response;
  const bytes = await response.arrayBuffer(), length = bytes.byteLength;
  const match = /^bytes=(\d*)-(\d*)$/.exec(range);
  let start = match?.[1] ? Number(match[1]) : (match?.[2] ? Math.max(0,length-Number(match[2])) : NaN);
  let end = match?.[1] && match?.[2] ? Math.min(length-1,Number(match[2])) : length-1;
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start > end || start >= length) {
    return new Response(null,{status:416,headers:{"Content-Range":`bytes */${length}`}});
  }
  return new Response(bytes.slice(start,end+1),{status:206,headers:{
    "Content-Type":response.headers.get("Content-Type") || "video/mp4",
    "Content-Length":String(end-start+1),"Accept-Ranges":"bytes","Content-Range":`bytes ${start}-${end}/${length}`
  }});
};

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request));
    return;
  }

  const url = new URL(request.url);
  const scopePath = new URL(self.registration.scope).pathname;
  const relativePath = url.pathname.startsWith(scopePath) ? url.pathname.slice(scopePath.length) : null;
  const corePath = relativePath === "" ? "./" : `./${relativePath}`;
  if (url.origin === self.location.origin && relativePath !== null && CORE_ASSETS.includes(corePath)) {
    event.respondWith(networkFirstAsset(request));
    return;
  }
  if (url.origin === self.location.origin && relativePath?.startsWith("media/films/") && url.pathname.endsWith(".mp4")) {
    event.respondWith(filmWithRange(request));
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

});
