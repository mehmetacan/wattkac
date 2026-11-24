// otoWATT seçili 45 istasyonda %25 indirim (25 Kasım – 24 Aralık 2026): kapak + 3 liste sayfası + hikâye, beyaz tema.
// Kullanım: node tools/ozel/otowatt_2026_11.mjs <klasör>   (klasörde liste.json: [[il, [[ad, ilçe], …]], …])
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");

const dir = process.argv[2];
const KOK = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const liste = JSON.parse(fs.readFileSync(path.join(dir, "liste.json"), "utf8"));
const LOGO = "data:image/svg+xml;base64," + fs.readFileSync(path.join(KOK, "tools/ozel/logolar/otowatt.svg")).toString("base64");
const toplam = liste.reduce((n, [, v]) => n + v.length, 0), ilSay = liste.length;

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=block');
*{box-sizing:border-box;margin:0;padding:0}html,body{overflow:hidden;font-family:'Plus Jakarta Sans',sans-serif;color:#0F1B3D;background:#fff}
.s{position:relative;overflow:hidden;padding:58px 60px 0;background:radial-gradient(700px 420px at 100% 0,rgba(255,212,0,.16),transparent 70%),radial-gradient(600px 420px at 0 100%,rgba(14,116,144,.07),transparent 70%),#fff}
.ust{display:flex;align-items:center;justify-content:space-between}
.wk{display:flex;align-items:center;gap:6px;font-size:34px;font-weight:800;letter-spacing:-.5px}.wk b{color:#E5A800}
.ow{height:44px}
.chip{display:inline-block;font-weight:800;background:#0F1B3D;color:#fff;border-radius:999px}
.vur{background:#FFD400;border-radius:22px;display:inline-block;font-weight:800}
.alt{position:absolute;left:60px;right:60px;bottom:44px;font-size:16px;color:#7A869C;line-height:1.45}
.alt b{color:#0F1B3D}
.mad{display:flex;gap:14px;align-items:flex-start;font-size:26px;line-height:1.35;color:#334155;margin-top:16px}
.mad i{flex:none;width:34px;height:34px;border-radius:50%;background:#E6F4EA;color:#047857;font-style:normal;font-weight:800;display:flex;align-items:center;justify-content:center;font-size:20px;margin-top:2px}
.mad b{color:#0F1B3D}
.il{display:flex;align-items:baseline;gap:12px;margin-top:26px;padding-bottom:8px;border-bottom:3px solid #0F1B3D}
.il h2{font-size:34px;font-weight:800;letter-spacing:-.5px}.il span{font-size:20px;font-weight:700;color:#0E7490}
.izgara{display:grid;grid-template-columns:1fr 1fr;column-gap:30px}
.ist{padding:11px 0;border-bottom:2px solid #EEF1F6}
.ist b{display:block;font-size:22px;font-weight:800;line-height:1.2}.ist small{display:block;font-size:17px;color:#5B6680;font-weight:600;margin-top:2px}`;

const UST = `<div class="ust"><div class="wk"><svg viewBox="0 0 24 24" width="38" height="38"><path d="M13.5 2 4 13.5h6.2L9.5 22 20 9.8h-6.4z" fill="#E5A800"/></svg><span>Watt<b>Kaç</b></span></div><img class="ow" src="${LOGO}" alt="otoWATT"></div>`;
const ALT = `<div class="alt">Kaynak: otowatt.com.tr kampanya duyurusu · 24 Kasım 2026 itibarıyla. Koşullar değişebilir; <b>şarjdan önce otoWATT uygulamasından kontrol edin.</b> Reklam veya iş birliği değildir. @wattkac</div>`;

const kapak = (hikaye) => `<div class="s" style="width:1080px;height:${hikaye ? 1920 : 1350}px;${hikaye ? "padding-top:190px" : ""}">${UST}
  <div style="margin-top:${hikaye ? 120 : 64}px"><span class="chip" style="font-size:30px;padding:10px 26px">25 Kasım – 24 Aralık</span></div>
  <div style="font-size:54px;font-weight:800;letter-spacing:-1.5px;line-height:1.1;margin-top:28px">Seçili ${toplam} otoWATT<br>istasyonunda</div>
  <div style="margin-top:22px"><span class="vur" style="font-size:136px;letter-spacing:-5px;line-height:1.08;padding:0 28px 10px;white-space:nowrap">%25 indirim</span></div>
  <div style="margin-top:34px;background:#F4F7FB;border:2px solid #E3E8F0;border-radius:24px;padding:22px 28px;font-size:28px;font-weight:700;color:#334155">
    Örnek DC: <s style="color:#94A3B8">13,99</s> → <b style="color:#047857;font-size:36px">10,49 TL/kWh</b></div>
  <div class="mad"><i>✓</i><span><b>Kod gerekmez:</b> indirimli fiyat şarjdan önce gösterilir</span></div>
  <div class="mad"><i>✓</i><span><b>${ilSay} ilde:</b> ${liste.map(([il]) => il).join(", ")}</span></div>
  <div class="mad"><i>✓</i><span>Başka indirim ve kampanyalarla birleşmez</span></div>
  <div style="position:absolute;left:60px;right:60px;bottom:${hikaye ? 230 : 112}px;font-size:28px;font-weight:800;text-align:right">${hikaye ? "İstasyon listesi @wattkac gönderisinde" : "İstasyonlar için kaydır →"}</div>
  ${hikaye ? "" : ALT}</div>`;

const sayfaIl = (gruplar, no, ek = "") => `<div class="s" style="width:1080px;height:1350px">${UST}
  <div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:34px"><div style="font-size:44px;font-weight:800;letter-spacing:-1px">%25 indirimli istasyonlar</div>
  <div style="font-size:22px;font-weight:700;color:#5B6680">${no}/3</div></div>
  ${gruplar.map(([il, v]) => `<div class="il"><h2>${il}</h2><span>${v.length} istasyon</span></div>
    <div class="izgara">${v.map(([ad, ilce]) => `<div class="ist"><b>${ad}</b><small>${ilce}</small></div>`).join("")}</div>`).join("")}
  ${ek}${ALT}</div>`;

const harita = `<div style="margin-top:34px;background:#0F1B3D;color:#fff;border-radius:26px;padding:28px 32px">
  <div style="font-size:30px;font-weight:800">🗺️ Haritada gör</div>
  <div style="font-size:24px;line-height:1.45;margin-top:10px;color:#CBD5E1">wattkac.com → Kampanyalar → otoWATT → <b style="color:#FFD400">Haritada gör</b>: kampanyalı ${toplam} istasyon indirimli fiyatıyla haritada.</div></div>`;

// Sayfa bölümü: 1) en kalabalık iki il, 2) sonraki üç il, 3) kalanlar + harita kutusu
const s1 = liste.slice(0, 2), s2 = liste.slice(2, 5), s3 = liste.slice(5);
const b = await chromium.launch();
async function cek(W, H, govde, dosya) {
  const p = await b.newPage({ viewport: { width: W, height: H } });
  await p.setContent(`<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>${CSS}</style></head><body>${govde}</body></html>`, { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  const tas = await p.evaluate(() => { const a = document.querySelector(".alt"); if (!a) return false; const els = [...document.querySelectorAll(".ist,.mad,.il")]; return els.some(e => e.getBoundingClientRect().bottom > a.getBoundingClientRect().top - 6); });
  if (tas) console.log("UYARI: taşma", dosya);
  await p.screenshot({ path: path.join(dir, dosya), type: "jpeg", quality: 93 });
  await p.close();
}
if (process.argv.includes("--video-kart")) {   // Reels giriş ve kapanış kartları (1080×1920)
  const vk = (govde) => `<div class="s" style="width:1080px;height:1920px;padding-top:150px">${UST}${govde}</div>`;
  await cek(1080, 1920, vk(`<div style="margin-top:300px"><span class="chip" style="font-size:34px;padding:12px 30px">25 Kasım – 24 Aralık</span></div>
    <div style="font-size:92px;font-weight:800;letter-spacing:-3px;line-height:1.05;margin-top:40px">otoWATT'ta <span class="vur" style="padding:0 18px 6px">%25 indirimli</span> ${toplam} istasyon nerede?</div>
    <div style="font-size:44px;font-weight:700;color:#5B6680;margin-top:50px;line-height:1.35">wattkac.com haritasında<br><b style="color:#0E7490">3 adımda bul</b></div>`), "video_giris.jpg");
  await cek(1080, 1920, vk(`<div style="margin-top:330px;text-align:center">
    <div style="font-size:40px;font-weight:800;color:#0E7490">otoWATT · 25 Kasım – 24 Aralık</div>
    <div style="font-size:120px;font-weight:800;letter-spacing:-4px;line-height:1.02;margin-top:30px">${toplam} istasyonda<br><span class="vur" style="padding:0 24px 8px">%25 indirim</span></div>
    <div style="margin:60px auto 0;display:inline-block;background:#F4F7FB;border:2px solid #E3E8F0;border-radius:28px;padding:26px 40px;font-size:40px;font-weight:700;color:#334155">DC <s style="color:#94A3B8">13,99</s> → <b style="color:#047857;font-size:52px">10,49 TL/kWh</b></div>
    <div style="font-size:40px;font-weight:700;color:#5B6680;margin-top:70px;line-height:1.4">Kampanyalı istasyonları haritada gör<br><b style="color:#0F1B3D;font-size:56px">wattkac.com</b></div></div>`), "video_son.jpg");
  await b.close(); process.exit(0);
}
await cek(1080, 1350, kapak(false), "1_kapak.jpg");
await cek(1080, 1350, sayfaIl(s1, 1), "2_liste.jpg");
await cek(1080, 1350, sayfaIl(s2, 2), "3_liste.jpg");
await cek(1080, 1350, sayfaIl(s3, 3, harita), "4_liste.jpg");
await cek(1080, 1920, kapak(true), "hikaye.jpg");
await b.close();
console.log("bitti:", dir, toplam, "istasyon");
