// WattKaç: statik site (site/) önünde küçük worker.
// Ücretsiz plan için: worker yalnızca /api/* isteklerinde çalışır (wrangler.jsonc → run_worker_first). Diğer her şey
// doğrudan statik dosyadır ve worker isteği sayılmaz. www → wattkac.com yönlendirmesi Cloudflare yönlendirme kuralıyla yapılır.
//
//   POST /api/geri-bildirim      → geri_bildirim tablosu
//   POST /api/olay               → analiz tablosu (çerezsiz, kişisel veri yok; gün + olay + değer başına sayaç)
//   POST /api/panel/giris        → PANEL_SIFRE ile giriş, imzalı çerez
//   POST /api/panel/cikis
//   GET  /api/panel/ozet?gun=30  → analiz özetleri
//   GET  /api/panel/geri-bildirim?durum=yeni|tum
//   POST /api/panel/geri-bildirim {id, durum}
const ANA = "wattkac.com";
const YONLENDIR = new Set(["www.wattkac.com", "wattkac.xyz", "www.wattkac.xyz"]);
const TURLER = new Set(["hata", "istasyon", "fiyat", "kampanya", "oneri", "diger"]);
const DURUMLAR = new Set(["yeni", "okundu", "cozuldu", "cop"]);
// Analiz: izin verilen olay adları. Değer alanı kısa bir etiket (ör. ağ adı, sayfa adı); kişisel veri içermez.
const OLAYLAR = new Set(["ziyaret", "tekil", "kaynak", "cihaz", "uygulama", "gorunum", "istasyon", "kampanya", "yol_tarifi",
  "filtre", "siralama", "konum", "geri_bildirim", "kurulum", "seo_sayfa", "panel_disi"]);
// Ücretsiz D1 yazma sınırını (günde 100.000 satır) korumak için: günlük ziyaret bu sayıyı aşınca yalnızca ziyaret sayılır
const AYRINTI_SINIRI = 3000;
const CEREZ = "wk_panel";
const CEREZ_GUN = 30;

const json = (o, status = 200, h = {}) =>
  new Response(JSON.stringify(o), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...h } });
const temiz = (v, n) => String(v ?? "").replace(/[\u0000-\u001F\u007F]/g, " ").trim().slice(0, n);
const gunTR = (t = Date.now()) => new Date(t + 3 * 3600e3).toISOString().slice(0, 10);

async function govde(request, max) {
  const len = Number(request.headers.get("content-length") || 0);
  if (len > max) throw new Error("uzun");
  const t = await request.text();
  if (t.length > max) throw new Error("uzun");
  return JSON.parse(t || "{}");
}

/* ---------- Geri bildirim ---------- */
async function geriBildirim(request, env) {
  if (request.method !== "POST") return json({ ok: false, hata: "yöntem" }, 405);
  let b;
  try { b = await govde(request, 8000); } catch { return json({ ok: false, hata: "geçersiz" }, 400); }
  // Bot tuzağı: görünmeyen alan doluysa ya da form 3 saniyeden kısa sürede gönderildiyse sessizce kabul et, kaydetme
  if (b.web || (Number(b.sure) > 0 && Number(b.sure) < 3000)) return json({ ok: true });
  const tur = TURLER.has(b.tur) ? b.tur : "diger";
  const mesaj = temiz(b.mesaj, 2000);
  if (mesaj.length < 5) return json({ ok: false, hata: "mesaj kısa" }, 400);
  const son = await env.DB.prepare("SELECT COUNT(*) AS n FROM geri_bildirim WHERE zaman > ?")
    .bind(new Date(Date.now() - 600e3).toISOString()).first();
  if (son && son.n > 60) return json({ ok: false, hata: "yoğun" }, 429);
  await env.DB.prepare("INSERT INTO geri_bildirim (zaman, tur, mesaj, iletisim, istasyon, sayfa) VALUES (?, ?, ?, ?, ?, ?)")
    .bind(new Date().toISOString(), tur, mesaj, temiz(b.iletisim, 120) || null, temiz(b.istasyon, 300) || null, temiz(b.sayfa, 200) || null)
    .run();
  return json({ ok: true });
}

