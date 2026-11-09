// WattKaç: statik site (site/) önünde küçük worker.
// 1) wattkac.xyz, www.wattkac.xyz ve www.wattkac.com → https://wattkac.com (301, yol ve sorgu korunur).
// 2) POST /api/geri-bildirim → D1 (wattkac-geri-bildirim) tablosuna yazar.
// Diğer tüm istekler (wattkac.com, workers.dev) doğrudan statik dosyalardan sunulur.
const ANA = "wattkac.com";
const YONLENDIR = new Set(["www.wattkac.com", "wattkac.xyz", "www.wattkac.xyz"]);
const TURLER = new Set(["hata", "istasyon", "fiyat", "kampanya", "oneri", "diger"]);

const json = (o, status = 200) =>
  new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

const temiz = (v, n) => String(v ?? "").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "").trim().slice(0, n);

async function geriBildirim(request, env) {
  if (request.method !== "POST") return json({ ok: false, hata: "yöntem" }, 405);
  if (!env.DB) return json({ ok: false, hata: "kayıt kapalı" }, 503);
  const len = Number(request.headers.get("content-length") || 0);
  if (len > 8000) return json({ ok: false, hata: "çok uzun" }, 413);
  let b;
  try { b = await request.json(); } catch { return json({ ok: false, hata: "geçersiz" }, 400); }
  // Bot tuzağı: görünmeyen alan doluysa ya da form 3 saniyeden kısa sürede gönderildiyse sessizce kabul et, kaydetme
  if (b.web || (Number(b.sure) > 0 && Number(b.sure) < 3000)) return json({ ok: true });
  const tur = TURLER.has(b.tur) ? b.tur : "diger";
  const mesaj = temiz(b.mesaj, 2000);
  if (mesaj.length < 5) return json({ ok: false, hata: "mesaj kısa" }, 400);
  // Basit taşma koruması: son 10 dakikada 60'tan fazla kayıt varsa yeni kayıt alma
  const son = await env.DB.prepare("SELECT COUNT(*) AS n FROM geri_bildirim WHERE zaman > ?")
    .bind(new Date(Date.now() - 600e3).toISOString()).first();
  if (son && son.n > 60) return json({ ok: false, hata: "yoğun" }, 429);
  await env.DB.prepare("INSERT INTO geri_bildirim (zaman, tur, mesaj, iletisim, istasyon, sayfa) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(new Date().toISOString(), tur, mesaj, temiz(b.iletisim, 120) || null, temiz(b.istasyon, 300) || null, temiz(b.sayfa, 200) || null)
    .run();
  return json({ ok: true });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (YONLENDIR.has(url.hostname)) {
      url.protocol = "https:";
      url.hostname = ANA;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    if (url.pathname === "/api/geri-bildirim") {
      try { return await geriBildirim(request, env); } catch { return json({ ok: false, hata: "sunucu" }, 500); }
    }
    return env.ASSETS.fetch(request);
  },
};
