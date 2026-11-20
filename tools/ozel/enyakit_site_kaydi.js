// wattkac.com'da En Yakıt 10,90 TL/kWh istasyonlarını bulmayı gösteren ekran kaydı (telefon, 1080×1920).
// Kullanım: node tools/ozel/enyakit_site_kaydi.js <çıktı-klasörü>   → <klasör>/site.mp4
// Kayıt Chrome'un ekran yayınından (CDP screencast) alınır; kareler zaman damgalarıyla 30 fps videoya çevrilir.
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path"), { execFileSync } = require("child_process");

const cikti = process.argv[2];
const kareDir = path.join(cikti, "_site");
fs.rmSync(kareDir, { recursive: true, force: true }); fs.mkdirSync(kareDir, { recursive: true });
const bekle = ms => new Promise(r => setTimeout(r, ms));
const DURAK = [ // batıdan doğuya
  [37.43, 27.42, 9], [41.16, 29.05, 10], [37.81, 29.24, 10], [36.62, 31.2, 8], [39.92, 32.86, 10],
  [37.43, 34.88, 10], [40.33, 35.35, 8], [37.15, 37.95, 8], [37.91, 40.1, 10], [40.45, 40.9, 7.6]];

(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 432, height: 768 }, deviceScaleFactor: 2.5, isMobile: true, hasTouch: true,
    locale: "tr-TR", geolocation: { latitude: 39.92, longitude: 32.85 }, permissions: ["geolocation"] });
  await ctx.addInitScript(() => { try { localStorage.setItem("wk.kurulum", "1"); localStorage.setItem("wk.install", "kuruldu"); } catch {} });
  await ctx.route("**/api/olay", r => r.fulfill({ status: 204, body: "" }));   // kayıt ziyaret sayılmasın
  const p = await ctx.newPage();
  await p.goto("https://wattkac.com/#g=harita", { waitUntil: "networkidle" });
  await p.waitForFunction(() => typeof M !== "undefined" && M.all && M.all.length > 1000);
  await p.evaluate(() => { M.map.setView([39.2, 34.9], 6, { animate: false }); });
  await p.addStyleTag({ content: `#ders{position:fixed;left:14px;right:14px;top:118px;z-index:99999;background:rgba(15,27,61,.94);color:#fff;border-radius:16px;
    padding:12px 16px;font:700 16px/1.35 system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.25);transition:opacity .25s;pointer-events:none}
    #ders b{color:#FFD400}#ders .n{display:inline-flex;width:24px;height:24px;border-radius:50%;background:#FFD400;color:#0F1B3D;align-items:center;justify-content:center;margin-right:8px;font-size:14px}
    #dokun{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;background:rgba(255,212,0,.55);border:3px solid #FFD400;z-index:99999;pointer-events:none;opacity:0;transition:opacity .2s}` });
  await p.evaluate(() => { const d = document.createElement("div"); d.id = "ders"; d.style.opacity = 0; document.body.append(d);
    const t = document.createElement("div"); t.id = "dokun"; document.body.append(t); });
  const ders = (html, ust = 118) => p.evaluate(([h, u]) => { const d = document.getElementById("ders"); d.innerHTML = h; d.style.top = u + "px"; d.style.opacity = h ? 1 : 0; }, [html, ust]);
  const dokun = async (sel) => { const el = p.locator(sel).first(); await el.scrollIntoViewIfNeeded(); const k = await el.boundingBox();
    await p.evaluate(([x, y]) => { const t = document.getElementById("dokun"); t.style.left = x + "px"; t.style.top = y + "px"; t.style.opacity = 1; }, [k.x + k.width / 2, k.y + k.height / 2]);
    await bekle(650); await el.click(); await p.evaluate(() => document.getElementById("dokun").style.opacity = 0); };

  await p.waitForLoadState("networkidle"); await bekle(2500);   // harita döşemeleri yüklenmeden kayıt başlamasın
  const cdp = await ctx.newCDPSession(p);
  const kareler = [];
  cdp.on("Page.screencastFrame", async f => {
    const dosya = path.join(kareDir, String(kareler.length).padStart(5, "0") + ".jpg");
    fs.writeFileSync(dosya, Buffer.from(f.data, "base64")); kareler.push([dosya, f.metadata.timestamp]);
    cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
  });
  await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1080, maxHeight: 1920, everyNthFrame: 1 });
  // Kare yalnızca ekran değişince gelir; sabit sahnelerde de kare akması için görünmez bir piksel her karede değişir
  await p.evaluate(() => { const x = document.createElement("div"); x.style.cssText = "position:fixed;right:0;bottom:0;width:1px;height:1px;z-index:99999;pointer-events:none";
    document.body.append(x); let i = 0; (function f() { x.style.background = i++ % 2 ? "rgba(0,0,0,.01)" : "rgba(0,0,0,.02)"; requestAnimationFrame(f); })(); });

  await bekle(600);
  await ders(`<span class="n">1</span>wattkac.com'da <b>Kampanyalar</b> sekmesine geç`);
  await bekle(1500);
  await dokun('button[data-go="kamp"]');
  await bekle(700);
  await ders(`<span class="n">2</span>En Yakıt kampanyasında <b>Haritada gör</b>'e dokun`);
  await p.evaluate(() => { const k = document.querySelector('[data-kmap="enyakit-secili-istasyonlarda"]').closest("article, .card, li, div.kamp") || document.querySelector('[data-kmap="enyakit-secili-istasyonlarda"]').parentElement.parentElement;
    k.scrollIntoView({ behavior: "smooth", block: "center" }); k.style.transition = "box-shadow .4s"; setTimeout(() => k.style.boxShadow = "0 0 0 4px #FFD400, 0 12px 30px rgba(0,0,0,.15)", 900); });
  await bekle(2600);
  await dokun('[data-kmap="enyakit-secili-istasyonlarda"]');
  await bekle(400);
  await ders(`<span class="n">3</span>Haritada yalnızca <b>10,90 TL/kWh</b> olan 26 istasyon kalır`, 168);
  await p.evaluate(() => M.map.flyToBounds(L.latLngBounds(M.filtered.map(s => [s.lat, s.lon])).pad(.08), { duration: 1 }));
  await bekle(2800);
  await ders(`Batıdan doğuya kampanyalı noktalar`, 168);
  for (const [la, lo, z] of DURAK) {
    await p.evaluate(([la, lo, z]) => new Promise(r => { M.map.once("moveend", () => setTimeout(r, 50)); M.map.flyTo([la, lo], z, { duration: 1 }); }), [la, lo, z]);
    await bekle(lo === 32.86 ? 500 : 1100);
    if (process.env.DEBUG) { await p.screenshot({ path: path.join(cikti, `durak_${lo}.jpg`), scale: "css" }); console.log(lo, await p.evaluate(() => [M.view.length, document.querySelectorAll(".leaflet-marker-icon").length, M.map.getZoom()].join(" "))); }
    if (lo === 32.86) { // Ankara'da bir istasyonu aç
      await ders(`<span class="n">4</span>İstasyona dokun: <b>indirimli fiyat</b> ve anlık durum`, 168);
      const id = await p.evaluate(() => M.filtered.find(s => /Podium/.test(s.name)).id);
      await p.evaluate(id => selectStation(id), id);
      await bekle(4200);
      await p.evaluate(() => { M.sel = null; M.group = null; document.getElementById("v-harita").dataset.s = "peek"; renderSheet(); renderMarkers(true); });
      await ders(`Batıdan doğuya kampanyalı noktalar`, 168);
      await bekle(500);
    }
  }
  await ders(`20–30 Kasım · <b>26 noktada 10,90 TL/kWh</b>`, 168);
  await p.evaluate(() => new Promise(r => { M.map.once("moveend", () => setTimeout(r, 50)); M.map.flyToBounds(L.latLngBounds(M.filtered.map(s => [s.lat, s.lon])).pad(.08), { duration: 1.2 }); }));
  await bekle(2800);
  await cdp.send("Page.stopScreencast");
  await bekle(300);
  await b.close();

  // Değişken aralıklı kareler → 30 fps
  const liste = kareler.map(([d, t], i) => `file '${path.resolve(d)}'\nduration ${((kareler[i + 1] ? kareler[i + 1][1] : t + 0.04) - t).toFixed(4)}`).join("\n")
    + `\nfile '${path.resolve(kareler[kareler.length - 1][0])}'\n`;
  fs.writeFileSync(path.join(kareDir, "liste.txt"), liste);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", path.join(kareDir, "liste.txt"),
    "-vf", "fps=30,scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0xF3F5F9,format=yuv420p",
    "-c:v", "libx264", "-crf", "19", "-preset", "medium", path.join(cikti, "site.mp4")]);
  console.log("site kaydı:", kareler.length, "kare,", (kareler[kareler.length - 1][1] - kareler[0][1]).toFixed(1), "sn");
})();
