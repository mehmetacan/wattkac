/* WattKaç service worker: uygulamayı hızlı açar ve bağlantı yokken son görülen veriyi gösterir. */
/* Depolama notu: başka alan adından "no-cors" ile alınan yanıtlar (opak yanıt) önbellekte saklanırsa tarayıcı her birini
   kota hesabında birkaç MB sayar. Eskiden harita karoları böyle saklandığı için uygulama telefonda GB'larca yer gösteriyordu.
   Artık harita karoları önbelleğe alınmaz (tarayıcının kendi HTTP önbelleği yeterli) ve kütüphaneler CORS ile, gerçek boyutlarıyla saklanır. */
const SURUM = "wk-v29";
const KABUK = ["./", "./index.html", "./manifest.webmanifest", "./logo.png", "./icons/icon-192.png", "./icons/icon-512.png",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js", "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"];
const VERI = /\/(kampanyalar|istasyonlar|tarifeler)\.json$/;

self.addEventListener("install", e => {
  e.waitUntil(caches.open(SURUM).then(c => Promise.all(KABUK.map(u => c.add(new Request(u, { mode: u.startsWith("http") ? "cors" : "same-origin" })).catch(() => {})))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== SURUM).map(k => caches.delete(k)))).then(() => self.clients.claim()));
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
async function onbellekOnce(req, ad) { // kütüphaneler, simgeler, yazı tipleri (opak yanıt asla saklanmaz)
  const c = await caches.open(ad), h = await c.match(req);
  if (h) return h;
  const r = await fetch(req);
  if (r.ok && r.type !== "opaque") await c.put(req, r.clone());
  return r;
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const u = new URL(req.url);
  // /api/* (ör. anlık durum) hiç ele alınmaz: service worker önbelleğine girmez, doğrudan ağa gider
  if (req.mode === "navigate") return e.respondWith(agOnce(req, SURUM));
  if (u.origin === location.origin && VERI.test(u.pathname)) return e.respondWith(agOnceVeri(req));
  if (u.hostname === "cdnjs.cloudflare.com" || (u.origin === location.origin && /\.(png|webmanifest|woff2)$/.test(u.pathname)))
    return e.respondWith(onbellekOnce(req, SURUM));
});

/* Bildirimler: sunucu içeriksiz bir "uyandırma" gönderir; gösterilecek metin /api/bildirim/icerik'ten alınır. */
self.addEventListener("push", e => e.waitUntil((async () => {
  let d = { baslik: "WattKaç", metin: "Sana uyan yeni bir kampanya var.", url: "./#g=kamp&bana=1" };
  try {
    const s = await self.registration.pushManager.getSubscription();
    if (s) {
      const r = await fetch("/api/bildirim/icerik", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ endpoint: s.endpoint }) });
      const j = await r.json(); if (j.ok && j.baslik) d = { ...d, ...j };
    }
  } catch {}
  await self.registration.showNotification(d.baslik, { body: d.metin, icon: "icons/icon-192.png", badge: "icons/icon-192.png", tag: "wk-kampanya", data: { url: d.url } });
})()));
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "./#g=kamp&bana=1", self.registration.scope).href;
  e.waitUntil(clients.matchAll({ type: "window", includeUncontrolled: true }).then(ws => {
    const w = ws.find(x => x.url.startsWith(self.registration.scope));
    return w ? w.navigate(url).then(c => (c || w).focus()) : clients.openWindow(url);
  }));
});
