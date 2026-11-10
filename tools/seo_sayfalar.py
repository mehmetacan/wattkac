#!/usr/bin/env python3
"""Arama motorları için statik sayfalar üretir (yayın sırasında, Cloudflare'e yüklemeden hemen önce çalışır).

Ana uygulama (site/index.html) JavaScript ile çizildiği için Google'ın içeriği okuması zor. Bu betik aynı veriden
JavaScript gerektirmeyen düz HTML sayfalar yazar:

  site/kampanyalar/index.html          güncel banka kartı ve şarj ağı kampanyaları
  site/sarj-agi/<ag>/index.html        her ağ için fiyat (TL/kWh), istasyon sayısı, geçerli kampanyalar
  site/sitemap.xml, site/robots.txt

Girdiler: data/kampanyalar.json, site/tarifeler.json, site/istasyonlar.json
Bu dosyalar depoya yazılmaz (.gitignore); her yayında yeniden üretilir. Statik dosya oldukları için worker isteği harcamaz.
"""
import datetime, html, json, pathlib, re, collections

SITE = pathlib.Path("site")
ALAN = "https://wattkac.com"
ALL = "Tüm şarj istasyonları"
AY = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
TRT = str.maketrans({"İ": "i", "I": "ı"})
e = lambda s: html.escape(str(s or ""), quote=True)


def fold(s):
    s = (s or "").translate(TRT).lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c"), ("â", "a"), ("î", "i")):
        s = s.replace(a, b)
    return s


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


def tarih(iso):
    try:
        y, m, d = iso.split("-")
        return f"{int(d)} {AY[int(m) - 1]} {y}"
    except Exception:  # noqa: BLE001
        return iso or ""


def tl(v):
    return f"{v:.2f}".replace(".", ",")


# Ağ adı → istasyon verisindeki marka adının sadeleştirilmiş başı
AG_ANAHTAR = {"Eşarj": "esarj", "ASTOR Şarj": "astor", "Trugo": "trugo", "ZES": "zes", "Voltrun": "voltrun", "Otopriz": "otopriz",
              "Ovolt": "ovolt", "Shell Recharge": "shell", "WAT Mobilite": "wat", "Voltla": "voltla"}

CSS = """*{box-sizing:border-box;margin:0;padding:0}body{background:#F6F7F9;color:#111827;font:16px/1.6 Inter,system-ui,-apple-system,Segoe UI,sans-serif;-webkit-font-smoothing:antialiased}
a{color:#1D4ED8}.w{max-width:760px;margin:0 auto;padding:0 16px 48px}
header{display:flex;align-items:center;gap:10px;padding:14px 0}header a.logo{display:flex;align-items:center;gap:6px;text-decoration:none;color:#111827;font-weight:900;font-size:20px;letter-spacing:-.3px}
header a.logo b{color:#E0A100}header .sp{flex:1}header a.cta{background:#FFC800;color:#111827;text-decoration:none;font-weight:800;border-radius:999px;padding:8px 14px;font-size:14px}
nav.bc{font-size:13px;color:#6B7280;margin:4px 0 10px}nav.bc a{color:#6B7280}
h1{font-size:28px;line-height:1.2;letter-spacing:-.5px;margin:6px 0 8px}h2{font-size:19px;margin:26px 0 10px;letter-spacing:-.2px}
p.lead{color:#4B5563;margin-bottom:14px}.card{background:#fff;border:1px solid #E5E7EB;border-radius:14px;padding:14px 16px;margin-bottom:10px}
.card h3{font-size:16px;margin-bottom:2px}.big{font-weight:800;color:#047857}.mut{color:#6B7280;font-size:14px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #E5E7EB;border-radius:14px;overflow:hidden}
th,td{padding:10px 12px;border-bottom:1px solid #F3F4F6;text-align:left}th{font-size:13px;color:#6B7280;font-weight:700}td.n{font-weight:800;white-space:nowrap}
ul.ag{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px}ul.ag a{display:block;background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:10px 12px;text-decoration:none;color:#111827;font-weight:700}
ul.ag small{display:block;color:#6B7280;font-weight:500}footer{margin-top:28px;font-size:13px;color:#6B7280}
.btn{display:inline-block;background:#111827;color:#fff;text-decoration:none;font-weight:800;border-radius:12px;padding:11px 16px;margin:6px 6px 0 0}"""

