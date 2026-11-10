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
//   /api/bildirim/*              → web push aboneliği (aşağıda "Bildirimler")
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

/* ---------- Bildirimler (web push) ----------
   POST /api/bildirim/abone   {abonelik:{endpoint}, profil:{banka,ag,arac,il}}  → kayıt / güncelleme
   POST /api/bildirim/cik     {endpoint}                                         → kaydı sil
   GET  /api/bildirim/anahtar                                                    → VAPID açık anahtarı
   POST /api/bildirim/icerik  {endpoint}                                         → son gönderilen bildirimin metni (service worker okur)
   Zamanlanmış görev (wrangler.jsonc → triggers.crons): profile uyan YENİ kampanyayı bildirir.
     - kampanya başına bir kez, abone başına günde en fazla bir bildirim (aynı gün iki kampanya eklenirse ikincisi ertesi gün gider)
     - yalnızca abonelikten SONRA eklenen kampanyalar (eski kampanyalar için bildirim yağmaz)
     - "kontrol": true (doğrulanmamış) kampanyalar bildirilmez
   Bildirim içeriksiz gönderilir (yalnızca VAPID imzası); böylece şifreleme gerekmez, metni cihaz /api/bildirim/icerik'ten alır.
   VAPID anahtar çifti ilk kullanımda üretilir ve D1'deki "ayar" tablosunda saklanır (elle kurulum gerekmez). */
const PUSH_HOST = /^(fcm\.googleapis\.com|updates\.push\.services\.mozilla\.com|[a-z0-9-]+\.push\.apple\.com|[a-z0-9-]+\.notify\.windows\.com)$/;
const ALL = "Tüm şarj istasyonları";
const TUR_BASI = 35;          // ücretsiz planda çağrı başına 50 dış istek sınırı var; her çalışmada en çok bu kadar bildirim
const ABONE_SINIRI = 50000;
const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
let tabloHazir = false;
async function bildirimTablo(env) {
  if (tabloHazir) return;
  await env.DB.batch([
    env.DB.prepare("CREATE TABLE IF NOT EXISTS abone (id INTEGER PRIMARY KEY, endpoint TEXT UNIQUE NOT NULL, profil TEXT NOT NULL, kayit TEXT NOT NULL, son_gun TEXT, bakildi TEXT, bekleyen TEXT)"),
    env.DB.prepare("CREATE TABLE IF NOT EXISTS gonderim (abone_id INTEGER NOT NULL, kampanya TEXT NOT NULL, gun TEXT NOT NULL, PRIMARY KEY (abone_id, kampanya))"),
    env.DB.prepare("CREATE TABLE IF NOT EXISTS ayar (ad TEXT PRIMARY KEY, deger TEXT NOT NULL)"),
  ]);
  tabloHazir = true;
}
async function vapid(env) {
  let r = await env.DB.prepare("SELECT deger FROM ayar WHERE ad = 'vapid'").first();
  if (!r) {
    const k = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
    const deger = JSON.stringify({ ozel: await crypto.subtle.exportKey("jwk", k.privateKey), acik: b64u(await crypto.subtle.exportKey("raw", k.publicKey)) });
    await env.DB.prepare("INSERT OR IGNORE INTO ayar (ad, deger) VALUES ('vapid', ?)").bind(deger).run();
    r = await env.DB.prepare("SELECT deger FROM ayar WHERE ad = 'vapid'").first();
  }
  return JSON.parse(r.deger);
}
const endpointGecerli = u => { try { const x = new URL(u); return x.protocol === "https:" && PUSH_HOST.test(x.hostname) && u.length < 1000; } catch { return false; } };
const liste = (v, n) => (Array.isArray(v) ? v : []).filter(x => typeof x === "string").map(x => temiz(x, 40)).filter(Boolean).slice(0, n);
async function bildirim(request, url, env) {
  await bildirimTablo(env);
  const yol = url.pathname.slice("/api/bildirim/".length);
  if (yol === "anahtar") return json({ ok: true, anahtar: (await vapid(env)).acik });
  if (request.method !== "POST") return json({ ok: false }, 405);
  let b;
  try { b = await govde(request, 6000); } catch { return json({ ok: false, hata: "geçersiz" }, 400); }
  const endpoint = String((b.abonelik && b.abonelik.endpoint) || b.endpoint || "");
  if (!endpointGecerli(endpoint)) return json({ ok: false, hata: "abonelik" }, 400);
  if (yol === "cik") { await env.DB.prepare("DELETE FROM gonderim WHERE abone_id IN (SELECT id FROM abone WHERE endpoint = ?)").bind(endpoint).run(); await env.DB.prepare("DELETE FROM abone WHERE endpoint = ?").bind(endpoint).run(); return json({ ok: true }); }
  if (yol === "icerik") {
    const r = await env.DB.prepare("SELECT bekleyen FROM abone WHERE endpoint = ?").bind(endpoint).first();
    let d = null; try { d = r && r.bekleyen ? JSON.parse(r.bekleyen) : null; } catch {}
    return json(d ? { ok: true, ...d } : { ok: false });
  }
  if (yol === "abone") {
    const p = b.profil || {};
    const profil = JSON.stringify({ banka: liste(p.banka, 30), ag: liste(p.ag, 40), arac: temiz(p.arac, 30), il: temiz(p.il, 30) });
    const say = await env.DB.prepare("SELECT COUNT(*) AS n FROM abone").first();
    if (say && say.n >= ABONE_SINIRI) return json({ ok: false, hata: "dolu" }, 503);
    await env.DB.prepare("INSERT INTO abone (endpoint, profil, kayit) VALUES (?, ?, ?) ON CONFLICT (endpoint) DO UPDATE SET profil = excluded.profil")
      .bind(endpoint, profil, gunTR()).run();
    return json({ ok: true });
  }
  return json({ ok: false }, 404);
}

