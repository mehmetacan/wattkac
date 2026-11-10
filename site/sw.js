/* WattKaç service worker: uygulamayı hızlı açar ve bağlantı yokken son görülen veriyi gösterir. */
const SURUM = "wk-v8";
const KABUK = ["./", "./index.html", "./manifest.webmanifest", "./logo.png", "./icons/icon-192.png", "./icons/icon-512.png",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"];
const VERI = /\/(kampanyalar|istasyonlar|tarifeler)\.json$/;
const KAROLAR = "wk-karo", KARO_SINIR = 400;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SURUM).then(c => Promise.all(KABUK.map(u => c.add(new Request(u, { mode: u.startsWith("http") ? "no-cors" : "same-origin" })).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SURUM && k !== KAROLAR).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

async function agOnce(req, ad) { // önce ağ, olmazsa önbellek (sayfa)
  try { const r = await fetch(req); if (r.ok) (await caches.open(ad)).put(req, r.clone()); return r; }
  catch { return (await caches.match(req)) || (await caches.match("./index.html")) || Response.error(); }
}
async function agOnceVeri(req) { // veri dosyaları: her zaman güncelini dene; bağlantı yoksa son kaydedileni ver
  const c = await caches.open(SURUM);
  try { const r = await fetch(req); if (r.ok) c.put(req, r.clone()); return r; }
  catch { return (await c.match(req, { ignoreSearch: true })) || Response.error(); }
}
async function onbellekOnce(req, ad, sinir) { // kütüphaneler ve harita karoları
  const c = await caches.open(ad), h = await c.match(req);
  if (h) return h;
  const r = await fetch(req);
  if (r.ok || r.type === "opaque") {
    await c.put(req, r.clone());
    if (sinir) c.keys().then(ks => { if (ks.length > sinir) ks.slice(0, ks.length - sinir).forEach(k => c.delete(k)); });
  }
  return r;
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const u = new URL(req.url);
  if (req.mode === "navigate") return e.respondWith(agOnce(req, SURUM));
  if (u.origin === location.origin && VERI.test(u.pathname)) return e.respondWith(agOnceVeri(req));
  if (u.hostname === "tile.openstreetmap.org") return e.respondWith(onbellekOnce(req, KAROLAR, KARO_SINIR));
  if (u.hostname === "cdnjs.cloudflare.com" || (u.origin === location.origin && /\.(png|webmanifest)$/.test(u.pathname)))
    return e.respondWith(onbellekOnce(req, SURUM));
});
