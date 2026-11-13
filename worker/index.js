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
//   GET  /api/durum/bigstation?c=95,96 → BIG Station cihazlarının anlık boş / şarjda durumu (aşağıda "Anlık durum")
//   GET  /api/durum/acropol?c=59,60   → Acropol Şarj soketlerinin anlık boş / şarjda durumu (aynı bölüm)
//   GET  /api/durum/<ağ>?c=…          → neva, lumicle, ecojet (electroop OCPI) ve solinved için aynısı (aynı bölüm)
//   GET  /api/durum/epsis?c=183,97    → EPSIS lokasyonlarının boş / dolu / toplam soket sayısı (aynı bölüm)
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

/* ---------- Anlık durum: BIG Station, Acropol Şarj, electroop OCPI ağları, Solinved ----------
   GET /api/durum/bigstation?c=95,96,97  → {ok, zaman, cihazlar: {"95": "bos" | "sarj" | "bilinmiyor", …}}
   GET /api/durum/acropol?c=59,60        → aynı biçim; kimlikler Acropol soket kimlikleri
   GET /api/durum/neva|lumicle|ecojet?c=L231,L230 → aynı biçim; kimlikler OCPI lokasyon kimlikleri (her lokasyon bir ünite)
   GET /api/durum/epsis?c=183,97         → {ok, zaman, guncel, cihazlar: {"183": {bos, dolu, toplam} | "bilinmiyor", …}}; kimlikler EPSIS
                                           lokasyon (istasyon) kimlikleri, sayılar soket sayısı
   GET /api/durum/solinved?c=28656       → aynı biçim; kimlikler Solinved soket (connector) kimlikleri
   Ağ yalnızca DURUM_AGLAR'daki izinli listeden seçilir; her ağın kimlik biçimi ve istek başına en çok kimlik sayısı ayrıdır.
   Ortak kurallar (her ağ için ayrı önbellek girdisi):
   - Bu uç noktaların tek kullanıcısı sitedir ve yalnızca biri haritada o ağın istasyon detayını açınca çağrılır.
     Zamanlanmış görev ya da arka planda yoklama yoktur.
   - Kaynak yanıtı GELİR GELMEZ kimlik başına tek duruma ("sarj" | "bos" | "bilinmiyor") indirgenir; diğer alanlar (ölçümler,
     şarj yüzdesi, oturum sahibi adı / plakası vb.) hiçbir yerde saklanmaz, loglanmaz, döndürülmez.
   - İndirgenmiş liste Cache API'de (her Cloudflare konumunda ayrı) DURUM_SN saniye tutulur: kullanıcı sayısından bağımsız olarak
     konum başına dakikada en çok bir yenileme. Önbellek süresi dolduğu anda aynı konumda eşzamanlı gelen birkaç istek ayrı ayrı
     yenileyebilir; Workers'ta istekler arası ortak Promise beklemek (başka isteğin G/Ç'si) güvenli olmadığından birleştirme
     yapılmaz, bu kısa pencere dışında yük değişmez. Yenileme başarısızsa DURUM_HATA_SN saniye yeniden denenmez (servis
     çöktüğünde üstüne istek yağmasın). Yenileme toplamda DURUM_SURE_MS içinde bitmezse kesilir.
   BIG Station: kaynak, BIG Station'ın kendi sistemini okuyan, giriş gerektirmeyen üçüncü taraf salt okunur servisin halka açık
     listesi (GET /api/stations, 100'erli sayfalar; yenileme başına ≈4 istek). O servisin başka hiçbir adresi çağrılmaz.
     liveStatus "offline" (ya da bilinmeyen) → "bilinmiyor"; bağlı (wifionline / gsmonline) ve status "active" → "sarj";
     bağlı ve "passive" → "bos". Ücretsiz plan: çağrı başına 50 dış istek sınırı; en çok 1 önbellek okuma + DURUM_SAYFA sayfa + 1 yazma.
   Acropol Şarj: kaynak, ağın kendi haritasının (acropolsarj.com/evsarjharitasi.aspx) kullandığı giriş gerektirmeyen tek liste
     (getAllAndFilteredStations, ≈150 KB, tüm istasyonlar tek istekte; yenileme başına 1 istek). Soket durumu (OCPP):
     Available → "bos"; Preparing / Charging / SuspendedEV / SuspendedEVSE / Finishing → "sarj" (soket dolu);
     Closed (çevrimdışı), Faulted, Unavailable, Reserved ve bilinmeyenler → "bilinmiyor".
   Neva Şarj, Lumicle, Ecojet: kaynak, ağların haritasının (electroop.io/chargestations/index?company=<ağ>) kullandığı giriş
     gerektirmeyen OCPI 2.2 "locations" listesi (<ağ>.mapcontentpartners.service.electroop.io/2.2/locations). Tek lokasyon ucu
     (/locations/{id}) yok (404) ve sayfalama parametreleri yok sayılıyor: yenileme başına tüm liste, 1 istek (50–650 KB; sıkıştırılmış
     5–60 KB). CPU sınırı için JSON.parse yapılmaz: metin yalnızca '{"id":"…","country_code"' (lokasyon başı) ve
     '"evse_id":"…","status":"…"' (EVSE durumu) kalıplarıyla taranır; başka alan okunmaz. Biçim değişirse sonuç boş çıkar → hata.
     OCPI 2.2 EVSE durumu: AVAILABLE → "bos"; CHARGING ve BLOCKED (soketin önü/park yeri dolu) → "sarj"; RESERVED, OUTOFORDER,
     INOPERATIVE, PLANNED, REMOVED, UNKNOWN ve bilinmeyenler → "bilinmiyor" (Acropol'deki Reserved gibi).
     Otopriz aynı platformda ama listesi 1,2 MB: metne çevirip taramak ≈10–15 ms CPU (ücretsiz plan sınırı 10 ms); eklenmedi.
     EPSIS de electroop'taydı; electroop Cloudflare'e 403 verdiği için EPSIS artık kendi haritasının ucundan (aşağıda) okunur.
   EPSIS: kaynak, ağın kendi haritasının (www.epsis.net/lokasyonlar) kullandığı https://www.epsis.net/api/public/locations?lang=tr
     (GeoJSON, ≈100 KB, tüm istasyonlar tek istekte; yenileme başına 1 istek). EPSIS telefonda izin verdi (14 Kasım 2026): 'siteden
     alabilirsiniz, kaynaklarımız açık'. robots.txt /api/ yasağı bu izinle aşılıyor; yalnızca /api/public/locations kullanılır (başka
     /api/ yolu çağrılmaz). Alanlar (EPSIS'in map.js / map-shared.js kodundan): properties.id lokasyon kimliği, aa/ad müsait AC/DC
     soket, ta/td toplam AC/DC soket, bb dolu (şarjda / bloke / rezerve) soket, st lokasyon durumu (m bakımda, p yakında). Yalnızca
     bunlar okunur: boş = aa+ad, dolu = bb, toplam = ta+td; kalan (arızalı, çevrimdışı, bilinmeyen) sitede "durumu bilinmiyor" olur.
     EPSIS sunucusu sayıları kendi kaynağından (electroop) yeniler; meta.updated_at son yenileme, meta.stale yenilemenin aksadığını
     bildirir. meta.stale true ise ya da meta.updated_at EPSIS_TAZE_DK dakikadan eskiyse (veya okunamıyorsa) tüm kimlikler
     "bilinmiyor" döner: bayat sayı gösterilmez. Bayatlık her istekte önbellekteki "guncel" ile yeniden hesaplanır.
   Solinved: kaynak, ağın haritası (solinvedcharge.com) olan Doldur CPMS kiracı sayfası (GetChargePointLocationsMap?tenantCode=SOL,
     ≈55 KB HTML; yenileme başına 1 istek). Sayfadaki chargePointsData dizisinden yalnızca soket kimliği ve lastStatus (OCPP) okunur;
     eşleme Acropol ile aynı. */