BEACON = """<script>(function(){try{var r=document.referrer?new URL(document.referrer).hostname:"",ua=navigator.userAgent,k=/Instagram/i.test(ua)||/instagram/.test(r)?"instagram":/google\\./.test(r)?"google":/bing\\.|yandex\\.|duckduckgo/.test(r)?"diğer arama":!r||r===location.hostname?"doğrudan":r.replace(/^www\\./,"");
var b=JSON.stringify({e:[["seo_sayfa",location.pathname,1],["kaynak",k,1]]});if(location.protocol==="https:")navigator.sendBeacon?navigator.sendBeacon("/api/olay",b):fetch("/api/olay",{method:"POST",body:b,keepalive:true});}catch(x){}})();</script>"""


def sayfa(yol, baslik, aciklama, govde, jsonld=None, bc=None):
    url = ALAN + yol
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (jsonld or []))
    bct = ""
    if bc:
        bct = '<nav class="bc" aria-label="Konum">' + " › ".join(f'<a href="{e(u)}">{e(t)}</a>' if u else e(t) for t, u in bc) + "</nav>"
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(baslik)}</title><meta name="description" content="{e(aciklama)}"><link rel="canonical" href="{e(url)}">
<meta property="og:type" content="website"><meta property="og:site_name" content="WattKaç"><meta property="og:title" content="{e(baslik)}">
<meta property="og:description" content="{e(aciklama)}"><meta property="og:url" content="{e(url)}"><meta property="og:image" content="{ALAN}/og.png">
<meta property="og:locale" content="tr_TR"><meta name="twitter:card" content="summary_large_image"><link rel="icon" href="/icons/favicon-32.png" sizes="32x32">
<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png"><meta name="theme-color" content="#ffffff"><style>{CSS}</style>{ld}</head>
<body><div class="w"><header><a class="logo" href="/"><svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M13.5 2 4 13.5h6.2L9.5 22 20 9.8h-6.4z" fill="#FFC800" stroke="#E0A100" stroke-width="1" stroke-linejoin="round"/></svg><span>Watt<b>Kaç</b></span></a>
<span class="sp"></span><a class="cta" href="/">Haritayı aç</a></header>{bct}{govde}
<footer>Bilgiler bankaların ve şarj ağlarının resmi sayfalarından derlenir; koşullar değişebilir, katılmadan önce resmi sayfadan kontrol edin.
WattKaç hiçbir banka veya şarj ağıyla bağlantılı değildir; reklam veya iş birliği değildir. · <a href="/kampanyalar/">Tüm kampanyalar</a> · <a href="/sarj-agi/">Şarj ağları</a></footer>
</div>{BEACON}</body></html>"""


def aktif(o, bugun):
    return not o.get("bit") or o["bit"] >= bugun


def main():
    D = json.loads((pathlib.Path("data/kampanyalar.json")).read_text(encoding="utf-8"))
    T = json.loads((SITE / "tarifeler.json").read_text(encoding="utf-8"))["aglar"]
    J = json.loads((SITE / "istasyonlar.json").read_text(encoding="utf-8"))
    bugun = datetime.date.today().isoformat()
    guncel = D.get("guncelleme") or bugun
    donem = D.get("donem") or ""

    say = collections.Counter()
    for r in J["istasyonlar"]:
        b = fold(r.get("b") or "")
        for ag, k in AG_ANAHTAR.items():
            if b.startswith(k):
                say[ag] += 1
    toplam = len(J["istasyonlar"])

    # Kampanyaları ağ başına topla
    banka_teklif = []  # (banka, teklif)
    for b in D["bankalar"]:
        for o in b.get("offers", []):
            if aktif(o, bugun):
                banka_teklif.append((b, o))
    ag_kayit = {x["name"]: x for x in D["istasyonlar"]}
    aglar = sorted(set(AG_ANAHTAR) | set(ag_kayit), key=lambda a: -say.get(a, 0))

    def ag_kampanyalari(ag):
        own = [o for o in ag_kayit.get(ag, {}).get("own", []) if aktif(o, bugun)]
        bank = [(b, o) for b, o in banka_teklif if ag in o.get("st", []) or ALL in o.get("st", [])]
        return own, bank

    yazilan = []

    def yaz(yol, icerik):
        p = SITE / yol.strip("/") / "index.html" if yol.endswith("/") else SITE / yol.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(icerik, encoding="utf-8")
        yazilan.append(yol)

    def teklif_kart(baslik, o, alt=""):
        tarihler = f"Son gün: {e(o.get('son'))}" if o.get("son") else ""
        dogrulama = ' <span class="mut">(doğrulanıyor: resmi sayfadan teyit edin)</span>' if o.get("kontrol") else ""
        return (f'<div class="card"><h3>{e(baslik)} · <span class="big">{e(o.get("big"))}</span>{dogrulama}</h3>'
                f'<div>{e(o.get("det"))}</div>{f"<div class=mut>{e(alt)}</div>" if alt else ""}'
                f'<div class="mut">{tarihler}{" · " if tarihler and o.get("join") else ""}{e(o.get("join"))}</div>'
                + (f'<div class="mut" style="margin-top:4px">{e(o.get("kosul"))}</div>' if o.get("kosul") else "")
                + (f'<a href="{e(o["link"])}" rel="nofollow noopener" target="_blank">Resmi kampanya sayfası ↗</a>' if o.get("link") else "")
                + "</div>")

    # ---- Ağ sayfaları
    ag_listesi = []
    for ag in aglar:
        s = slug(ag)
        tar = T.get(ag) or {}
        own, bank = ag_kampanyalari(ag)
        n = say.get(ag, 0)
        if not (tar.get("ac") or tar.get("dc") or own or bank):
            continue
        satir = []
        for tur in ("ac", "dc"):
            p = tar.get(tur)
            if not p:
                continue
            fiyat = tl(p["min"]) if p.get("min") == p.get("max") else f"{tl(p['min'])} – {tl(p['max'])}"
            ek = ""
            if p.get("saatli"):
                ek = "; " + ", ".join(f"{z['bas']}–{z.get('etiket', z['bit'])} {tl(z['v'])} TL" for z in p["saatli"])
                ek += " (yalnızca duyurulan istasyonlarda)" if p.get("saatli_liste") else ""
            satir.append(f'<tr><td>{tur.upper()}{" (hızlı)" if tur == "dc" else ""}</td><td class="n">{fiyat} TL/kWh</td><td class="mut">{e(ek.lstrip("; "))}</td></tr>')
        fiyat_html = ""
        if satir:
            fiyat_html = (f'<h2>{e(ag)} kWh fiyatı</h2><table><tr><th>Tür</th><th>Fiyat</th><th>Not</th></tr>{"".join(satir)}</table>'
                          f'<p class="mut" style="margin-top:6px">{e(tar.get("not"))}'
                          + (f' Son kontrol: {tarih(tar["kontrol"])}.' if tar.get("kontrol") else "")
                          + (f' <a href="{e(tar["kaynak"])}" rel="nofollow noopener" target="_blank">Resmi fiyat sayfası ↗</a>' if tar.get("kaynak") else "") + "</p>")
        kamp_html = ""
        if own:
            kamp_html += f"<h2>{e(ag)} kendi kampanyaları</h2>" + "".join(teklif_kart(ag, o) for o in own)
        if bank:
            kamp_html += f"<h2>{e(ag)} istasyonlarında geçerli kredi kartı kampanyaları</h2>" + "".join(
                teklif_kart(b["name"], o, b.get("sub", "")) for b, o in bank)
        if not kamp_html:
            kamp_html = f"<h2>Kampanyalar</h2><p>Şu an {e(ag)} için bildiğimiz geçerli bir kampanya yok.</p>"
        fiyat_ozet = ""
        if tar.get("dc"):
            fiyat_ozet = f"DC {tl(tar['dc']['max'])} TL/kWh"
        if tar.get("ac"):
            fiyat_ozet = (f"AC {tl(tar['ac']['max'])}" + (", " + fiyat_ozet if fiyat_ozet else " TL/kWh"))
        baslik = f"{ag} şarj fiyatı ve kampanyaları ({donem}) · WattKaç"
        aciklama = (f"{ag} elektrikli araç şarj fiyatı" + (f": {fiyat_ozet}" if fiyat_ozet else "") +
                    f". {ag} istasyonlarında geçerli {len(own) + len(bank)} kampanya" + (f", Türkiye'de {n} istasyon" if n else "") + ". Resmi kaynaklardan, her gün güncellenir.")
        govde = (f"<h1>{e(ag)} şarj fiyatı ve kampanyaları</h1><p class='lead'>{e(donem)} itibarıyla {e(ag)} istasyonlarında kWh fiyatı ve kredi kartıyla "
                 f"kazanabileceğin indirimler." + (f" Haritamızda {n} {e(ag)} istasyonu var." if n else "") + "</p>"
                 f'<a class="btn" href="/">Yakınımdaki istasyonları gör</a><a class="btn" style="background:#fff;color:#111827;border:1px solid #E5E7EB" href="/#g=kamp&amp;ag={e(ag)}">Kampanyaları uygulamada aç</a>'
                 + fiyat_html + kamp_html + f'<p class="mut" style="margin-top:14px">Son güncelleme: {tarih(guncel)}</p>')
        ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "WattKaç", "item": ALAN + "/"},
            {"@type": "ListItem", "position": 2, "name": "Şarj ağları", "item": ALAN + "/sarj-agi/"},
            {"@type": "ListItem", "position": 3, "name": ag, "item": f"{ALAN}/sarj-agi/{s}/"}]}]
        yaz(f"/sarj-agi/{s}/", sayfa(f"/sarj-agi/{s}/", baslik, aciklama, govde, ld,
                                    [("WattKaç", "/"), ("Şarj ağları", "/sarj-agi/"), (ag, None)]))
        ag_listesi.append((ag, s, n, fiyat_ozet, len(own) + len(bank)))

    # ---- Ağlar dizini
    li = "".join(f'<li><a href="/sarj-agi/{s}/">{e(a)}<small>{e(f) or "fiyat bilgisi yok"}{f" · {k} kampanya" if k else ""}</small></a></li>'
                 for a, s, n, f, k in ag_listesi)
    yaz("/sarj-agi/", sayfa("/sarj-agi/", f"Şarj ağları: kWh fiyatları ve kampanyalar ({donem}) · WattKaç",
                            "Trugo, ZES, Eşarj, Voltrun, Otopriz, Ovolt, Shell Recharge, WAT Mobilite ve diğer şarj ağlarının güncel kWh fiyatları ve kampanyaları.",
                            f"<h1>Şarj ağları</h1><p class='lead'>Türkiye'deki elektrikli araç şarj ağlarının güncel kWh fiyatları ve geçerli kampanyaları. "
                            f"Haritamızda toplam {toplam:,} istasyon var.</p>".replace(",", ".") + f'<ul class="ag">{li}</ul>',
                            None, [("WattKaç", "/"), ("Şarj ağları", None)]))

    # ---- Kampanyalar sayfası
    kart = []
    for b in D["bankalar"]:
        tek = [o for o in b.get("offers", []) if aktif(o, bugun)]
        if not tek:
            continue
        kart.append(f"<h2>{e(b['name'])}</h2>" + "".join(
            teklif_kart(b["name"], o, "Geçerli ağlar: " + ", ".join(o.get("st", []))) for o in tek))
    for a in D["istasyonlar"]:
        own = [o for o in a.get("own", []) if aktif(o, bugun)]
        if own:
            kart.append(f"<h2>{e(a['name'])}</h2>" + "".join(teklif_kart(a["name"], o) for o in own))
    adet = sum(1 for b in D["bankalar"] for o in b.get("offers", []) if aktif(o, bugun)) + \
        sum(1 for a in D["istasyonlar"] for o in a.get("own", []) if aktif(o, bugun))
    yaz("/kampanyalar/", sayfa("/kampanyalar/", f"Elektrikli araç şarj kampanyaları ({donem}) · WattKaç",
                               f"{donem} geçerli {adet} elektrikli araç şarj kampanyası: kredi kartı bonus, iade ve indirimleri ile şarj ağlarının kendi kampanyaları. Resmi kaynaklardan, her gün güncellenir.",
                               f"<h1>Elektrikli araç şarj kampanyaları</h1><p class='lead'>{e(donem)} geçerli {adet} kampanya. Hangi kartla hangi şarj ağında ne kazanırsın? "
                               f"Her kampanya, kampanyayı yapan banka ya da şarj ağının resmi sayfasına bağlanır.</p>"
                               f'<a class="btn" href="/#g=kamp">Kartıma uyanları uygulamada filtrele</a>' + "".join(kart)
                               + f'<p class="mut" style="margin-top:14px">Son güncelleme: {tarih(guncel)}</p>',
                               None, [("WattKaç", "/"), ("Kampanyalar", None)]))

    # ---- sitemap & robots
    urls = ["/"] + yazilan
    sm = "".join(f"<url><loc>{ALAN}{u}</loc><lastmod>{guncel}</lastmod><changefreq>daily</changefreq><priority>{'1.0' if u == '/' else '0.8' if u in ('/kampanyalar/', '/sarj-agi/') else '0.6'}</priority></url>" for u in urls)
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding="utf-8")
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /panel\nDisallow: /api/\n\nSitemap: {ALAN}/sitemap.xml\n", encoding="utf-8")
    print(f"SEO: {len(yazilan)} statik sayfa, sitemap {len(urls)} adres")


if __name__ == "__main__":
    main()
