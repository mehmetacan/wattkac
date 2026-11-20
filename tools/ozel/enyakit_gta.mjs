// En Yakıt Reels'i için gün batımı / neon temalı giriş ve kapanış kartları (1080×1920).
// Kullanım: node tools/ozel/enyakit_gta.mjs <çıktı-klasörü>  → giris_gta.jpg, son_gta.jpg
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
const { chromium } = createRequire(import.meta.url)("playwright");

const cikti = process.argv[2];
const KOK = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const logo = "data:image/png;base64," + fs.readFileSync(path.join(KOK, "tools/ozel/enyakit_logo.png")).toString("base64");

const palmiye = (x, y, s, ters) => `<g transform="translate(${x} ${y}) scale(${ters ? -s : s} ${s})" fill="#12051F">
  <path d="M0 0 C 10 -120 30 -260 70 -400 L 84 -398 C 48 -260 30 -120 22 0 Z"/>
  ${[[-150, -40], [-120, 40], [-60, -95], [20, -110], [110, -70], [150, 10], [80, 60]].map(([dx, dy]) =>
    `<path d="M78 -400 Q ${78 + dx * .55} ${-400 + dy * .55 - 40} ${78 + dx} ${-400 + dy} Q ${78 + dx * .5} ${-400 + dy * .4} 78 -392 Z"/>`).join("")}
</g>`;
const kisi = (kahve) => `<g filter="url(#rim)" fill="#12051F">
  <circle cx="842" cy="1404" r="36"/>
  <rect x="828" y="1430" width="28" height="26" rx="8"/>
  <path d="M800 1462 Q 842 1442 886 1458 L 904 1562 Q 860 1580 808 1568 Z"/>
  <path d="M820 1548 L 968 1560 Q 986 1564 984 1586 L 820 1594 Z"/>
  <path d="M950 1566 L 984 1566 L 1000 1712 L 970 1714 Z"/>
  <path d="M966 1700 L 1022 1700 Q 1034 1716 1020 1722 L 966 1722 Z"/>
  ${kahve
    ? `<path d="M868 1460 Q 912 1470 920 1500 L 900 1508 Q 890 1486 862 1484 Z"/><path d="M912 1500 Q 900 1440 868 1418 L 878 1408 Q 920 1430 930 1494 Z"/>
       <rect x="848" y="1376" width="34" height="44" rx="6" fill="#F5F1EA"/><rect x="848" y="1392" width="34" height="12" fill="#00704A"/>
       <path d="M858 1366 q -10 -20 2 -38 q 12 -18 0 -40 M872 1366 q -10 -20 2 -38 q 12 -18 0 -40" stroke="#FFE7F3" stroke-width="5" fill="none" stroke-linecap="round" opacity=".85"/>`
    : `<path d="M870 1462 Q 920 1500 930 1548 L 908 1552 Q 896 1510 860 1488 Z"/>`}
</g>`;
const sahne = (kahve) => `<svg viewBox="0 0 1080 1920" width="1080" height="1920" style="position:absolute;inset:0">
<defs>
  <linearGradient id="gok" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1A0838"/><stop offset=".34" stop-color="#5B1A8C"/><stop offset=".55" stop-color="#E8357D"/><stop offset=".64" stop-color="#FF7A3D"/><stop offset=".69" stop-color="#FFC24A"/></linearGradient>
  <linearGradient id="gunes" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE96A"/><stop offset="1" stop-color="#FF3F8E"/></linearGradient>
  <linearGradient id="deniz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3B1466"/><stop offset="1" stop-color="#0B0420"/></linearGradient>
  <mask id="serit"><rect width="1080" height="1920" fill="#fff"/>${[0, 1, 2, 3, 4, 5].map(i => `<rect x="0" y="${1168 + i * 26}" width="1080" height="${4 + i * 3}" fill="#000"/>`).join("")}</mask>
  <filter id="rim" x="-20%" y="-20%" width="140%" height="140%"><feMorphology in="SourceAlpha" operator="dilate" radius="3" result="d"/><feFlood flood-color="#FF4FA3"/><feComposite in2="d" operator="in" result="k"/><feGaussianBlur in="k" stdDeviation="4" result="g"/><feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="parla"><feGaussianBlur stdDeviation="10"/></filter>
</defs>
<rect width="1080" height="1920" fill="url(#gok)"/>
<circle cx="540" cy="1150" r="300" fill="url(#gunes)" mask="url(#serit)"/>
<rect y="1300" width="1080" height="620" fill="url(#deniz)"/>
${[0, 1, 2, 3, 4].map(i => `<rect x="${380 + i * 14}" y="${1316 + i * 22}" width="${320 - i * 28}" height="5" rx="2" fill="#FF6FA8" opacity="${.7 - i * .12}"/>`).join("")}
<path d="M0 1300 L 1080 1300" stroke="#FFB0D6" stroke-width="2" opacity=".6"/>
${palmiye(70, 1580, 1.25, false)}${palmiye(1010, 1560, 1.05, true)}${palmiye(180, 1600, .8, false)}
<rect y="1700" width="1080" height="220" fill="#0B0318"/>
<path d="M0 1700 L 1080 1700" stroke="#FF2D95" stroke-width="5" filter="url(#rim)"/>
<g transform="translate(-40 0)">
  <rect x="980" y="1470" width="66" height="232" rx="12" fill="#E30A17"/><rect x="992" y="1496" width="42" height="56" rx="6" fill="#1A0838"/>
  <path d="M1013 1600 C 1000 1660 920 1690 850 1650" stroke="#12051F" stroke-width="10" fill="none"/>
</g>
<g filter="url(#rim)" fill="#12051F">
  <path d="M120 1690 L 128 1612 Q 150 1590 230 1580 Q 330 1500 470 1488 Q 600 1482 700 1530 Q 760 1556 820 1580 Q 930 1592 960 1620 L 968 1690 Z"/>
  <circle cx="290" cy="1690" r="62"/><circle cx="800" cy="1690" r="62"/>
</g>
<path d="M330 1580 Q 420 1512 520 1508 L 540 1580 Z M560 1580 L 548 1510 Q 640 1514 700 1548 L 720 1580 Z" fill="#2A0F4F" opacity=".9"/>
<ellipse cx="945" cy="1640" rx="26" ry="9" fill="#5EF0FF" filter="url(#parla)"/><ellipse cx="945" cy="1640" rx="16" ry="5" fill="#E8FDFF"/>
<path d="M130 1640 L 160 1640" stroke="#FF2D55" stroke-width="8" stroke-linecap="round" filter="url(#parla)"/>
${kisi(kahve)}
</svg>`;

