// wattkac.com'da otoWATT %25 indirimli 45 istasyonu bulmayı gösteren ekran kaydı (telefon, 1080×1920, açık tema).
// Kullanım: node tools/ozel/otowatt_site_kaydi.js <çıktı-klasörü>   → <klasör>/site.mp4
// Kayıt Chrome'un ekran yayınından (CDP screencast) alınır; kareler zaman damgalarıyla 30 fps videoya çevrilir.
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path"), { execFileSync } = require("child_process");

const cikti = process.argv[2];
const kareDir = path.join(cikti, "_site");
fs.rmSync(kareDir, { recursive: true, force: true }); fs.mkdirSync(kareDir, { recursive: true });
const bekle = ms => new Promise(r => setTimeout(r, ms));
const DURAK = [ // batıdan doğuya: [enlem, boylam, yakınlık]
  [38.62, 27.08, 9.3], [37.03, 27.4, 11], [37.83, 27.45, 9.2], [38.85, 27.65, 9], [37.2, 28.36, 11.5], [36.63, 29.12, 12],
  [37.79, 29.07, 11], [36.5, 32.1, 12], [37.93, 32.5, 12], [39.81, 32.78, 12], [37.0, 35.24, 11.3]];
const ACIK = 29.07;   // bu durakta bir istasyon açılır (Denizli)

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
  await p.addStyleTag({ content: `@import url('https://fonts.googleapis.com/css2?family=Anton&display=block');
    #ders{position:fixed;left:0;right:0;top:118px;z-index:99999;background:rgba(15,27,61,.94);color:#fff;
    padding:12px 18px 14px;font:800 17px/1.3 'Plus Jakarta Sans',system-ui,sans-serif;border-top:3px solid #FFD400;border-bottom:3px solid #FFD400;
    box-shadow:0 8px 24px rgba(18,5,31,.35);transition:opacity .25s;pointer-events:none}
    #ders b{color:#FFD24A}#ders .g{display:inline-block;font:400 18px/1 Anton,Impact,sans-serif;letter-spacing:1.5px;background:#FFD400;color:#0F1B3D;padding:5px 12px 6px;border-radius:6px;margin:0 10px 6px 0}
    #ders .y{display:block;font:400 25px/1.1 Anton,Impact,sans-serif;letter-spacing:.5px;text-transform:uppercase}
    #bitti{position:fixed;inset:0;z-index:99998;display:flex;flex-direction:column;align-items:center;justify-content:center;background:rgba(18,5,31,.55);opacity:0;transition:opacity .35s;pointer-events:none}
    #bitti .bb{width:100%;text-align:center;background:linear-gradient(90deg,transparent,rgba(18,5,31,.92) 15%,rgba(18,5,31,.92) 85%,transparent);padding:20px 0 24px}
    #bitti .t{padding:10px 0 2px;font:400 50px/1.2 Anton,Impact,sans-serif;letter-spacing:1px;text-transform:uppercase;color:#FFD400}
    #bitti .s{font:800 19px/1.3 'Plus Jakarta Sans',system-ui,sans-serif;color:#fff;margin-top:10px}#bitti .s b{color:#5EF0FF}
    #dokun{position:fixed;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;background:rgba(255,212,0,.5);border:3px solid #FFD400;box-shadow:0 0 14px #FFD400;z-index:99999;pointer-events:none;opacity:0;transition:opacity .2s}` });
  await p.evaluate(() => { const d = document.createElement("div"); d.id = "ders"; d.style.opacity = 0; document.body.append(d);
    const e = document.createElement("div"); e.id = "bitti"; e.lang = "tr"; e.innerHTML = '<div class="bb"><div class="t">45 istasyonda %25 indirim</div><div class="s">otoWATT · <b>25 Kasım – 24 Aralık</b></div></div>'; document.body.append(e);
    const t = document.createElement("div"); t.id = "dokun"; document.body.append(t); });
  const ders = (html, ust = 118) => p.evaluate(([h, u]) => { const d = document.getElementById("ders"); d.lang = "tr"; d.innerHTML = h; d.style.top = u + "px"; d.style.opacity = h ? 1 : 0; }, [html, ust]);
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
  await ders(`<span class="g">ADIM 1</span><span class="y">Kampanyalar sekmesine geç</span>`);
  await bekle(1500);
  await dokun('button[data-go="kamp"]');
  await bekle(700);
  await ders(`<span class="g">ADIM 2</span><span class="y">otoWATT'ta “Haritada gör”e dokun</span>`);
  await p.evaluate(() => { const k = document.querySelector('[data-kmap="otowatt-secili-istasyonlarda"]').closest("article, .card, li, div.kamp") || document.querySelector('[data-kmap="otowatt-secili-istasyonlarda"]').parentElement.parentElement;
    k.scrollIntoView({ behavior: "smooth", block: "center" }); k.style.transition = "box-shadow .4s"; setTimeout(() => k.style.boxShadow = "0 0 0 4px #FFD400, 0 12px 30px rgba(0,0,0,.15)", 900); });
  await bekle(2600);
  await dokun('[data-kmap="otowatt-secili-istasyonlarda"]');
  await bekle(400);
  await ders(`<span class="g">ADIM 3</span><span class="y">45 istasyon haritada</span><b>%25 indirimli</b> noktalar kalır`, 168);
  await p.evaluate(() => M.map.flyToBounds(L.latLngBounds(M.filtered.map(s => [s.lat, s.lon])).pad(.08), { duration: 1 }));
  await bekle(2800);
  await ders(`<span class="y">Batıdan doğuya 45 istasyon</span>`, 168);
  for (const [la, lo, z] of DURAK) {
    await p.evaluate(([la, lo, z]) => new Promise(r => { M.map.once("moveend", () => setTimeout(r, 50)); M.map.flyTo([la, lo], z, { duration: 1 }); }), [la, lo, z]);
    await bekle(lo === ACIK ? 500 : 1100);
    if (process.env.DEBUG) { await p.screenshot({ path: path.join(cikti, `durak_${lo}.jpg`), scale: "css" }); console.log(lo, await p.evaluate(() => [M.view.length, document.querySelectorAll(".leaflet-marker-icon").length, M.map.getZoom()].join(" "))); }
    if (lo === ACIK) { // Ankara'da bir istasyonu aç
      await ders(`<span class="g">ADIM 4</span><span class="y">İstasyona dokun</span><b>İndirimli fiyat</b> ve anlık durum`, 168);
      const id = await p.evaluate(() => (M.filtered.find(s => /Marlen Hotel Denizli/.test(s.name)) || M.filtered[0]).id);
      await p.evaluate(id => selectStation(id), id);
      await bekle(4200);
      await p.evaluate(() => { M.sel = null; M.group = null; document.getElementById("v-harita").dataset.s = "peek"; renderSheet(); renderMarkers(true); });
      await ders(`<span class="y">Batıdan doğuya 45 istasyon</span>`, 168);
      await bekle(500);
    }
  }
  await ders("", 168);
  await p.evaluate(() => new Promise(r => { M.map.once("moveend", () => setTimeout(r, 50)); M.map.flyToBounds(L.latLngBounds(M.filtered.map(s => [s.lat, s.lon])).pad(.08), { duration: 1.2 }); }));
  await bekle(900);
  await p.evaluate(() => document.getElementById("bitti").style.opacity = 1);
  await bekle(2600);
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
