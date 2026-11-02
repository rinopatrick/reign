/* Reign service worker — offline-first app shell, network-first API.

- App shell (/, /static/*): cache-first, fallback to network, then cache.
- API (/api/*, /health): network-first with 5s timeout, fallback to cache
  only for GET; mutations never served from cache.
- Versioned cache name: bump APP_VERSION on shell changes.
*/

const APP_VERSION = "v0.4.0-pwa1";
const SHELL_CACHE = `reign-shell-${APP_VERSION}`;
const API_CACHE = `reign-api-${APP_VERSION}`;
const SHELL_URLS = ["/", "/static/index.html", "/static/app.js", "/static/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("reign-") && ![SHELL_CACHE, API_CACHE].includes(k))
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

function isApiRequest(url) {
  return url.pathname.startsWith("/api/") || url.pathname === "/health";
}

function isShellRequest(url) {
  return (
    url.pathname === "/" ||
    url.pathname === "/static/index.html" ||
    url.pathname.startsWith("/static/")
  );
}

async function networkFirst(request) {
  const cache = await caches.open(API_CACHE);
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(request, { signal: controller.signal });
    clearTimeout(timer);
    if (request.method === "GET" && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch (e) {
    if (request.method === "GET") {
      const cached = await cache.match(request);
      if (cached) return cached;
    }
    throw e;
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (isApiRequest(url)) {
    event.respondWith(networkFirst(event.request));
  } else if (isShellRequest(url)) {
    event.respondWith(cacheFirst(event.request));
  }
});
