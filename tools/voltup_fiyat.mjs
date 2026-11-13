#!/usr/bin/env node
// VoltUp'ın istasyon bazlı fiyat listesini okur ve data/aglar/voltup_fiyat.json olarak kaydeder.
//
// Kaynak: VoltUp'ın kendi sitesindeki (https://voltup.com.tr/#istasyonlar) "Şarj Tarifeleri" bölümünün gömdüğü sayfa
//   https://voltup.petroo.dev/price-list/true/true
// Bu sayfa bir Blazor Server uygulamasıdır: liste düz HTML'de yoktur, tarayıcıda SignalR bağlantısıyla çizilir ve ayrıca
// herkese açık bir JSON adresi yoktur. Bu yüzden sayfa, herhangi bir ziyaretçinin tarayıcısı gibi bir kez açılır ve ekrandaki
// kartlar okunur. Giriş, anahtar ya da oturum kullanılmaz. Günde tek sayfa yüklemesi yapılır.
//
// Çalıştırma: node tools/voltup_fiyat.mjs   (playwright paketi ve chromium kurulu olmalı)
// Okunamazsa ya da liste beklenenden kısaysa dosyaya dokunulmaz (önceki fiyatlar korunur) ve çıkış kodu 1 olur.
import { createRequire } from "node:module";
import { writeFileSync, mkdirSync } from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const URL = "https://voltup.petroo.dev/price-list/true/true";
const SAYFA = "https://voltup.com.tr/#istasyonlar";
const OUT = "data/aglar/voltup_fiyat.json";
const UA = "WattKac/1.0 (+https://wattkac.com; gunluk istasyon listesi)";
const EN_AZ = 20;

// "12,49 ₺ / kWs" → 12.49 ; "- / kWs" → null
const fiyat = s => {
  const m = /(\d+(?:[.,]\d+)?)\s*₺/.exec(s || "");
  const v = m ? parseFloat(m[1].replace(",", ".")) : null;
  return v && v > 0 && v < 100 ? v : null;
};

const browser = await chromium.launch();
let kartlar = [], aktif = null;
try {
  const page = await browser.newPage({ userAgent: UA, locale: "tr-TR" });
  // Görsel, yazı tipi ve analitik istekleri gereksiz: yalnızca sayfanın kendisi ve uygulama dosyaları yüklenir
  await page.route("**/*", r => (["image", "font", "media"].includes(r.request().resourceType()) || /google|gstatic|fontawesome|epaykolay|freeipapi/.test(r.request().url()) ? r.abort() : r.continue()));
  await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForSelector("article.location-price-card", { timeout: 60000 });
  // Liste parça parça çizilebilir: kart sayısı 3 sn boyunca değişmeyene kadar bekle
  let onceki = -1;
  for (let i = 0; i < 20; i++) {
    const n = await page.locator("article.location-price-card").count();
    if (n === onceki) break;
    onceki = n;
    await page.waitForTimeout(3000);
  }
  aktif = await page.evaluate(() => {
    const m = [...document.querySelectorAll(".price-list-metric")].find(e => /aktif/i.test(e.innerText));
    return m ? parseInt(m.querySelector("strong")?.innerText, 10) || null : null;
  });
  kartlar = await page.evaluate(() => [...document.querySelectorAll("article.location-price-card")].map(k => {
    const t = s => (k.querySelector(s)?.innerText || "").replace(/\s+/g, " ").trim();
    const chip = {};
    k.querySelectorAll(".location-price-chip").forEach(c => { chip[(c.querySelector("span")?.innerText || "").trim().toUpperCase()] = (c.querySelector("strong")?.innerText || "").trim(); });
    return { n: t(".location-price-title"), ad: t(".location-price-address"), ac: chip.AC || "", dc: chip.DC || "" };
  }));
} catch (e) {
  console.error("voltup fiyat: sayfa okunamadı:", e.message);
} finally {
  await browser.close();
}

const ist = kartlar.filter(k => k.n).map(k => ({ n: k.n, ad: k.ad, ac: fiyat(k.ac), dc: fiyat(k.dc) }));
if (ist.length < EN_AZ || !ist.some(k => k.ac || k.dc)) {
  console.error(`voltup fiyat: BAŞARISIZ (yalnızca ${ist.length} istasyon; beklenen ≥${EN_AZ}); önceki dosya korunuyor`);
  process.exit(1);
}
if (aktif && aktif !== ist.length) console.error(`voltup fiyat: uyarı, sayfa ${aktif} aktif lokasyon diyor, okunan ${ist.length}`);
ist.sort((a, b) => a.n.localeCompare(b.n, "tr"));
mkdirSync("data/aglar", { recursive: true });
const bugun = new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10);
writeFileSync(OUT, JSON.stringify({ kaynak: URL, sayfa: SAYFA, cekildi: bugun, sayi: ist.length, istasyonlar: ist }));
console.log(`voltup fiyat: ${ist.length} istasyon (AC fiyatlı ${ist.filter(k => k.ac).length}, DC fiyatlı ${ist.filter(k => k.dc).length})`);