// Kampanya verisini sitedeki kampanyalar.json'dan okur ve düz listeye çevirir (sitedeki flatten() ile aynı mantık)
async function kampanyalar(env) {
  const r = await env.ASSETS.fetch(new Request(`https://${ANA}/kampanyalar.json`));
  if (!r.ok) throw new Error("kampanyalar.json " + r.status);
  const d = await r.json(), bugun = gunTR(), out = [];
  for (const b of d.bankalar || []) for (const o of b.offers || []) out.push({ ...o, kid: b.id, kurum: b.name, tip: "banka", st: o.st || [] });
  for (const s of d.istasyonlar || []) for (const o of s.own || []) out.push({ ...o, kid: s.id, kurum: s.name, tip: "ag", st: [s.name] });
  return out.filter(c => (!c.bit || c.bit >= bugun) && c.link && !c.kontrol)
    .map(c => ({ ...c, anahtar: temiz(`${c.kid}|${c.big}|${c.bas || ""}`, 120), tarih: c.eklendi || c.bas || "" }));
}
// Kampanya bu profile uyuyor mu? Yalnızca kişinin açıkça seçtiği kart / ağ / araçla ilgili kampanyalar bildirilir.
function uyar(c, p) {
  const arac = Array.isArray(c.arac) && c.arac.length, iller = Array.isArray(c.iller) && c.iller.length;
  if (arac && !c.arac.includes(p.arac)) return false;
  if (iller && !c.iller.includes(p.il)) return false;
  if (c.tip === "banka") return p.banka.includes(c.kid) && (!p.ag.length || c.st.includes(ALL) || c.st.some(s => p.ag.includes(s)));
  return p.ag.includes(c.kurum) || !!arac;
}
async function vapidBaslik(v, endpoint) {
  const anahtar = await crypto.subtle.importKey("jwk", v.ozel, { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const parca = o => b64u(enc.encode(JSON.stringify(o)));
  const govde = parca({ typ: "JWT", alg: "ES256" }) + "." + parca({ aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 12 * 3600, sub: `https://${ANA}` });
  const imza = await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, anahtar, enc.encode(govde));
  return `vapid t=${govde}.${b64u(imza)}, k=${v.acik}`;
}
async function bildirimGonder(env, gonder = fetch) {
  await bildirimTablo(env);
  const gun = gunTR();
  const aboneler = (await env.DB.prepare("SELECT id, endpoint, profil, kayit FROM abone WHERE (son_gun IS NULL OR son_gun < ?1) AND (bakildi IS NULL OR bakildi < ?1) ORDER BY id LIMIT ?2").bind(gun, TUR_BASI).all()).results;
  if (!aboneler.length) return { bakilan: 0, giden: 0 };
  const C = await kampanyalar(env), v = await vapid(env);
  const gitmis = new Map();
  const g = await env.DB.prepare(`SELECT abone_id, kampanya FROM gonderim WHERE abone_id IN (${aboneler.map(() => "?").join(",")})`).bind(...aboneler.map(a => a.id)).all();
  for (const x of g.results) (gitmis.get(x.abone_id) || gitmis.set(x.abone_id, new Set()).get(x.abone_id)).add(x.kampanya);
  const islemler = []; let giden = 0;
  for (const a of aboneler) {
    let p; try { p = JSON.parse(a.profil); } catch { p = null; }
    p = { banka: [], ag: [], arac: "", il: "", ...(p || {}) };
    const eski = gitmis.get(a.id) || new Set();
    // abonelikten sonra eklenen, daha önce bildirilmemiş, profile uyan kampanyalardan en eskisi
    const c = C.filter(k => k.tarih && k.tarih >= a.kayit && !eski.has(k.anahtar) && uyar(k, p)).sort((x, y) => x.tarih.localeCompare(y.tarih))[0];
    if (!c) { islemler.push(env.DB.prepare("UPDATE abone SET bakildi = ? WHERE id = ?").bind(gun, a.id)); continue; }
    let durum = 0;
    try { durum = (await gonder(a.endpoint, { method: "POST", headers: { authorization: await vapidBaslik(v, a.endpoint), ttl: "86400", urgency: "normal", "content-length": "0" } })).status; } catch {}
    if (durum === 404 || durum === 410) { // abonelik iptal edilmiş
      islemler.push(env.DB.prepare("DELETE FROM gonderim WHERE abone_id = ?").bind(a.id), env.DB.prepare("DELETE FROM abone WHERE id = ?").bind(a.id));
    } else if (durum >= 200 && durum < 300) {
      giden++;
      const icerik = JSON.stringify({ baslik: temiz(`${c.kurum}: ${c.big}`, 80), metin: temiz(c.det, 140), url: "./#g=kamp&bana=1" });
      islemler.push(env.DB.prepare("INSERT OR IGNORE INTO gonderim (abone_id, kampanya, gun) VALUES (?, ?, ?)").bind(a.id, c.anahtar, gun),
        env.DB.prepare("UPDATE abone SET son_gun = ?1, bakildi = ?1, bekleyen = ?2 WHERE id = ?3").bind(gun, icerik, a.id));
    } // başka hata: dokunma, sonraki çalışmada yeniden denenir
  }
  if (islemler.length) await env.DB.batch(islemler);
  return { bakilan: aboneler.length, giden };
}

export default {
  async scheduled(olayi, env, ctx) {
    if (env.DB) ctx.waitUntil(bildirimGonder(env).catch(() => {}));
  },
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
        if (url.pathname.startsWith("/api/bildirim/")) return await bildirim(request, url, env);
      } catch {
        return json({ ok: false, hata: "sunucu" }, 500);
      }
      return json({ ok: false }, 404);
    }
    return env.ASSETS.fetch(request);
  },
};
