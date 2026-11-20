// En Yakıt 20–30 Kasım 2026 kampanyası: haritalı karusel, hikâye ve Reels videosu.
// Kullanım: node tools/ozel/enyakit_2026_11.mjs <il-sınırları.geojson> <çıktı-klasörü> [--video]
// İl sınırları: https://cdn.jsdelivr.net/gh/cihadturhan/tr-geojson@master/geo/tr-cities-utf8.json
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const [geoYolu, cikti] = process.argv.slice(2);
const VIDEO = process.argv.includes("--video");
const KOK = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const geo = JSON.parse(fs.readFileSync(geoYolu, "utf8"));
const logo = "data:image/png;base64," + fs.readFileSync(path.join(KOK, "tools/ozel/enyakit_logo.png")).toString("base64");
fs.mkdirSync(cikti, { recursive: true });

// Koordinatlar istasyonlar.json'daki En Yakıt kayıtlarından; ilçeler En Yakıt'ın kampanya görsellerinden
const ST = [
  ["Bi Mola Çiftalan", "Eyüpsultan", "İstanbul", 41.236, 28.9091, 1],
  ["Bi Mola Fenertepe", "Eyüpsultan", "İstanbul", 41.1987, 28.8223, 1],
  ["Bi Mola Işıklar", "Eyüpsultan", "İstanbul", 41.1958, 28.8258, 1],
  ["Bi Mola Odayeri", "Eyüpsultan", "İstanbul", 41.2347, 28.8884, 1],
  ["Bi Mola Çekmeköy 1-2", "Beykoz", "İstanbul", 41.0558, 29.1879, 1],
  ["Bi Mola Poyrazköy (Güney)", "Beykoz", "İstanbul", 41.1974, 29.1483, 1],
  ["Bi Mola Poyrazköy (Kuzey)", "Beykoz", "İstanbul", 41.1988, 29.1479, 1],
  ["Bi Mola Reşadiye", "Çekmeköy", "İstanbul", 41.1034, 29.2909, 1],
  ["Bi Mola Ömerli", "Çekmeköy", "İstanbul", 41.089, 29.2866, 1],
  ["Keller Williams Bodrum", "Bodrum", "Muğla", 37.0534, 27.3812, 2],
  ["Yalçınlar Cam Söke", "Söke", "Aydın", 37.7981, 27.4697, 2],
  ["Rindera İş ve Yaşam Merkezi", "Honaz", "Denizli", 37.8067, 29.243, 2],
  ["Fame Beach Hotel Kemer", "Kemer", "Antalya", 36.602, 30.5666, 2],
  ["Kaia Coracesium Otel", "Alanya", "Antalya", 36.5862, 31.8734, 2],
  ["Rota İncek AVM", "Yenimahalle", "Ankara", 39.8309, 32.709, 2],
  ["Podium AVM", "Yenimahalle", "Ankara", 39.9617, 32.7685, 2],
  ["Mamak Beykoz Petrol", "Mamak", "Ankara", 39.9511, 33.0609, 2],
  ["Taşpınar Dinlenme Tesisi", "Pozantı", "Adana", 37.4331, 34.8763, 3],
  ["Sorgun Safa Termal Hotel", "Sorgun", "Yozgat", 39.8033, 35.207, 3],
  ["Ens Park Merzifon", "Merzifon", "Amasya", 40.8692, 35.4964, 3],
  ["Teymur Continental Hotel", "Şehitkamil", "Gaziantep", 37.0762, 37.3681, 3],
  ["Park Hayat (Güney)", "Karaköprü · Urfa yönü", "Şanlıurfa", 37.1967, 38.563, 3],
  ["Park Hayat (Kuzey)", "Karaköprü · Antep yönü", "Şanlıurfa", 37.1988, 38.5628, 3],
  ["Akcan Otomotiv Volvo", "Kayapınar", "Diyarbakır", 37.9128, 40.0959, 3],
  ["Timya Outlet AVM", "Merkez", "Rize", 41.017, 40.5154, 3],
  ["Polat Palandöken Hotel", "Palandöken", "Erzurum", 39.8657, 41.2745, 3],
].map(([n, ilce, il, lat, lon, b]) => ({ n, ilce, il, lat, lon, b }));
// Kampanya 27 istasyon sayar: Çekmeköy 1 ve 2 aynı noktada
const SAYI = 27;

