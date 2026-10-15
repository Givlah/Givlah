// Givlah service worker. Caches only static shell files and an offline notice.
// Pages, photos and anything personal always come from the network.
const CACHE = "givlah-shell-v1";
const PRECACHE = [{% for url in precache %}"{{ url|escapejs }}"{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    // Never show a stale page: offline means an explicit notice instead.
    event.respondWith(fetch(request).catch(() => caches.match("/offline/")));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)));
  }
});
