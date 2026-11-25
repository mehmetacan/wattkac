// wattkac.com'da otoWATT %25 indirimli 45 istasyonu bulmayı gösteren ekran kaydı (telefon, 1080×1920, açık tema).
// Kullanım: node tools/ozel/otowatt_site_kaydi.js <çıktı-klasörü>   → <klasör>/site.mp4
// Kayıt Chrome'un ekran yayınından (CDP screencast) alınır; kareler zaman damgalarıyla 30 fps videoya çevrilir.
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path"), { execFileSync } = require("child_process");

const cikti = process.argv[2];
const kareDir = path.join(cikti, "_site");
fs.rmSync(kareDir, { recursive: true, force: true }); fs.mkdirSync(kareDir, { recursive: true });
const bekle = ms => new Promise(r => setTimeout(r, ms));
// Sabit ölçekte batıdan doğuya kayış: İzmir → Adana; sonunda tek istasyona yakınlaşılır
const KAY_BAS = [38.35, 27.15], KAY_SON = [37.45, 35.0], KAY_Z = 7.4, KAY_MS = 3500;
const ACIK_AD = "Başkent Üniversitesi Hastanesi Seyhan";

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
  // Yönlendirme kartı sitenin kendi diliyle: beyaz kart, sarı numara, Plus Jakarta Sans
  await p.addStyleTag({ content: `
    #ders{position:fixed;left:12px;right:12px;top:118px;z-index:99999;display:flex;align-items:center;gap:12px;background:#fff;color:#0F1B3D;
    padding:12px 16px;border-radius:16px;font:700 17px/1.35 'Plus Jakarta Sans',system-ui,sans-serif;box-shadow:0 10px 28px rgba(15,27,61,.18);
    border:1px solid #E3E8F0;transition:opacity .25s;pointer-events:none}
    #ders b{color:#047857}#ders .g{flex:none;width:30px;height:30px;border-radius:50%;background:#FFD400;color:#0F1B3D;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px}
    #ders .y{display:block}#ders .y small{display:block;font-weight:600;font-size:14px;color:#5B6680;margin-top:1px}
    #dokun{position:fixed;width:46px;height:46px;margin:-23px 0 0 -23px;border-radius:50%;background:rgba(255,212,0,.45);border:3px solid #FFD400;z-index:99999;pointer-events:none;opacity:0;transition:opacity .2s}` });
  await p.evaluate(() => { const d = document.createElement("div"); d.id = "ders"; d.style.opacity = 0; document.body.append(d);
    const t = document.createElement("div"); t.id = "dokun"; document.body.append(t); });
  const ders = (html, ust = 118) => p.evaluate(([h, u]) => { const d = document.getElementById("ders"); d.lang = "tr"; d.innerHTML = h; d.style.top = u + "px"; d.style.opacity = h ? 1 : 0; }, [html, ust]);
  const dokun = async (sel) => { const el = p.locator(sel).first(); await el.scrollIntoViewIfNeeded(); const k = await el.boundingBox();
    await p.evaluate(([x, y]) => { const t = document.getElementById("dokun"); t.style.left = x + "px"; t.style.top = y + "px"; t.style.opacity = 1; }, [k.x + k.width / 2, k.y + k.height / 2]);
    await bekle(400); await el.click(); await p.evaluate(() => document.getElementById("dokun").style.opacity = 0); };

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

  await bekle(300);
  await ders(`<span class="g">1</span><span class="y">Kampanyalar sekmesine geç</span>`);
  await bekle(600);
  await dokun('button[data-go="kamp"]');
  await bekle(400);
  await ders(`<span class="g">2</span><span class="y">otoWATT kampanyasında “Haritada gör”e dokun</span>`);
  await p.evaluate(() => { const k = document.querySelector('[data-kmap="otowatt-secili-istasyonlarda"]').closest("article"); k.scrollIntoView({ behavior: "instant", block: "center" });
    k.style.transition = "box-shadow .4s"; setTimeout(() => k.style.boxShadow = "0 0 0 4px #FFD400, 0 12px 30px rgba(0,0,0,.15)", 150); });
  await bekle(900);
  await dokun('[data-kmap="otowatt-secili-istasyonlarda"]');
  await bekle(200);
  await ders(`<span class="g">3</span><span class="y">Haritada yalnızca kampanyalı istasyonlar kalır<small>45 istasyonda %25 indirim</small></span>`, 168);
  // Sabit ölçekte başlangıca (İzmir) gel, sonra Adana'ya kadar kesintisiz kay
  await p.evaluate(([la, lo, z]) => new Promise(r => { M.map.once("moveend", () => setTimeout(r, 250)); M.map.flyTo([la, lo], z, { duration: 0.8 }); }), [KAY_BAS[0], KAY_BAS[1], KAY_Z]);
  await bekle(250);
  await p.evaluate(([a, b, z, ms]) => new Promise(r => { const t0 = performance.now(); let son = 0;
    (function adim(t) { const u = Math.min(1, (t - t0) / ms), e = u < .5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
      M.map.setView([a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e], z, { animate: false });
      // kayarken yeni giren noktalar çizilsin
      if (t - son > 120) { son = t; refresh(); }
      if (u < 1) requestAnimationFrame(adim); else { refresh(); setTimeout(r, 150); } })(t0); }), [KAY_BAS, KAY_SON, KAY_Z, KAY_MS]);
  await ders(`<span class="g">4</span><span class="y">İstasyona dokun<small>İndirimli fiyatı ve anlık durumu gör</small></span>`, 168);
  const id = await p.evaluate(ad => (M.filtered.find(s => s.name.includes(ad)) || M.filtered[0]).id, ACIK_AD);
  await p.evaluate(id => { const s = M.byId.get(id); return new Promise(r => { M.map.once("moveend", () => setTimeout(r, 200)); M.map.flyTo([s.lat, s.lon], 15, { duration: 0.9 }); }); }, id);
  await p.evaluate(id => selectStation(id), id);
  await bekle(2300);
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