const CSS = `@import url('https://fonts.googleapis.com/css2?family=Anton&family=Plus+Jakarta+Sans:wght@600;700;800&display=block');
*{box-sizing:border-box;margin:0;padding:0}html,body{width:1080px;height:1920px;overflow:hidden;background:#1A0838;font-family:'Plus Jakarta Sans',sans-serif;color:#fff}
.ust{position:absolute;left:72px;right:72px;top:120px;display:flex;align-items:center;justify-content:space-between;z-index:2}
.wk{display:flex;align-items:center;gap:6px;font-size:44px;font-weight:800;color:#fff;text-shadow:0 3px 0 #12051F}.wk b{color:#FFD400}
.ey{background:#fff;border-radius:18px;padding:10px 18px;height:96px;box-shadow:0 6px 0 #12051F}
.blok{position:absolute;left:72px;right:72px;z-index:2}
.bas{font-family:'Anton',sans-serif;text-transform:uppercase;line-height:.98;transform:skewX(-7deg);transform-origin:left;
  background:linear-gradient(180deg,#FFF3A8 0%,#FFD24A 40%,#FF5FA2 100%);-webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-stroke:3px #12051F;filter:drop-shadow(0 7px 0 #12051F) drop-shadow(0 0 26px rgba(255,79,163,.55))}
.etiket{display:inline-block;font-family:'Anton',sans-serif;font-size:40px;letter-spacing:2px;background:#FF2D95;color:#fff;padding:6px 24px 8px;transform:skewX(-10deg);box-shadow:6px 6px 0 #12051F}
.alt{font-size:40px;font-weight:800;line-height:1.3;text-shadow:0 4px 0 #12051F,0 0 18px rgba(18,5,31,.8)}
.alt b{color:#5EF0FF}`;

const b = await chromium.launch();
async function cek(govde, dosya) {
  const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
  await p.setContent(`<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>${CSS}</style></head><body>${govde}</body></html>`, { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  await p.screenshot({ path: path.join(cikti, dosya), type: "jpeg", quality: 93 });
  await p.close();
}
const UST = `<div class="ust"><div class="wk"><svg viewBox="0 0 24 24" width="46" height="46"><path d="M13.5 2 4 13.5h6.2L9.5 22 20 9.8h-6.4z" fill="#FFD400"/></svg><span>Watt<b>Kaç</b></span></div><img class="ey" src="${logo}"></div>`;
await cek(`${sahne(false)}${UST}
  <div class="blok" style="top:330px"><span class="etiket">20–30 KASIM</span>
    <div class="bas" style="font-size:118px;margin-top:34px">En Yakıt'ta</div>
    <div class="bas" style="font-size:190px">10,90 TL</div>
    <div class="bas" style="font-size:96px">27 istasyon nerede?</div>
    <div class="alt" style="margin-top:40px">wattkac.com haritasında<br><b>3 adımda bul</b></div></div>`, "giris_gta.jpg");
await cek(`${sahne(true)}${UST}
  <div class="blok" style="top:330px"><span class="etiket" style="background:#00704A">GÖREV TAMAMLANDI</span>
    <div class="bas" style="font-size:104px;margin-top:34px">Bu fiyatların üstüne</div>
    <div class="bas" style="font-size:104px">bir sıcak kahve</div>
    <div class="bas" style="font-size:104px">içelim</div>
    <div class="alt" style="margin-top:40px">En Yakıt'ta 200 kWh şarja<br><b>15 Starbucks yıldızı</b> · 1 Kasım – 30 Nisan</div>
    <div class="alt" style="margin-top:26px;font-size:36px">wattkac.com</div></div>`, "son_gta.jpg");
await b.close();
console.log("bitti");