const DURUM_SN = 60, DURUM_HATA_SN = 30, DURUM_SURE_MS = 6000, DURUM_SAYFA = 10, DURUM_EN_COK = 20;
const DURUM_UA = "WattKac/1.0 (+https://wattkac.com; anlik durum)";
const DURUM_BASLIK = { "user-agent": DURUM_UA, accept: "application/json" };
const BIG_URL = "https://bsx-reverse.ee-w.workers.dev/api/stations?offset={o}&limit=100";
const BAGLI = new Set(["wifionline", "gsmonline"]);
const ACROPOL_URL = "https://ipi8yuvwgw.eu-central-1.awsapprunner.com/api/getAllAndFilteredStations";
const ACROPOL_DOLU = new Set(["preparing", "charging", "suspendedev", "suspendedevse", "finishing"]);
const OCPI_URL = "https://{}.mapcontentpartners.service.electroop.io/2.2/locations";
const OCPI_DURUM = { AVAILABLE: "bos", CHARGING: "sarj", BLOCKED: "sarj" };
const OCPI_KALIP = /\{"id":"([A-Za-z0-9][A-Za-z0-9_-]{0,39})","country_code"|"evse_id":"[^"]{0,80}","status":"([A-Z_]{1,20})"/g;
const SOL_URL = "https://cpms-api.doldurapp.com/ChargePoint/GetChargePointLocationsMap?tenantCode=SOL";
// EPSIS telefonda izin verdi (14 Kasım 2026): 'siteden alabilirsiniz, kaynaklarımız açık'. robots.txt /api/ yasağı bu izinle
// aşılıyor; yalnızca /api/public/locations kullanılır.
const EPSIS_URL = "https://www.epsis.net/api/public/locations?lang=tr";
const EPSIS_TAZE_DK = 15;