/* ---------- Kullanım analizi ---------- */
async function olay(request, env) {
  if (request.method !== "POST") return json({ ok: false }, 405);
  let b;
  try { b = await govde(request, 4000); } catch { return json({ ok: false }, 400); }
  const gun = gunTR();
  const say = new Map();
  for (const x of Array.isArray(b.e) ? b.e.slice(0, 40) : []) {
    if (!Array.isArray(x)) continue;
    const ad = String(x[0] || ""), deger = temiz(x[1], 60), n = Math.max(1, Math.min(50, Math.floor(Number(x[2]) || 1)));
    if (!OLAYLAR.has(ad)) continue;
    const k = ad + "\u0001" + deger;
    say.set(k, Math.min(50, (say.get(k) || 0) + n));
  }
  if (!say.size) return json({ ok: true });
  // Günlük ziyaret sınırı aşıldıysa ayrıntıları yazma, yalnızca ziyareti say
  const z = await env.DB.prepare("SELECT sayi FROM analiz WHERE gun = ? AND olay = 'ziyaret' AND deger = ''").bind(gun).first();
  const ayrinti = !z || z.sayi < AYRINTI_SINIRI;
  const st = env.DB.prepare("INSERT INTO analiz (gun, olay, deger, sayi) VALUES (?, ?, ?, ?) ON CONFLICT (gun, olay, deger) DO UPDATE SET sayi = sayi + excluded.sayi");
  const islemler = [];
  for (const [k, n] of say) {
    const [ad, deger] = k.split("\u0001");
    if (!ayrinti && ad !== "ziyaret") continue;
    islemler.push(st.bind(gun, ad, deger, n));
  }
  if (islemler.length) await env.DB.batch(islemler);
  return json({ ok: true });
}

