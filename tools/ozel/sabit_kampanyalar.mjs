// Profilde sabitlenecek iki tek görsellik gönderi: banka kartı ve şarj ağı kampanyaları (beyaz tema, marka logolarıyla).
// Kullanım: node tools/ozel/sabit_kampanyalar.mjs <çıktı-klasörü>   → banka.jpg, sarj.jpg
// Logolar tools/ozel/logolar/<id>.<uzantı>; logosu olmayan marka adıyla yazılır.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");

const cikti = process.argv[2];
const KOK = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const LDIR = path.join(KOK, "tools/ozel/logolar");
const MIME = { svg: "image/svg+xml", png: "image/png", webp: "image/webp", jpg: "image/jpeg" };
const logo = id => { const f = fs.readdirSync(LDIR).find(x => x.split(".")[0] === id); if (!f) return null;
  return `data:${MIME[f.split(".").pop()]};base64,` + fs.readFileSync(path.join(LDIR, f)).toString("base64"); };
fs.mkdirSync(cikti, { recursive: true });

// [logo kimliği, ad, satırlar: [metin, son gün]]; * resmi sayfada doğrulanıyor
const BANKA = [
  ["garanti", "Garanti BBVA", [["<b>75 TL bonus</b> · Ovolt", "30 Kas"], ["<b>100 TL bonus</b> · Varr", "30 Kas"], ["<b>%50 bonus</b> · Shell Recharge uygulaması", "30 Kas"]]],
  ["ziraat", "Ziraat Bankası", [["<b>%20 Jest Lira</b> · 20 şarj ağında", "30 Kas"]]],
  ["vakifbank", "VakıfBank", [["<b>%20 indirim</b> · kredi kartıyla 6 ağda", "30 Kas"], ["<b>%20 indirim</b> · Recycle Card ile 12 ağda", "30 Kas"]]],
  ["akbank", "Akbank", [["<b>%20 indirim</b> · Voltla uygulamasıyla 10 ağda", "22 Kas"]]],
  ["yapikredi", "Yapı Kredi", [["<b>435 TL Worldpuan</b> · WAT Mobilite", "30 Kas"]]],
  ["qnb", "QNB", [["<b>50 TL ParaPuan</b> · tüm istasyonlarda", "30 Kas"], ["<b>125 mil</b> · Miles&Smiles QNB", "30 Kas"]]],
  ["halkbank", "Halkbank", [["<b>75 TL ParafPara</b> · tüm istasyonlarda", "30 Kas"], ["<b>%10 indirim</b> · Paraf Doğal ile", "süresiz"]]],
  ["denizbank", "DenizBank", [["<b>%10 indirim</b> · tüm istasyonlarda", "30 Kas"]]],
  ["kuveytturk", "Kuveyt Türk", [["<b>%10 indirim</b> · tüm istasyonlarda", "30 Kas"]]],
  ["on", "ON Dijital", [["<b>%20 iade</b> · tüm istasyonlarda*", "30 Kas"]]],
];
const SARJ = [
  ["zes", "ZES", [["<b>%15</b> Vodafone Red · <b>%15</b> TAV Passport", "31 Ara"], ["<b>%15 iade</b> Vodafone Pay · <b>30 kWh</b> Metro alışverişine", "31 Ara"], ["<b>1.250 TL</b> şarj desteği · Pirelli lastik alana", "30 Ara"]]],
  ["otopriz", "Otopriz", [["<b>%30</b> · seçili 73 istasyonda (AC ve DC)", "30 Kas"], ["<b>DC %30</b> · ayın son günü", "30 Kas"], ["<b>DC %10</b> favori istasyonda · <b>%20</b> doğum gününde", "süresiz"]]],
  ["enyakit", "En Yakıt", [["DC <s>14,90</s> <b>10,90 TL/kWh</b> · seçili 27 istasyonda", "30 Kas"], ["<b>200 kWh'ye 15 Starbucks yıldızı</b>*", "30 Nis"]]],
  ["astor", "ASTOR Şarj", [["DC <s>13,99</s> <b>10,90</b> · AC <s>9,89</s> <b>8,99 TL/kWh</b> · uygulamada", "30 Kas"]]],
  ["wat", "WAT Mobilite", [["<b>Her salı %10</b> · AC ve DC", "29 Ara"], ["<b>%4</b> · Ford sahiplerine", "31 Ara"]]],
  ["ovolt", "Ovolt", [["<b>%12 indirim</b> · dahil istasyonlarda", "22 Kas"], ["<b>50 TL VoltPuan</b> · yeni üyeye", "31 Ara"]]],
  ["trugo", "Trugo", [["<b>%20 indirim</b> · Togg sahiplerine, DC", "30 Kas"]]],
  ["esarj", "Eşarj", [["<b>%10 Eşarj Puan</b> · Allianz EV kasko sahiplerine", "31 Ara"]]],
  ["aksa", "Aksa Şarj", [["<b>%15</b> · Karaköprü (Şanlıurfa)", "26 Kas"], ["<b>%15</b> · Pendik Duru Park", "12 Ara"]]],
  ["rotawatt", "Rotawatt", [["<b>%20 indirim</b> · uygulamayla 25 ağda", "31 Ara"]]],
];

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=block');
*{box-sizing:border-box;margin:0;padding:0}html,body{width:1080px;height:1350px;overflow:hidden;font-family:'Plus Jakarta Sans',sans-serif;color:#0F1B3D;background:#fff}
.s{position:relative;width:1080px;height:1350px;padding:58px 56px 0;background:radial-gradient(700px 420px at 100% 0,rgba(255,212,0,.16),transparent 70%),#fff}
.ust{display:flex;align-items:center;justify-content:space-between}
.wk{display:flex;align-items:center;gap:6px;font-size:34px;font-weight:800;letter-spacing:-.5px}.wk b{color:#E5A800}
.ay{font-size:22px;font-weight:800;background:#0F1B3D;color:#fff;border-radius:999px;padding:8px 20px}
h1{font-size:54px;font-weight:800;letter-spacing:-1.5px;line-height:1.05;margin-top:30px}
h1 span{background:#FFD400;border-radius:12px;padding:0 12px}
.alt{font-size:22px;color:#5B6680;font-weight:600;margin-top:12px}
.liste{margin-top:24px;border-top:2px solid #EEF1F6}
.sat{display:flex;align-items:center;gap:22px;padding:9px 0;border-bottom:2px solid #EEF1F6}
.lg{flex:none;width:176px;height:58px;display:flex;align-items:center;justify-content:center}
.lg img{max-width:176px;max-height:58px;object-fit:contain}
.lg.simge{flex-direction:column;height:auto;gap:4px}.lg.simge img{max-height:46px}.lg.simge small{font-size:17px;font-weight:800;color:#0F1B3D}
.lg.yazi{font-size:24px;font-weight:800;letter-spacing:-.3px;text-align:center;line-height:1.1;color:#0F1B3D}
.tk{flex:1;min-width:0}
.tk div{display:flex;justify-content:space-between;align-items:baseline;gap:14px;font-size:21px;line-height:1.34;color:#334155}
.tk b{color:#0F1B3D;font-weight:800;font-size:25px;letter-spacing:-.3px;padding:0 4px;margin:0 -2px;border-radius:4px;background:linear-gradient(transparent 52%,#FFE066 52%,#FFE066 92%,transparent 92%)}
.tk s{color:#94A3B8;font-weight:600}
.tk i{flex:none;font-style:normal;font-size:16px;font-weight:700;color:#0E7490;background:#E6F4F7;border-radius:8px;padding:2px 9px}
.tk i.yakin{color:#B42318;background:#FDECEA}
.alt2{position:absolute;left:56px;right:56px;bottom:40px;display:flex;justify-content:space-between;align-items:flex-end;gap:20px}
.alt2 .u{font-size:24px;font-weight:800}.alt2 .u b{color:#0E7490}
.alt2 .n{font-size:15px;color:#7A869C;line-height:1.4;max-width:560px;text-align:right}`;

const WK = `<div class="wk"><svg viewBox="0 0 24 24" width="38" height="38"><path d="M13.5 2 4 13.5h6.2L9.5 22 20 9.8h-6.4z" fill="#E5A800"/></svg><span>Watt<b>Kaç</b></span></div>`;
const SIMGE = new Set(["otopriz", "esarj"]);   // logosu yalnızca simge olan markalar: altına ad yazılır
const sayfa = (baslik, alt, liste, not) => `<div class="s"><div class="ust">${WK}<span class="ay">Kasım 2026</span></div>
  <h1>${baslik}</h1><div class="alt">${alt}</div>
  <div class="liste">${liste.map(([id, ad, sat]) => { const l = logo(id);
    return `<div class="sat"><div class="lg${l ? (SIMGE.has(id) ? " simge" : "") : " yazi"}">${l ? `<img src="${l}" alt="${ad}">${SIMGE.has(id) ? `<small>${ad}</small>` : ""}` : ad}</div><div class="tk">${sat.map(([t, s]) =>
      `<div><span>${t}</span><i class="${/^2[0-6] Kas$/.test(s) ? "yakin" : ""}">${s}</i></div>`).join("")}</div></div>`; }).join("")}</div>
  <div class="alt2"><div class="u">Ayrıntılar ve istasyonlar<br><b>wattkac.com/kampanyalar</b></div><div class="n">${not}21 Kasım 2026 itibarıyla, resmi kaynaklardan. Koşullar değişebilir; katılmadan önce resmi sayfadan kontrol edin. Reklam veya iş birliği değildir.</div></div></div>`;

const b = await chromium.launch();
async function cek(govde, dosya) {
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  await p.setContent(`<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>${CSS}</style></head><body>${govde}</body></html>`, { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  const tasma = await p.evaluate(() => { const l = document.querySelector(".liste").getBoundingClientRect(), a = document.querySelector(".alt2").getBoundingClientRect(); return l.bottom > a.top - 8; });
  if (tasma) console.log("UYARI: liste alt bilgiye taşıyor:", dosya);
  await p.screenshot({ path: path.join(cikti, dosya), type: "jpeg", quality: 93 });
  await p.close();
}
await cek(sayfa("Banka kartıyla <span>şarj kampanyaları</span>", "Hangi kartla hangi şarj ağında ne kazanırsın?", BANKA, "* Resmi sayfada doğrulanıyor. "), "banka.jpg");
await cek(sayfa("Şarj ağlarının <span>kendi kampanyaları</span>", "Ağların ve şarj uygulamalarının indirimleri", SARJ, "* Resmi sayfada doğrulanıyor. "), "sarj.jpg");
await b.close();
console.log("bitti:", cikti);