// BIG Station: tek cihaz kaydı → durum (yalnızca status ve liveStatus okunur)
function cihazDurumu(x) {
  if (!BAGLI.has(x.liveStatus)) return "bilinmiyor";
  return x.status === "active" ? "sarj" : x.status === "passive" ? "bos" : "bilinmiyor";
}
// OCPP soket durumu → durum (Acropol status, Solinved lastStatus)
function ocppDurumu(v) {
  const st = typeof v === "string" ? v.toLowerCase() : "";
  return st === "available" ? "bos" : ACROPOL_DOLU.has(st) ? "sarj" : "bilinmiyor";
}
// Acropol: tek soket kaydı → durum (yalnızca status okunur)
const soketDurumu = x => ocppDurumu(x.status);
const kimlikGecerli = id => /^\d{1,9}$/.test(id);
const ocpiKimlik = id => /^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/.test(id);
// Kayıtları indirgenmiş haritaya ekler (BIG sayfalaması sabit sıralı değil: aynı kimlik iki kez gelirse ilki kalır)
function durumEkle(harita, liste, durumu = cihazDurumu) {
  for (const x of liste) {
    if (!x || typeof x !== "object") continue;
    const id = String(x.id ?? "");
    if (kimlikGecerli(id) && !(id in harita)) harita[id] = durumu(x);
  }
}
async function bigCek(getir, signal) {
  const harita = {};
  for (let sayfa = 0; sayfa < DURUM_SAYFA; sayfa++) {
    const r = await getir(BIG_URL.replace("{o}", String(sayfa * 100)), { headers: DURUM_BASLIK, signal });
    if (!r.ok) throw new Error("durum " + r.status);
    let liste = (await r.json()).stations;   // ham yanıt yalnızca bu blokta yaşar
    if (!Array.isArray(liste)) throw new Error("durum biçim");
    const n = liste.length;
    durumEkle(harita, liste); liste = null;
    if (n < 100) return harita;
  }
  throw new Error("durum sayfa");
}
async function acropolCek(getir, signal) {
  const r = await getir(ACROPOL_URL, { headers: DURUM_BASLIK, signal });
  if (!r.ok) throw new Error("durum " + r.status);
  let liste = (await r.json()).data;   // ham yanıt yalnızca bu blokta yaşar
  if (!Array.isArray(liste)) throw new Error("durum biçim");
  const harita = {};
  for (const ist of liste) {
    for (const u of (ist && Array.isArray(ist.unites) ? ist.unites : [])) {
      if (u && Array.isArray(u.sockets)) durumEkle(harita, u.sockets, soketDurumu);
    }
  }
  liste = null;
  if (!Object.keys(harita).length) throw new Error("durum boş");
  return harita;
}
// electroop OCPI: metin taranır (yukarıda); lokasyon kimliği → ilk EVSE'nin durumu. Ham metin yalnızca bu blokta yaşar.
async function ocpiCek(sirket, getir, signal) {
  const r = await getir(OCPI_URL.replace("{}", sirket), { headers: DURUM_BASLIK, signal });
  if (!r.ok) throw new Error("durum " + r.status);
  let t = await r.text();
  const harita = Object.create(null), kalip = new RegExp(OCPI_KALIP);
  let id = null;
  for (let m; (m = kalip.exec(t));) {
    if (m[1] !== undefined) id = m[1];
    else if (id !== null) { if (!(id in harita)) harita[id] = OCPI_DURUM[m[2]] || "bilinmiyor"; id = null; }
  }
  t = null;
  if (!Object.keys(harita).length) throw new Error("durum boş");
  return { ...harita };
}
// Solinved: sayfadaki chargePointsData → soket kimliği → durum (yalnızca connectors[].id ve lastStatus okunur)
async function solCek(getir, signal) {
  const r = await getir(SOL_URL, { headers: { ...DURUM_BASLIK, accept: "text/html" }, signal });
  if (!r.ok) throw new Error("durum " + r.status);
  let t = await r.text();
  const m = /const\s+chargePointsData\s*=\s*'(.*?)';/s.exec(t);
  t = null;
  if (!m) throw new Error("durum biçim");
  let liste = JSON.parse(m[1]);   // ham dizi yalnızca bu blokta yaşar
  if (!Array.isArray(liste)) throw new Error("durum biçim");
  const harita = {};
  for (const s of liste) {
    for (const u of (s && Array.isArray(s.chargeUnits) ? s.chargeUnits : [])) {
      for (const c of (u && Array.isArray(u.connectors) ? u.connectors : [])) {
        const id = String(c && c.id != null ? c.id : "");
        if (kimlikGecerli(id) && !(id in harita)) harita[id] = ocppDurumu(c.lastStatus);
      }
    }
  }
  liste = null;
  if (!Object.keys(harita).length) throw new Error("durum boş");
  return harita;
}
// EPSIS: lokasyon kimliği → {bos, dolu, toplam} (yalnızca id, aa, ad, ta, td, bb, st okunur) + meta güncelliği.
// Ham yanıt yalnızca bu blokta yaşar.
const sayi = v => (Number.isInteger(v) && v >= 0 && v <= 999 ? v : null);
async function epsisCek(getir, signal) {
  const r = await getir(EPSIS_URL, { headers: DURUM_BASLIK, signal });
  if (!r.ok) throw new Error("durum " + r.status);
  let j = await r.json();
  const liste = j && j.data && j.data.features, meta = (j && j.meta) || {};
  if (!Array.isArray(liste)) throw new Error("durum biçim");
  const harita = {};
  for (const f of liste) {
    const p = f && f.properties;
    if (!p || typeof p !== "object") continue;
    const id = String(p.id ?? "");
    if (!kimlikGecerli(id) || id in harita) continue;
    const aa = sayi(p.aa), ad = sayi(p.ad), ta = sayi(p.ta), td = sayi(p.td), bb = sayi(p.bb);
    if (p.st === "m" || p.st === "p" || [aa, ad, ta, td, bb].includes(null) || aa > ta || ad > td || aa + ad + bb > ta + td || !(ta + td)) {
      harita[id] = "bilinmiyor"; continue;
    }
    harita[id] = { bos: aa + ad, dolu: bb, toplam: ta + td };
  }
  const guncel = meta.stale === false && typeof meta.updated_at === "string" && meta.updated_at.length <= 40 ? meta.updated_at : null;
  j = null;
  if (!Object.keys(harita).length) throw new Error("durum boş");
  return { c: harita, guncel };
}
// EPSIS verisi taze mi (meta.stale false ve updated_at son EPSIS_TAZE_DK dakika içinde; saat farkı için 2 dk ileriye izin)
function epsisTaze(guncel, simdi = Date.now()) {
  const t = typeof guncel === "string" ? Date.parse(guncel) : NaN;
  return Number.isFinite(t) && simdi - t <= EPSIS_TAZE_DK * 60000 && t - simdi <= 120000;
}
const ocpiAg = sirket => ({ anahtar: `https://wattkac.com/__durum/${sirket}`, cek: (g, s) => ocpiCek(sirket, g, s), kimlik: ocpiKimlik, enCok: 40 });
// İzinli ağlar. kimlik: kimlik biçimi (yoksa 1–9 haneli sayı), enCok: istek başına en çok kimlik (yoksa DURUM_EN_COK)
const DURUM_AGLAR = {
  bigstation: { anahtar: "https://wattkac.com/__durum/bigstation", cek: bigCek },
  acropol: { anahtar: "https://wattkac.com/__durum/acropol", cek: acropolCek },
  neva: ocpiAg("nevasarj"),
  // EPSIS: kendi haritasının ucu (electroop'taki eski "epsis" girdisinin yerine); guncellik: meta güncelliği denetlenir
  epsis: { anahtar: "https://wattkac.com/__durum/epsis", cek: epsisCek, guncellik: true },
  lumicle: ocpiAg("lumicle"),
  ecojet: ocpiAg("ecojet"),
  solinved: { anahtar: "https://wattkac.com/__durum/solinved", cek: solCek },
};
async function durumCek(ag, getir) {
  const ac = new AbortController(), zam = setTimeout(() => ac.abort(), DURUM_SURE_MS);
  try {
    const a = DURUM_AGLAR[ag], c = await a.cek(getir, ac.signal);
    return a.guncellik ? { zaman: new Date().toISOString(), c: c.c, guncel: c.guncel } : { zaman: new Date().toISOString(), c };
  }
  finally { clearTimeout(zam); }
}
const durumYanit = (o, sn) => new Response(JSON.stringify(o), { headers: { "content-type": "application/json", "cache-control": `max-age=${sn}` } });
async function durumAnlik(ag, ctx, getir) {
  const onb = typeof caches !== "undefined" && caches.default, anahtar = DURUM_AGLAR[ag].anahtar;
  if (onb) {
    try {
      const h = await onb.match(anahtar);
      if (h) {
        const d = await h.json(), yas = Date.now() - Date.parse(d.zaman);
        if (yas >= 0 && yas < (d.hata ? DURUM_HATA_SN : DURUM_SN) * 1000) return d;
      }
    } catch {}
  }
  let d;
  try { d = await durumCek(ag, getir); } catch (e) {
    // neden yalnızca bizim kısa iletimiz (ör. "durum 403", "durum boş", AbortError); kaynak yanıtından metin taşınmaz
    const m = String(e && e.message || e && e.name || "");
    d = { zaman: new Date().toISOString(), hata: 1, neden: /^(durum [0-9a-zçğıöşü ]{1,12}|AbortError|TypeError)$/i.test(m) ? m : "diğer" };
  }
  if (onb) {
    const yaz = onb.put(anahtar, durumYanit(d, d.hata ? DURUM_HATA_SN : DURUM_SN)).catch(() => {});
    if (ctx && ctx.waitUntil) ctx.waitUntil(yaz); else await yaz;
  }
  return d;
}
async function durumIstek(ag, request, url, ctx, getir = fetch) {
  if (request.method !== "GET") return json({ ok: false }, 405);
  const a = DURUM_AGLAR[ag], gecerli = a.kimlik || kimlikGecerli, enCok = a.enCok || DURUM_EN_COK;
  const ham = String(url.searchParams.get("c") || "");
  const ids = [...new Set(ham.split(","))];
  if (!ham || ham.length > (a.kimlik ? enCok * 41 : 220) || ids.length > enCok || !ids.every(gecerli)) return json({ ok: false, hata: "c" }, 400);
  let d;
  try { d = await durumAnlik(ag, ctx, getir); } catch { d = { hata: 1 }; }
  if (d.hata || !d.c) return json({ ok: false, neden: d.neden || "diğer" }, 503);
  const cihazlar = {}, bayat = a.guncellik && !epsisTaze(d.guncel);   // bayat veri: tüm kimlikler "bilinmiyor"
  for (const id of ids) cihazlar[id] = !bayat && Object.prototype.hasOwnProperty.call(d.c, id) ? d.c[id] : "bilinmiyor";
  const o = a.guncellik ? { ok: true, zaman: d.zaman, guncel: d.guncel || null, cihazlar } : { ok: true, zaman: d.zaman, cihazlar };
  return json(o, 200, { "cache-control": "public, max-age=60" });
}

export default {
  async scheduled(olayi, env, ctx) {
    if (env.DB) ctx.waitUntil(bildirimGonder(env).catch(() => {}));
  },
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (YONLENDIR.has(url.hostname)) {
      url.protocol = "https:";
      url.hostname = ANA;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    const durumAg = /^\/api\/durum\/([a-z]{1,20})$/.exec(url.pathname);
    if (durumAg && Object.prototype.hasOwnProperty.call(DURUM_AGLAR, durumAg[1])) {   // veritabanı gerektirmez
      try { return await durumIstek(durumAg[1], request, url, ctx); } catch { return json({ ok: false }, 503); }
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