/* ---------- Panel girişi (HMAC imzalı çerez) ---------- */
const enc = new TextEncoder();
async function hmac(anahtar, veri) {
  const k = await crypto.subtle.importKey("raw", enc.encode(anahtar), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const s = new Uint8Array(await crypto.subtle.sign("HMAC", k, enc.encode(veri)));
  return btoa(String.fromCharCode(...s)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function esit(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}
async function oturumVar(request, env) {
  if (!env.PANEL_SIFRE) return false;
  const c = (request.headers.get("cookie") || "").split(/;\s*/).find(x => x.startsWith(CEREZ + "="));
  if (!c) return false;
  const [bitis, imza] = c.slice(CEREZ.length + 1).split(".");
  if (!bitis || !imza || Number(bitis) < Date.now()) return false;
  return esit(imza, await hmac(env.PANEL_SIFRE, "panel:" + bitis));
}
async function giris(request, env) {
  if (request.method !== "POST") return json({ ok: false }, 405);
  if (!env.PANEL_SIFRE) return json({ ok: false, hata: "Panel şifresi henüz tanımlanmadı (PANEL_SIFRE)." }, 503);
  // Kaba kuvvet koruması: dakikada en fazla 10 deneme (tüm site için)
  const dk = new Date().toISOString().slice(0, 16);
  const d = await env.DB.prepare("INSERT INTO giris_deneme (dakika, sayi) VALUES (?, 1) ON CONFLICT (dakika) DO UPDATE SET sayi = sayi + 1 RETURNING sayi").bind(dk).first();
  if (d && d.sayi > 10) return json({ ok: false, hata: "Çok fazla deneme, bir dakika sonra tekrar dene." }, 429);
  let b;
  try { b = await govde(request, 1000); } catch { return json({ ok: false }, 400); }
  const s = String(b.sifre || "");
  const ok = esit(await hmac("wk", s), await hmac("wk", env.PANEL_SIFRE));
  if (!ok) { await new Promise(r => setTimeout(r, 600)); return json({ ok: false, hata: "Şifre yanlış." }, 401); }
  if (Math.random() < 0.1) await env.DB.prepare("DELETE FROM giris_deneme WHERE dakika < ?").bind(new Date(Date.now() - 864e5).toISOString().slice(0, 16)).run();
  const bitis = String(Date.now() + CEREZ_GUN * 864e5);
  const deger = bitis + "." + (await hmac(env.PANEL_SIFRE, "panel:" + bitis));
  return json({ ok: true }, 200, { "set-cookie": `${CEREZ}=${deger}; Path=/api/panel; Max-Age=${CEREZ_GUN * 86400}; HttpOnly; Secure; SameSite=Strict` });
}

async function ozet(url, env) {
  const gunSayisi = Math.max(1, Math.min(90, Number(url.searchParams.get("gun")) || 30));
  const bas = gunTR(Date.now() - (gunSayisi - 1) * 864e5);
  const [gunluk, toplam, gb] = await env.DB.batch([
    env.DB.prepare("SELECT gun, olay, SUM(sayi) AS n FROM analiz WHERE gun >= ? AND olay IN ('ziyaret','tekil','istasyon','kampanya','yol_tarifi','geri_bildirim') GROUP BY gun, olay ORDER BY gun").bind(bas),
    env.DB.prepare("SELECT olay, deger, SUM(sayi) AS n FROM analiz WHERE gun >= ? GROUP BY olay, deger ORDER BY n DESC").bind(bas),
    env.DB.prepare("SELECT durum, COUNT(*) AS n FROM geri_bildirim GROUP BY durum"),
  ]);
  const bugun = await env.DB.prepare("SELECT COUNT(*) AS satir, COALESCE(SUM(sayi),0) AS n FROM analiz WHERE gun = ?").bind(gunTR()).first();
  return json({ ok: true, bas, gun: gunSayisi, bugun: gunTR(), gunluk: gunluk.results, toplam: toplam.results, gb: gb.results,
    sinir: { bugun_olay: bugun.n, bugun_satir: bugun.satir, ayrinti_siniri: AYRINTI_SINIRI } });
}

async function panelGeriBildirim(request, url, env) {
  if (request.method === "POST") {
    let b;
    try { b = await govde(request, 1000); } catch { return json({ ok: false }, 400); }
    if (!DURUMLAR.has(b.durum) || !Number.isInteger(b.id)) return json({ ok: false }, 400);
    await env.DB.prepare("UPDATE geri_bildirim SET durum = ? WHERE id = ?").bind(b.durum, b.id).run();
    return json({ ok: true });
  }
  const durum = url.searchParams.get("durum") || "acik";
  const q = durum === "tum" ? "SELECT * FROM geri_bildirim WHERE durum != 'cop' ORDER BY id DESC LIMIT 200"
    : "SELECT * FROM geri_bildirim WHERE durum IN ('yeni','okundu') ORDER BY id DESC LIMIT 200";
  const r = await env.DB.prepare(q).all();
  return json({ ok: true, liste: r.results });
}

async function panel(request, url, env) {
  const yol = url.pathname.slice("/api/panel/".length);
  if (yol === "giris") return giris(request, env);
  if (yol === "cikis") return json({ ok: true }, 200, { "set-cookie": `${CEREZ}=; Path=/api/panel; Max-Age=0; HttpOnly; Secure; SameSite=Strict` });
  if (!(await oturumVar(request, env))) return json({ ok: false, hata: "giriş gerekli" }, 401);
  if (yol === "ozet") return ozet(url, env);
  if (yol === "geri-bildirim") return panelGeriBildirim(request, url, env);
  return json({ ok: false }, 404);
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
    if (url.pathname.startsWith("/api/")) {
      if (!env.DB) return json({ ok: false, hata: "veritabanı yok" }, 503);
      try {
        if (url.pathname === "/api/geri-bildirim") return await geriBildirim(request, env);
        if (url.pathname === "/api/olay") return await olay(request, env);
        if (url.pathname.startsWith("/api/panel/")) return await panel(request, url, env);
      } catch {
        return json({ ok: false, hata: "sunucu" }, 500);
      }
      return json({ ok: false }, 404);
    }
    return env.ASSETS.fetch(request);
  },
};