const KX = 100 * Math.cos((39 * Math.PI) / 180), KY = 100;
const px = (lon, lat) => [(lon - 25.5) * KX, (42.4 - lat) * KY];
ST.forEach(s => ([s.x, s.y] = px(s.lon, s.lat)));
const yollar = [];
for (const f of geo.features) {
  const g = f.geometry, polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  let d = "";
  for (const p of polys) for (const r of p) d += "M" + r.map(([lo, la]) => px(lo, la).map(v => v.toFixed(1)).join(",")).join("L") + "Z";
  yollar.push(d);
}

const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=block');
*{box-sizing:border-box;margin:0;padding:0}
html,body{overflow:hidden;font-family:'Plus Jakarta Sans',sans-serif;color:#0F1B3D;background:#F3F5F9}
.s{position:relative;overflow:hidden;background:radial-gradient(900px 700px at 95% -8%,rgba(255,212,0,.20),transparent 60%),radial-gradient(800px 700px at -10% 108%,rgba(32,190,190,.14),transparent 60%),#F3F5F9}
.ust{position:absolute;left:72px;right:72px;top:64px;display:flex;align-items:center;justify-content:space-between}
.wk{display:flex;align-items:center;gap:6px;font-size:40px;font-weight:800;letter-spacing:-.5px;color:#0F1B3D}
.wk b{color:#E5A800}
.ey{height:84px}
.harita{position:absolute;overflow:hidden}
.harita svg{position:absolute;inset:0;width:100%;height:100%}
.harita path{fill:#E1E6EE;stroke:#fff;stroke-width:1.4;vector-effect:non-scaling-stroke;stroke-linejoin:round}
.pin{position:absolute;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;background:#E30A17;border:5px solid #fff;box-shadow:0 4px 12px rgba(227,10,23,.35)}
.pin i{position:absolute;inset:-5px;display:flex;align-items:center;justify-content:center;font-style:normal;font-size:15px;font-weight:800;color:#fff}
.pin.no{width:40px;height:40px;margin:-20px 0 0 -20px;border-width:4px}
.pin.no i{inset:-4px;font-size:18px}
.ring{position:absolute;border-radius:50%;border:4px solid rgba(227,10,23,.5);pointer-events:none}
.chip{display:inline-block;background:#0F1B3D;color:#fff;font-weight:800;border-radius:999px}
.sari{background:#FFD400;color:#0F1B3D;border-radius:22px;display:inline-block}
.alt{position:absolute;left:72px;right:72px;bottom:56px;font-size:21px;color:#5B6680;line-height:1.45}
.alt b{color:#0F1B3D}
.liste{position:absolute;left:72px;right:72px;display:grid;grid-template-columns:1fr 1fr;column-gap:28px}
.li{display:flex;gap:16px;align-items:flex-start;padding:15px 0;border-bottom:2px solid #E1E6EE}
.li .nu{flex:none;width:40px;height:40px;border-radius:50%;background:#E30A17;color:#fff;font-weight:800;font-size:19px;display:flex;align-items:center;justify-content:center;margin-top:2px}
.li b{display:block;font-size:26px;font-weight:800;line-height:1.2}
.li span{display:block;font-size:21px;color:#5B6680;margin-top:3px}
`;
const WK = `<div class="wk"><svg viewBox="0 0 24 24" width="42" height="42"><path d="M13.5 2 4 13.5h6.2L9.5 22 20 9.8h-6.4z" fill="#E5A800"/></svg><span>Watt<b>Kaç</b></span></div>`;
const FINCAN = (s) => `<svg viewBox="0 0 120 120" width="${s}" height="${s}"><path d="M44 30c-6-8 6-12 0-20M60 30c-6-8 6-12 0-20M76 30c-6-8 6-12 0-20" stroke="#B9875A" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M22 42h76l-8 56a10 10 0 0 1-10 9H40a10 10 0 0 1-10-9z" fill="#00704A"/><path d="M96 52h6a12 12 0 0 1 0 24h-9" stroke="#00704A" stroke-width="8" fill="none"/><rect x="18" y="36" width="84" height="12" rx="6" fill="#0B4D35"/><circle cx="60" cy="74" r="13" fill="#fff" opacity=".9"/></svg>`;

const sayfa = (W, H, govde) => `<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body style="width:${W}px;height:${H}px"><div class="s" style="width:${W}px;height:${H}px">${govde}</div>
<script>
const YOLLAR=${JSON.stringify(yollar)}, ST=${JSON.stringify(ST)};
function harita(el, kam, pinler){ // kam: {cx,cy,w}; pinler: [{i, no, olcek, halka}]
  const W=el.clientWidth,H=el.clientHeight, h=kam.w*H/W, x0=kam.cx-kam.w/2, y0=kam.cy-h/2, k=W/kam.w;
  if(!el.firstChild){ el.innerHTML='<svg preserveAspectRatio="none">'+YOLLAR.map(d=>'<path d="'+d+'"/>').join('')+'</svg><div class="pl"></div>'; }
  el.querySelector('svg').setAttribute('viewBox', x0+' '+y0+' '+kam.w+' '+h);
  el.querySelector('.pl').innerHTML=pinler.map(p=>{const s=ST[p.i], X=(s.x-x0)*k, Y=(s.y-y0)*k, o=p.olcek??1;
    const halka=p.halka?'<div class="ring" style="left:'+(X-p.halka/2)+'px;top:'+(Y-p.halka/2)+'px;width:'+p.halka+'px;height:'+p.halka+'px;opacity:'+(p.hop??1)+'"></div>':'';
    return halka+'<div class="pin'+(p.no?' no':'')+'" style="left:'+X+'px;top:'+Y+'px;transform:scale('+o+')">'+(p.no?'<i>'+p.no+'</i>':'')+'</div>'}).join('');
}
function sigdir(ids, W, H, pay){ const xs=ids.map(i=>ST[i].x), ys=ids.map(i=>ST[i].y);
  let a=Math.min(...xs),b=Math.max(...xs),c=Math.min(...ys),d=Math.max(...ys);
  let w=Math.max(b-a,(d-c)*W/H)*(1+pay)+60; return {cx:(a+b)/2, cy:(c+d)/2, w}; }
</script></body></html>`;

const TUM = ST.map((_, i) => i);
const BOLGE = {
  1: { bas: "Kuzey Marmara Otoyolu", alt: "İstanbul · 10 istasyon" },
  2: { bas: "Ege, Akdeniz ve Ankara", alt: "5 ilde 8 istasyon" },
  3: { bas: "Karadeniz, İç ve Doğu Anadolu", alt: "8 ilde 9 istasyon" },
};
const ALT = `<div class="alt">Güncelleme: 20 Kasım 2026 · Koşullar değişebilir, <b>şarjdan önce En Yakıt uygulamasından kontrol edin.</b> @wattkac</div>`;

const tarayici = await chromium.launch();
async function cek(W, H, govde, dosya, hazirla) {
  const p = await tarayici.newPage({ viewport: { width: W, height: H } });
  await p.setContent(sayfa(W, H, govde), { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  if (hazirla) await p.evaluate(hazirla);
  await p.screenshot({ path: path.join(cikti, dosya), type: "jpeg", quality: 92 });
  await p.close();
}

const kapak = (W, H, hikaye) => {
  const y = hikaye ? 230 : 0;
  return `<div class="ust" style="top:${64 + (hikaye ? 120 : 0)}px">${WK}<img class="ey" src="${logo}"></div>
  <div style="position:absolute;left:72px;right:72px;top:${190 + y}px">
    <span class="chip" style="font-size:30px;padding:10px 26px">20–30 Kasım</span>
    <div style="font-size:52px;font-weight:800;line-height:1.12;margin-top:30px;letter-spacing:-1px">Seçili ${SAYI} En Yakıt istasyonunda DC şarj</div>
    <div style="margin-top:26px;display:flex;align-items:flex-end;gap:22px"><span class="sari" style="font-size:168px;font-weight:800;letter-spacing:-6px;padding:0 30px 8px;line-height:1.05">10,90</span>
      <span style="font-size:46px;font-weight:800;padding-bottom:22px">TL/kWh</span></div>
    <div style="font-size:30px;color:#5B6680;margin-top:22px">Liste fiyatı <s>14,90 TL/kWh</s> · uygulamadan başlatılan şarjda otomatik</div>
  </div>
  <div class="harita" id="h" style="left:40px;right:40px;top:${hikaye ? 1060 : 660}px;height:${hikaye ? 560 : 440}px"></div>
  <div style="position:absolute;left:72px;right:72px;bottom:${hikaye ? 230 : 140}px;display:flex;justify-content:space-between;align-items:center;font-size:28px;font-weight:700">
    <span style="display:flex;align-items:center;gap:12px">${FINCAN(46)} Bonus: Starbucks yıldızı</span><span>${hikaye ? "İstasyonlar @wattkac gönderisinde" : "İstasyonlar için kaydır →"}</span></div>
  ${hikaye ? "" : ALT}`;
};
const kapakHazir = () => { const el = document.getElementById("h"); harita(el, sigdir(ST.map((_, i) => i), el.clientWidth, el.clientHeight, .04), ST.map((_, i) => ({ i, olcek: .8 }))); };

const bolgeSayfa = (b) => {
  const ids = TUM.filter(i => ST[i].b === b);
  const satir = ids.map((i, k) => `<div class="li"><div class="nu">${k + 1}</div><div><b>${ST[i].n}</b><span>${ST[i].ilce} / ${ST[i].il}</span></div></div>`).join("");
  return `<div class="ust">${WK}<img class="ey" src="${logo}"></div>
  <div style="position:absolute;left:72px;right:72px;top:178px"><div style="font-size:50px;font-weight:800;letter-spacing:-1px;color:#E30A17">${BOLGE[b].bas}</div>
  <div style="font-size:25px;color:#5B6680;margin-top:6px;font-weight:600">${BOLGE[b].alt}</div></div>
  <div class="harita" id="h" data-b="${b}" style="left:40px;right:40px;top:300px;height:430px"></div>
  <div class="liste" style="top:752px">${satir}</div>${ALT}`;
};
const bolgeHazir = () => { const el = document.getElementById("h"), b = +el.dataset.b, ids = ST.map((s, i) => s.b === b ? i : -1).filter(i => i >= 0);
  // Şanlıurfa'daki iki Park Hayat ve Poyrazköy çiftleri üst üste: numaralar biraz kaydırılır
  harita(el, b === 1 ? sigdir(ids, el.clientWidth, el.clientHeight, .25) : sigdir(ids, el.clientWidth, el.clientHeight, .12), ids.map((i, k) => ({ i, no: k + 1 })));
  const pins = el.querySelectorAll(".pin"); const kaydir = { 1: [[1, 26, -6], [4, -16, 6], [2, -22, 0], [3, 22, 0], [6, 0, 22], [7, 0, -22], [8, 18, -18], [9, -10, 14]], 2: [[6, -14, 16], [7, -14, -16]], 3: [[5, 0, 22], [6, 0, -22]] }[b] || [];
  for (const [k, dx, dy] of kaydir) { const p = pins[k - 1]; p.style.left = parseFloat(p.style.left) + dx + "px"; p.style.top = parseFloat(p.style.top) + dy + "px"; } };

const starbucks = (W, H, hikaye) => `<div class="ust" style="top:${64 + (hikaye ? 120 : 0)}px">${WK}<img class="ey" src="${logo}"></div>
  <div style="position:absolute;left:72px;right:72px;top:${210 + (hikaye ? 260 : 0)}px">
    <div style="display:flex;align-items:center;gap:22px">${FINCAN(120)}<div style="font-size:30px;font-weight:700;color:#00704A">Bu keyfin üzerine<br>bir kahve iyi gider</div></div>
    <div style="font-size:66px;font-weight:800;line-height:1.08;letter-spacing:-1.5px;margin-top:40px">Şarj ettikçe<br>Starbucks yıldızı kazan</div>
    <div style="margin-top:44px;background:#fff;border-radius:32px;padding:40px 44px;box-shadow:0 18px 50px rgba(15,27,61,.10);display:flex;align-items:center;gap:30px">
      <div style="text-align:center"><div style="font-size:86px;font-weight:800;letter-spacing:-3px;line-height:1">200</div><div style="font-size:28px;font-weight:700;color:#5B6680">kWh şarj</div></div>
      <div style="font-size:64px;font-weight:800;color:#C3CAD6">→</div>
      <div style="text-align:center"><div style="font-size:86px;font-weight:800;letter-spacing:-3px;line-height:1;color:#00704A">15</div><div style="font-size:28px;font-weight:700;color:#5B6680">Starbucks yıldızı</div></div>
      <div style="margin-left:auto;font-size:26px;line-height:1.35;color:#0F1B3D;font-weight:600;max-width:300px">En Yakıt'ta 200 kWh şarjı tamamla, dilediğin içeceğin keyfini çıkar.</div>
    </div>
    <div style="margin-top:34px"><span class="chip" style="font-size:30px;padding:12px 28px;background:#00704A">1 Kasım 2026 – 30 Nisan 2027</span></div>
    <div style="font-size:27px;color:#5B6680;margin-top:30px;line-height:1.45">10,90 TL/kWh indirimi 20–30 Kasım'da seçili ${SAYI} istasyonda; yıldız kampanyası Nisan sonuna kadar sürüyor. Katılım ve yıldız tanımlama koşulları için En Yakıt'ın resmi duyurusuna bakın.</div>
  </div>${hikaye ? "" : ALT}`;

await cek(1080, 1350, kapak(1080, 1350, false), "1_kapak.jpg", kapakHazir);
for (const b of [1, 2, 3]) await cek(1080, 1350, bolgeSayfa(b), `${b + 1}_bolge${b}.jpg`, bolgeHazir);
await cek(1080, 1350, starbucks(1080, 1350, false), "5_starbucks.jpg");
await cek(1080, 1920, kapak(1080, 1920, true), "hikaye.jpg", kapakHazir);
await cek(1080, 1920, starbucks(1080, 1920, true), "hikaye_starbucks.jpg");

if (VIDEO) {
  // Batıdan doğuya duraklar (aynı şehirdeki noktalar tek durak)
  const grup = {};
  ST.forEach((s, i) => { const k = s.b === 1 ? "İstanbul" : s.il === "Antalya" ? s.ilce : s.il; (grup[k] ||= { ad: k === s.ilce ? `${s.ilce} / ${s.il}` : (k === "İstanbul" ? "İstanbul · Kuzey Marmara Otoyolu" : s.il), ids: [] }).ids.push(i); });
  const duraklar = Object.values(grup).map(g => ({ ...g, lon: Math.min(...g.ids.map(i => ST[i].lon)) })).sort((a, b) => a.lon - b.lon);
  const FPS = 30, GIRIS = 2.6, DURAK = 1.25, CIKIS = 2.2, SON = 4.2;
  const TUR = duraklar.length * DURAK, TOPLAM = GIRIS + TUR + CIKIS + SON;
  const govde = `<div class="harita" id="h" style="left:0;right:0;top:0;height:1920px"></div>
    <div style="position:absolute;left:0;right:0;top:0;height:330px;background:linear-gradient(#F3F5F9 62%,rgba(243,245,249,0))"></div>
    <div class="ust" style="top:150px">${WK}<img class="ey" src="${logo}"></div>
    <div id="bas" style="position:absolute;left:72px;right:72px;top:290px"><span class="chip" style="font-size:32px;padding:10px 26px">20–30 Kasım</span>
      <div style="margin-top:22px;display:flex;align-items:flex-end;gap:18px"><span class="sari" style="font-size:130px;font-weight:800;letter-spacing:-5px;padding:0 26px 6px;line-height:1.05">10,90</span><span style="font-size:42px;font-weight:800;padding-bottom:18px">TL/kWh</span></div>
      <div style="font-size:34px;font-weight:700;margin-top:16px">Seçili ${SAYI} En Yakıt istasyonunda DC şarj</div></div>
    <div id="kart" style="position:absolute;left:60px;right:60px;top:1560px;background:#fff;border-radius:30px;padding:30px 36px;box-shadow:0 16px 44px rgba(15,27,61,.12)"></div>
    <div id="son" style="position:absolute;inset:0;background:rgba(243,245,249,.96);display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:0 90px;opacity:0">
      ${FINCAN(220)}<div style="font-size:74px;font-weight:800;line-height:1.1;letter-spacing:-2px;margin-top:40px">Bu fiyatların üstüne<br>bir sıcak kahve içelim</div>
      <div style="font-size:36px;font-weight:600;color:#5B6680;margin-top:36px;line-height:1.4">En Yakıt'ta 200 kWh şarja<br><b style="color:#00704A">15 Starbucks yıldızı</b> · 1 Kasım – 30 Nisan</div>
      <div style="margin-top:70px;transform:scale(1.3)">${WK}</div></div>`;
  const p = await tarayici.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.setContent(sayfa(1080, 1920, govde), { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  await p.evaluate(([duraklar, z]) => {
    const el = document.getElementById("h"), W = el.clientWidth, H = el.clientHeight;
    const tum = sigdir(ST.map((_, i) => i), W, H, .02); tum.cy -= 40 * tum.w / W;
    const kamlar = duraklar.map(d => { const k = sigdir(d.ids, W, H, .3); k.w = Math.max(k.w, d.ids.length > 3 ? 150 : 420); k.cy += 70 * k.w / W; return k; });
    const e = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2, ara = (a, b, t) => a + (b - a) * t;
    const gec = (a, b, t) => { const u = e(Math.min(1, Math.max(0, t))), m = Math.hypot(b.cx - a.cx, b.cy - a.cy);
      return { cx: ara(a.cx, b.cx, u), cy: ara(a.cy, b.cy, u), w: Math.exp(ara(Math.log(a.w), Math.log(b.w), u)) * (1 + Math.min(1.2, m / 400) * Math.sin(Math.PI * u)) }; };
    const kart = (d) => `<div style="font-size:26px;font-weight:800;color:#E30A17;letter-spacing:.5px">${d.ad.toLocaleUpperCase("tr")}</div>` +
      `<div style="display:grid;grid-template-columns:${d.ids.length > 4 ? "1fr 1fr" : "1fr"};gap:6px 24px;margin-top:12px">` +
      d.ids.map(i => `<div style="font-size:${d.ids.length > 4 ? 25 : 34}px;font-weight:700">${ST[i].n}</div>`).join("") + "</div>";
    window.kare = (t) => {
      const son = document.getElementById("son"), bas = document.getElementById("bas"), kd = document.getElementById("kart");
      let kam = tum, pin = [], kartD = null;
      const tt = t - z.GIRIS;
      if (t < z.GIRIS) { kam = tum; pin = ST.map((_, i) => ({ i, olcek: Math.min(1, Math.max(0, (t - .6 - i * .03) * 4)) * .7 })); bas.style.opacity = 1; }
      else if (tt < z.TUR) {
        const n = Math.floor(tt / z.DURAK), f = (tt - n * z.DURAK) / z.DURAK, onceki = n ? kamlar[n - 1] : tum;
        kam = gec(onceki, kamlar[n], f / .45); kartD = duraklar[n];
        bas.style.opacity = Math.max(0, 1 - tt * 2);
        const gor = new Set(duraklar.slice(0, n).flatMap(d => d.ids));
        pin = ST.map((_, i) => gor.has(i) ? { i, olcek: .7 } : duraklar[n].ids.includes(i) ? { i, olcek: f < .4 ? 0 : Math.min(1.15, (f - .4) * 6), halka: f < .4 ? 0 : 30 + (f - .4) * 140, hop: Math.max(0, 1 - (f - .4) * 1.8) } : null).filter(Boolean);
      } else {
        const u = (tt - z.TUR) / z.CIKIS; kam = gec(kamlar[kamlar.length - 1], tum, u);
        pin = ST.map((_, i) => ({ i, olcek: .8 }));
        kartD = { ad: "Toplam " + z.SAYI + " istasyon", ids: [] };
        son.style.opacity = Math.max(0, Math.min(1, (t - (z.GIRIS + z.TUR + z.CIKIS)) * 2.5));
      }
      harita(el, kam, pin);
      if (kartD) { kd.style.opacity = 1; const h = kart(kartD); if (kd.dataset.h !== h) { kd.innerHTML = h; kd.dataset.h = h; } }
      else kd.style.opacity = 0;
      if (kartD && !kartD.ids.length) kd.innerHTML = `<div style="font-size:40px;font-weight:800">${kartD.ad}</div><div style="font-size:30px;color:#5B6680;margin-top:8px">20–30 Kasım · DC 10,90 TL/kWh</div>`;
    };
  }, [duraklar, { GIRIS, TUR, CIKIS, DURAK, SAYI }]);
  const kareler = path.join(cikti, "_kareler");
  fs.mkdirSync(kareler, { recursive: true });
  const n = Math.round(TOPLAM * FPS);
  for (let f = 0; f < n; f++) {
    await p.evaluate(t => kare(t), f / FPS);
    await p.screenshot({ path: path.join(kareler, String(f).padStart(4, "0") + ".jpg"), type: "jpeg", quality: 90 });
  }
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", path.join(kareler, "%04d.jpg"),
    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", path.join(cikti, "reels.mp4")]);
  fs.rmSync(kareler, { recursive: true });
  console.log("video:", n, "kare,", TOPLAM.toFixed(1), "sn,", duraklar.map(d => d.ad).join(" → "));
}
await tarayici.close();
console.log("bitti:", cikti);
