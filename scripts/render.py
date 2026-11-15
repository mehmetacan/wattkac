"""data/kampanyalar.json dosyasından tüm Instagram görsellerini üretir.

Post türleri: banka (kart kampanyaları + o kartla geçerli uygulama kampanyaları), şarj ağı (yalnızca ağın kendi indirimi),
uygulama (birçok ağda geçerli, uygulamadan başlatılan şarjdaki kart koşulsuz kampanya; ör. Rotawatt).

Çıktı: media/<etiket>/<post_id>/{1_kapak,2_detay}.jpg ve hikaye.jpg
Kullanım: python scripts/render.py --etiket 2026-11
Gereksinim: google-chrome (veya chromium) ve Pillow.
"""
import argparse, html, json, os, shutil, subprocess, tempfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = "Tüm şarj istasyonları"
BOLT = '<svg viewBox="0 0 24 24" width="{s}" height="{s}"><path d="M13.5 2 4 13.5h6.2L9.5 22 20 9.8h-6.4z" fill="{c}"/></svg>'
NAME_BREAK = {"Ziraat Bankası": "Ziraat<br>Bankası", "Garanti BBVA": "Garanti<br>BBVA", "Kuveyt Türk": "Kuveyt<br>Türk",
              "Shell Recharge": "Shell<br>Recharge", "WAT Mobilite": "WAT<br>Mobilite", "Yapı Kredi": "Yapı<br>Kredi",
              "ON Dijital": "ON<br>Dijital"}


def son_txt(son, prefix):
    """'30 Kasım' → 'Son gün: 30 Kasım'; tarihsiz metinler olduğu gibi."""
    return f"{prefix}{son}" if son[:1].isdigit() else son


def esc(s):
    return html.escape(str(s), quote=True)


def chrome_bin():
    for b in ["google-chrome", "chromium", "chromium-browser", "google-chrome-stable"]:
        if shutil.which(b):
            return b
    raise SystemExit("Chrome/Chromium bulunamadı")


def shot(page, out_jpg, W, H):
    os.makedirs(os.path.dirname(out_jpg), exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        hp, png = os.path.join(td, "p.html"), os.path.join(td, "p.png")
        open(hp, "w", encoding="utf-8").write(page)
        subprocess.run([chrome_bin(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", f"--window-size={W},{H}", f"--screenshot={png}",
                        "--virtual-time-budget=1500", "file://" + hp],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        Image.open(png).convert("RGB").save(out_jpg, "JPEG", quality=92, optimize=True)


# ------------------------------------------------------------------ detay / hikaye şablonu
def base_css(W, H, story):
    pt, pb, px = (215, 250, 80) if story else (64, 60, 68)
    return f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;background:#0A1020;font-family:'Inter',sans-serif;color:#F4F6FB;overflow:hidden}}
.wrap{{width:{W}px;height:{H}px;padding:{pt}px {px}px {pb}px;display:flex;flex-direction:column;
 background:radial-gradient(900px 700px at 90% -5%, rgba(255,212,0,.18), transparent 60%),
            radial-gradient(800px 700px at -10% 105%, rgba(34,227,160,.13), transparent 60%),#0A1020}}
.brand{{display:flex;align-items:center;gap:12px;font-weight:800;font-size:40px;letter-spacing:-.5px}}
.brand b{{color:#FFD400}}
.tag{{margin-left:auto;font-size:24px;font-weight:600;color:#9FB0D0;border:2px solid #263353;border-radius:999px;padding:7px 20px}}
.h1{{margin-top:{60 if story else 34}px;font-size:{86 if story else 76}px;font-weight:900;letter-spacing:-2px;line-height:1}}
.h2{{margin-top:10px;font-size:30px;color:#22E3A0;font-weight:700}}
.offers{{margin-top:{40 if story else 26}px;display:flex;flex-direction:column;gap:{22 if story else 16}px}}
.of{{background:rgba(255,255,255,.045);border:2px solid #202C4A;border-radius:24px;padding:{26 if story else 20}px 28px}}
.ot{{display:flex;justify-content:space-between;align-items:baseline;gap:16px}}
.big{{font-size:{54 if story else 46}px;font-weight:900;color:#FFD400;letter-spacing:-1px;line-height:1.05}}
.son{{flex:none;font-size:22px;font-weight:800;color:#0A1020;background:#FFD400;border-radius:12px;padding:6px 14px}}
.det{{margin-top:8px;font-size:{30 if story else 27}px;font-weight:600;line-height:1.3}}
.lbl{{margin-top:14px;font-size:20px;font-weight:700;color:#8394B8;letter-spacing:1px;text-transform:uppercase}}
.chips{{margin-top:8px;display:flex;flex-wrap:wrap;gap:8px}}
.chip{{font-size:{24 if story else 22}px;font-weight:700;color:#DDE6F7;background:#16213D;border:2px solid #2A3961;border-radius:999px;padding:5px 15px}}
.chip.all{{color:#0A1020;background:#22E3A0;border-color:#22E3A0}}
.join{{margin-top:12px;font-size:{23 if story else 21}px;color:#9FB0D0;font-weight:500}}
.join b{{color:#F4F6FB}}
.spacer{{flex:1;min-height:20px}}
.note{{font-size:24px;color:#C9D4EA;font-weight:600;line-height:1.35;background:rgba(34,227,160,.08);border:2px solid rgba(34,227,160,.35);border-radius:20px;padding:16px 22px}}
.note b{{color:#22E3A0}}
.foot{{margin-top:16px;font-size:21px;color:#8394B8;line-height:1.4}}
.foot b{{color:#C9D4EA}}
.empty{{font-size:30px;color:#9FB0D0;font-weight:600}}
.row{{display:flex;justify-content:space-between;align-items:center;gap:16px;background:rgba(255,255,255,.045);border:2px solid #202C4A;border-radius:20px;padding:{18 if story else 15}px 24px}}
.rk{{font-size:{30 if story else 27}px;font-weight:800}}
.rv{{font-size:{27 if story else 24}px;font-weight:700;color:#FFD400;text-align:right}}
"""


def foot(d):
    return (f'<div class="foot">Güncelleme: {esc(d["guncelleme_txt"])} · Koşullar değişebilir, '
            '<b>katılmadan önce resmi kanallardan kontrol edin.</b> @wattkac</div>')


def chips(st):
    return "".join(f'<span class="chip{" all" if s == ALL else ""}">{esc(s)}</span>' for s in st)


def brand(tag):
    return f'<div class="brand">{BOLT.format(s=46, c="#FFD400")}<span>Watt<b>Kaç</b></span><span class="tag">{esc(tag)}</span></div>'


GUNLER = ["pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar"]
GUN_AD = {"pazartesi": "pazartesi", "sali": "salı", "carsamba": "çarşamba", "persembe": "perşembe", "cuma": "cuma",
          "cumartesi": "cumartesi", "pazar": "pazar"}


def gun_txt(o):
    """'gunler': ["sali"] → 'Her salı'; gün koşulu yoksa boş."""
    g = [GUN_AD[x] for x in GUNLER if x in (o.get("gunler") or [])]
    if not g or len(g) == 7:
        return ""
    return "Her " + (", ".join(g[:-1]) + " ve " + g[-1] if len(g) > 1 else g[0])


def banka_teklifleri(d, b):
    """Bankanın teklifleri + o bankanın kartıyla geçerli uygulama kampanyaları ("kart": banka id; ör. Shell Recharge + Garanti).
    Kampanya veride tek kayıttır (uygulamalar altında); kart koşullu olduğu için postu banka postudur, uygulama postunda tekrar edilmez."""
    app = [o for u in d.get("uygulamalar", []) for o in u.get("offers", []) if o.get("kart") == b["id"]]
    return app + list(b["offers"])


def uygulama_teklifleri(u):
    """Uygulama postuna giren teklifler: kart koşulu olmayanlar (kartlılar ilgili banka postunda)."""
    return [o for o in u.get("offers", []) if not o.get("kart")]


def bank_html(b, d, story):
    W, H = (1080, 1920) if story else (1080, 1350)
    offers = ""
    for o in banka_teklifleri(d, b):
        lbl = "Geçerli istasyonlar" if o["st"] != [ALL] else "Nerede geçerli"
        offers += (f'<div class="of"><div class="ot"><div class="big">{esc(o["big"])}</div><div class="son">{esc(son_txt(o["son"], "Son: "))}</div></div>'
                   f'<div class="det">{esc(o["det"])}</div><div class="lbl">{lbl}</div><div class="chips">{chips(o["st"])}</div>'
                   f'<div class="join">Katılım: <b>{esc(o["join"])}</b></div></div>')
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{base_css(W, H, story)}</style></head><body><div class="wrap">'
            f'{brand("Banka · " + d["donem"])}<div class="h1">{esc(b["name"])}</div><div class="h2">{esc(b["sub"])}</div>'
            f'<div class="offers">{offers}</div><div class="spacer"></div>{foot(d)}</div></body></html>')


def app_html(u, d, story):
    """Uygulama postu: birçok ağda geçerli, uygulamadan başlatılan şarjdaki kampanya + geçerli ağlar + gün koşulu."""
    W, H = (1080, 1920) if story else (1080, 1350)
    offers = ""
    for o in uygulama_teklifleri(u):
        gt = gun_txt(o)
        offers += (f'<div class="of"><div class="ot"><div class="big">{esc(o["big"])}</div><div class="son">{esc(son_txt(o["son"], "Son: "))}</div></div>'
                   f'<div class="det">{esc(o["det"])}</div>'
                   + (f'<div class="gun">{esc(gt)}</div>' if gt else "")
                   + f'<div class="lbl">Geçerli şarj ağları ({len(o["st"])})</div><div class="chips">{chips(o["st"])}</div>'
                   + (f'<div class="join">Katılım: <b>{esc(o["join"])}</b></div>' if o.get("join") else "") + '</div>')
    css = base_css(W, H, story) + (".gun{margin-top:12px;display:inline-block;font-size:26px;font-weight:900;color:#0A1020;background:#22E3A0;"
                                   "border-radius:12px;padding:6px 16px}")
    if not story:
        css += ".h1{margin-top:24px}.offers{margin-top:20px}.chip{font-size:19px;padding:3px 12px}.chips{gap:6px}"
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="wrap">'
            f'{brand("Uygulama · " + d["donem"])}<div class="h1">{esc(u["name"])}</div><div class="h2">{esc(u.get("sub", ""))}</div>'
            f'<div class="offers">{offers}</div><div class="spacer"></div>'
            f'<div class="note">İndirim, şarjı <b>{esc(u["name"])} uygulamasından</b> başlatıp ödeyince geçerli.</div>'
            f'{foot(d)}</div></body></html>')


# ------------------------------------------------------------------ uygulama postu: fiyat tablolu düzen
# Teklifte "fiyatlar" varsa (kampanya sahibinin kendi tablosu: {"kaynak", "tarih", "not"?, "satirlar": [{"ag", "ac": [liste, kampanya] | null,
# "dc": [...]}]}) post fiyat odaklı üretilir: kapak (en ucuz 3 DC), fiyat tablosu slaytları, katılım slaydı, hikâye (en ucuz 5 DC).
TABLO_SATIR = 13  # slayt başına en fazla satır (1080×1350'de ~30px yazıyla okunaklı sığan)


def tl(v):
    return f"{v:.2f}".replace(".", ",")


def kadar(son):
    """'31 Aralık' → "31 Aralık'a kadar" (Eylül/Ekim → 'e)."""
    if not son[:1].isdigit():
        return son
    return f"{son}'{'e' if son.split()[-1] in ('Eylül', 'Ekim') else 'a'} kadar"


def fiyat_satirlari(o):
    """Tablo satırları, DC kampanya fiyatına göre ucuzdan pahalıya (DC'si olmayan sona, AC'ye göre)."""
    rows = list((o.get("fiyatlar") or {}).get("satirlar") or [])
    return sorted(rows, key=lambda r: (r.get("dc") is None, (r.get("dc") or r.get("ac") or [0, 99])[1], r["ag"]))


def bolumler(rows, n=TABLO_SATIR):
    """Satırları en fazla n'lik, olabildiğince eşit slaytlara böler (25 → 13 + 12)."""
    k = max(1, -(-len(rows) // n))
    boy = -(-len(rows) // k)
    return [rows[i:i + boy] for i in range(0, len(rows), boy)]


def indirimli(big):
    """'%20 indirim' → '%20 indirimli'; başka biçimde olduğu gibi."""
    return big + "li" if big.endswith("indirim") else big


def fiyat_hucre(p, cls):
    if not p:
        return f'<div class="pc {cls} yok">—</div>'
    return f'<div class="pc {cls}"><s>{tl(p[0])}</s><span class="ok">→</span><b>{tl(p[1])}</b></div>'


APP_CSS = """
.top{display:flex;align-items:center;gap:12px;font-size:38px;font-weight:800}
.top b{color:#FFD400}
.pill{margin-left:auto;font-size:28px;font-weight:900;letter-spacing:3px;color:#0A1020;background:#22E3A0;border-radius:12px;padding:9px 20px}
.app{font-size:44px;font-weight:800;color:#22E3A0;letter-spacing:-.5px}
.gun{font-weight:900;letter-spacing:-7px;line-height:.9;text-transform:uppercase;color:#F4F6FB}
.ind{align-self:flex-start;background:#FFD400;color:#0A1020;font-weight:900;letter-spacing:-2px;text-transform:uppercase;border-radius:24px}
.vl{font-size:26px;font-weight:800;color:#8394B8;letter-spacing:2px;text-transform:uppercase}
.vl span{text-transform:none;letter-spacing:1px}
.vit{display:flex;flex-direction:column}
.vr{display:flex;align-items:center;gap:22px;background:rgba(255,255,255,.05);border:2px solid #24304F;border-radius:26px}
.vr .n{flex:1;font-weight:800;letter-spacing:-.5px;white-space:nowrap}
.vr .ak{font-weight:800;color:#8394B8}
.vr s{color:#7D8BA8;font-weight:700;text-decoration-thickness:3px}
.vr b{color:#FFD400;font-weight:900;letter-spacing:-2px}
.vr.ilk{border-color:#FFD400;background:rgba(255,212,0,.09)}
.alt{display:flex;justify-content:space-between;align-items:center;font-weight:800}
.alt span:last-child{color:#9FB0D0;font-weight:700}
"""


def app_cover_fiyat_html(u, o, d):
    rows = [r for r in fiyat_satirlari(o) if r.get("dc")][:3]
    gt = gun_txt(o) or o["big"]
    vit = "".join(f'<div class="vr{" ilk" if i == 0 else ""}"><span class="n">{esc(r["ag"])}</span><span class="ak">DC</span>'
                  f'<s>{tl(r["dc"][0])}</s><b>{tl(r["dc"][1])}</b></div>' for i, r in enumerate(rows))
    css = base_css(1080, 1350, False) + APP_CSS + """
.w{width:1080px;height:1350px;padding:76px 84px 74px;display:flex;flex-direction:column;
 background:radial-gradient(900px 700px at 95% -5%, rgba(255,212,0,.20), transparent 60%),
            radial-gradient(800px 700px at -10% 105%, rgba(34,227,160,.14), transparent 60%),#0A1020}
.app{margin-top:58px}.gun{margin-top:6px;font-size:198px}
.ind{margin-top:26px;font-size:80px;padding:14px 32px 18px}
.vl{margin-top:58px}.vit{margin-top:18px;gap:18px}
.vr{padding:22px 32px}.vr .n{font-size:46px}.vr .ak{font-size:26px}.vr s{font-size:36px}.vr b{font-size:72px}
.alt{font-size:32px}"""
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="w">'
            f'<div class="top">{BOLT.format(s=42, c="#FFD400")}<span>Watt<b>Kaç</b></span><span class="pill">UYGULAMA</span></div>'
            f'<div class="app">{esc(u["name"])} uygulamasıyla</div><div class="gun">{esc(gt)}</div>'
            f'<div class="ind">{esc(o["big"])}</div>'
            f'<div class="vl">En ucuz DC fiyatları · <span>TL/kWh</span></div><div class="vit">{vit}</div><div class="spacer"></div>'
            f'<div class="alt"><span>{len(o["st"])} şarj ağında · {esc(kadar(o["son"]))}</span><span>Tüm fiyatlar →</span></div>'
            f'</div></body></html>')


def app_tablo_html(u, o, rows, bas, idx, tot, d):
    gt = gun_txt(o)
    f = o["fiyatlar"]
    satir = "".join(f'<div class="tr"><span class="no">{bas + i}</span><span class="ag">{esc(r["ag"])}</span>'
                    f'{fiyat_hucre(r.get("ac"), "ac")}{fiyat_hucre(r.get("dc"), "dc")}</div>' for i, r in enumerate(rows))
    alt = f.get("not") or f"{u['name']} uygulamasından başlatılan şarjda"
    css = base_css(1080, 1350, False) + """
.wrap{padding:56px 52px 50px}
.h1{margin-top:26px;font-size:62px;letter-spacing:-1.5px}.h1 span{color:#FFD400}
.h2{margin-top:8px;font-size:28px}
.th,.tr{display:grid;grid-template-columns:50px 1fr 262px 300px;align-items:center;column-gap:12px;padding:0 20px}
.th{margin-top:22px;height:40px;font-size:22px;font-weight:800;color:#8394B8;letter-spacing:2px;text-transform:uppercase}
.th span:nth-child(n+3){text-align:right}
.tb{flex:none;border:2px solid #202C4A;border-radius:22px;overflow:hidden}
.tr{height:68px}.tr:nth-child(odd){background:rgba(255,255,255,.05)}
.no{font-size:24px;font-weight:800;color:#5E6C8C}
.ag{font-size:31px;font-weight:800;white-space:nowrap;letter-spacing:-.3px}
.pc{display:flex;align-items:baseline;justify-content:flex-end;gap:8px;white-space:nowrap}
.pc s{font-size:27px;font-weight:600;color:#7D8BA8;text-decoration-thickness:2px}
.pc .ok{font-size:22px;color:#5E6C8C}
.pc b{font-size:34px;font-weight:900;letter-spacing:-.5px}
.pc.ac b{color:#F4F6FB}.pc.dc b{color:#FFD400;font-size:36px}
.pc.yok{font-size:30px;color:#5E6C8C;font-weight:700}
.nt{margin-top:16px;font-size:24px;font-weight:700;color:#C9D4EA;line-height:1.3}.nt b{color:#22E3A0}
.nt{white-space:nowrap}
.foot{margin-top:6px;font-size:20px}"""
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="wrap">'
            f'{brand(u["name"] + f" · {idx}/{tot}")}'
            f'<div class="h1">{esc((gt.replace("Her ", "") + " fiyatları").capitalize() if gt else "Kampanya fiyatları")} <span>(TL/kWh)</span></div>'
            f'<div class="h2">{esc(indirimli(o["big"]))} · üstü çizili: liste fiyatı · DC\'ye göre sıralı</div>'
            f'<div class="th"><span>#</span><span>Şarj ağı</span><span>AC</span><span>DC</span></div><div class="tb">{satir}</div>'
            f'<div class="spacer"></div><div class="nt"><b>{esc(alt)}.</b></div>'
            f'<div class="foot">Kaynak: {esc(f["kaynak"])} ({esc(tarih_txt(f["tarih"]))}) · Koşullar değişebilir · @wattkac</div>'
            f'</div></body></html>')


def app_katilim_html(u, o, d):
    gt = gun_txt(o)
    f = o["fiyatlar"]
    adim = [(f"{u['name']} uygulamasını indir", "Üye ol; şarjı ve ödemeyi uygulamadan yapacaksın."),
            ("Anlaşmalı istasyonda başlat", f"{len(o['st'])} şarj ağından birinin istasyonunda şarjı {u['name']} uygulamasından başlat."),
            (f"{gt + ': ' if gt else ''}{o['big']}", (f.get("not") or o["det"]) + ".")]
    kart = "".join(f'<div class="ad"><div class="nm">{i}</div><div><div class="at">{esc(a)}</div><div class="ax">{esc(b)}</div></div></div>'
                   for i, (a, b) in enumerate(adim, 1))
    css = base_css(1080, 1350, False) + """
.h1{margin-top:44px;font-size:80px}
.h2{margin-top:12px;font-size:32px}
.ads{margin-top:40px;display:flex;flex-direction:column;gap:20px}
.ad{display:flex;gap:28px;align-items:flex-start;background:rgba(255,255,255,.045);border:2px solid #202C4A;border-radius:26px;padding:28px 30px}
.nm{flex:none;width:76px;height:76px;border-radius:50%;background:#FFD400;color:#0A1020;font-size:44px;font-weight:900;display:flex;align-items:center;justify-content:center}
.at{font-size:38px;font-weight:900;letter-spacing:-.5px;line-height:1.15}
.ax{margin-top:8px;font-size:28px;font-weight:600;color:#C9D4EA;line-height:1.3}
.ip{margin-top:28px;font-size:30px;font-weight:700;line-height:1.35;background:rgba(34,227,160,.08);border:2px solid rgba(34,227,160,.4);border-radius:24px;padding:24px 28px}
.ip b{color:#22E3A0}.ip i{font-style:normal;color:#FFD400;font-weight:800}"""
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="wrap">'
            f'{brand(u["name"] + " · Katılım")}<div class="h1">Nasıl katılırım?</div>'
            f'<div class="h2">{esc(" · ".join(x for x in (gt, str(len(o["st"])) + " şarj ağında", kadar(o["son"])) if x))}</div>'
            f'<div class="ads">{kart}</div>'
            f'<div class="ip"><b>wattkac.com</b>\'da istasyon detayında <i>“Hangi uygulamayla?” → {esc(u["name"])}</i> seç; '
            f'o istasyonda {esc(u["name"])} ile fiyatı gör.</div>'
            f'<div class="spacer"></div>{foot(d)}</div></body></html>')


def app_hikaye_fiyat_html(u, o, d):
    rows = [r for r in fiyat_satirlari(o) if r.get("dc")][:5]
    gt = gun_txt(o) or o["big"]
    vit = "".join(f'<div class="vr{" ilk" if i == 0 else ""}"><span class="n">{esc(r["ag"])}</span><span class="ak">DC</span>'
                  f'<s>{tl(r["dc"][0])}</s><b>{tl(r["dc"][1])}</b></div>' for i, r in enumerate(rows))
    css = base_css(1080, 1920, True) + APP_CSS + """
.wrap{padding:200px 76px 250px}
.app{margin-top:56px}.gun{margin-top:8px;font-size:188px}
.ind{margin-top:26px;font-size:80px;padding:12px 32px 16px}
.vl{margin-top:56px;font-size:28px}.vit{margin-top:16px;gap:14px}
.vr{padding:16px 32px}.vr .n{font-size:48px}.vr .ak{font-size:28px}.vr s{font-size:38px}.vr b{font-size:74px}
.son{margin-top:34px;align-self:flex-start;font-size:34px;font-weight:800;color:#F4F6FB;background:none;padding:0}
.cta{display:flex;justify-content:space-between;align-items:center;gap:20px}
.cta span{font-size:34px;font-weight:700;color:#C9D4EA;line-height:1.25}
.cta b{flex:none;font-size:40px;font-weight:900;color:#0A1020;background:#FFD400;border-radius:18px;padding:14px 26px}"""
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="wrap">'
            f'{brand("Uygulama · " + d["donem"])}'
            f'<div class="app">{esc(u["name"])} uygulamasıyla</div><div class="gun">{esc(gt)}</div><div class="ind">{esc(o["big"])}</div>'
            f'<div class="vl">En ucuz 5 DC fiyatı · <span>TL/kWh</span></div><div class="vit">{vit}</div>'
            f'<div class="son">{len(o["st"])} şarj ağında · {esc(kadar(o["son"]))}</div><div class="spacer"></div>'
            f'<div class="cta"><span>{len(o["st"])} ağın tüm fiyatları<br>gönderide</span><b>wattkac.com</b></div>'
            f'</div></body></html>')


def tarih_txt(iso):
    y, m, g = iso.split("-")
    return f"{int(g)} {AYLAR[int(m) - 1]} {y}"


AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def station_html(s, d, story):
    """Sadece ağın KENDİ indirimi + banka kartıyla birleşince net fiyat. Banka kampanyaları burada tekrar edilmez."""
    W, H = (1080, 1920) if story else (1080, 1350)
    own = "".join(f'<div class="of"><div class="ot"><div class="big">{esc(o["big"])}</div><div class="son">{esc(son_txt(o["son"], "Son: "))}</div></div>'
                  f'<div class="det">{esc(o["det"])}</div></div>' for o in s["own"])
    bp = ""
    bl = s.get("birlesik")
    if bl:
        rows = "".join(f'<div class="row"><div class="rk">{esc(k)}</div><div class="rv">{esc(v)}</div></div>' for k, v in bl["satirlar"])
        bp = (f'<div class="lbl" style="margin-top:{34 if story else 24}px">Banka kartıyla birleşince · {esc(bl["baslik"])}</div>'
              f'<div class="offers" style="margin-top:10px;gap:12px">{rows}</div>'
              f'<div class="foot" style="margin-top:12px">{esc(bl.get("not", ""))}</div>')
    # 5+ kampanyalı ağda kartlar sığsın diye sıkı düzen
    css = base_css(W, H, story)
    if len(s["own"]) >= 5:
        css += (f".offers{{gap:{14 if story else 10}px}}.of{{padding:{18 if story else 12}px 24px;border-radius:20px}}"
                f".big{{font-size:{44 if story else 34}px}}.son{{font-size:20px;padding:4px 12px}}"
                f".det{{margin-top:4px;font-size:{26 if story else 22}px}}")
        if not story:
            css += (".h1{margin-top:22px;font-size:64px}.of{padding:10px 24px}"
                    ".row{padding:10px 24px}.rk{font-size:24px}.rv{font-size:22px}.note{padding:12px 20px;font-size:22px}")
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="wrap">'
            f'{brand("Şarj ağı · " + d["donem"])}<div class="h1">{esc(s["name"])}</div><div class="h2">Ağın kendi indirimi</div>'
            f'<div class="offers">{own}</div>{bp}<div class="spacer"></div>'
            f'<div class="note"><b>Kart kampanyalarının tamamı</b> banka postlarımızda; orada hangi istasyonlarda geçerli olduğu yazıyor.</div>'
            f'{foot(d)}</div></body></html>')


def stlist_html(s, d, part, idx, tot):
    """İstasyon listesi slaydı: il başlıkları + 'istasyon · ilçe', iki sütun."""
    blocks = "".join(
        f'<div class="ib"><div class="il">{esc(x["il"])}</div>' +
        "".join(f'<div class="ys"><b>{esc(a)}</b> · {esc(b)}</div>' for a, b in x["yerler"]) + '</div>' for x in part)
    n = sum(len(x["yerler"]) for x in part)
    css = base_css(1080, 1350, False) + """
.cols{margin-top:22px;column-count:2;column-gap:34px;column-fill:auto;height:950px;overflow:hidden}
.ib{break-inside:avoid;margin-bottom:10px}
.il{font-size:23px;font-weight:900;color:#FFD400;letter-spacing:.3px;border-bottom:2px solid #202C4A;padding-bottom:2px;margin-bottom:4px}
.ys{font-size:19px;line-height:1.27;color:#9FB0D0;font-weight:500}
.ys b{color:#F4F6FB;font-weight:700}"""
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{css}</style></head><body><div class="wrap">'
            f'{brand(f"İstasyon listesi {idx}/{tot}")}<div class="h1" style="font-size:64px">{esc(s["name"])} · {esc(s["own"][0]["big"])}</div>'
            f'<div class="h2">Kampanyalı istasyonlar ({n} istasyon) · {esc(son_txt(s["own"][0]["son"], "Son gün: "))}</div>'
            f'<div class="cols">{blocks}</div>{foot(d)}</div></body></html>')


def list_html(title_html, sub, rows, d, extra=""):
    r = "".join(f'<div class="row"><div class="rk">{esc(k)}</div><div class="rv">{esc(v)}</div></div>' for k, v in rows)
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>{base_css(1080, 1350, False)}</style></head><body><div class="wrap">'
            f'{brand(d["guncelleme_txt"])}<div class="h1" style="font-size:70px">{title_html}</div><div class="h2">{esc(sub)}</div>'
            f'<div class="offers" style="gap:10px">{r}</div>{extra}<div class="spacer"></div>{foot(d)}</div></body></html>')


# ------------------------------------------------------------------ ızgara kapağı
def cover_html(name, big, sub, bottom_left, bottom_right, kind):
    bank = kind.endswith("bank")
    bg, fg, acc = ("#FFD400", "#0A1020", "#0A1020") if bank else ("#0A1020", "#F4F6FB", "#22E3A0")
    boxbg, boxfg = ("#0A1020", "#FFD400") if bank else ("#FFD400", "#0A1020")
    pill = "BANKA" if bank else "UYGULAMA" if kind.endswith("app") else "ŞARJ AĞI"
    nm = NAME_BREAK.get(name, esc(name).replace("&lt;br&gt;", "<br>"))
    lines = nm.count("<br>") + 1
    fs = 188 if lines == 1 and len(name) <= 6 else (150 if lines == 1 else 158)
    if kind.startswith("sum"):
        fs = 132
    glow = "" if bank else "background-image:radial-gradient(800px 700px at 95% 0%, rgba(34,227,160,.16), transparent 60%);"
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:1080px;height:1350px;overflow:hidden;font-family:'Inter',sans-serif}}
.w{{width:1080px;height:1350px;background:{bg};{glow}color:{fg};padding:78px 96px 80px;display:flex;flex-direction:column}}
.top{{display:flex;align-items:center;gap:12px;font-size:38px;font-weight:800}}
.pill{{margin-left:auto;font-size:30px;font-weight:900;letter-spacing:3px;color:{bg};background:{acc};border-radius:12px;padding:10px 22px}}
.sp{{flex:1}}
.name{{font-size:{fs}px;font-weight:900;letter-spacing:-6px;line-height:.95}}
.box{{margin-top:44px;align-self:flex-start;background:{boxbg};color:{boxfg};font-size:96px;font-weight:900;letter-spacing:-3px;line-height:1.02;border-radius:28px;padding:22px 34px 26px;max-width:888px}}
.sub{{margin-top:30px;font-size:40px;font-weight:700;opacity:.85}}
.bot{{display:flex;justify-content:space-between;align-items:center;font-size:36px;font-weight:800}}
.bot span:last-child{{opacity:.7;font-weight:700}}
</style></head><body><div class="w">
<div class="top">{BOLT.format(s=42, c=("#0A1020" if bank else "#FFD400"))}<span>WattKaç</span><span class="pill">{pill}</span></div>
<div class="sp"></div><div class="name">{nm}</div><div class="box">{esc(big)}</div><div class="sub">{esc(sub)}</div><div class="sp"></div>
<div class="bot"><span>{esc(bottom_left)}</span><span>{esc(bottom_right)}</span></div></div></body></html>"""


# ------------------------------------------------------------------ ana akış
def render_all(d, etiket, sadece=None):
    want = (lambda pid: not sadece or pid in sadece)
    out = os.path.join(ROOT, "media", etiket)
    if os.path.exists(out) and not sadece:
        shutil.rmtree(out)
    for pid in (sadece or []):
        shutil.rmtree(os.path.join(out, pid), ignore_errors=True)
    old = []
    mf = os.path.join(out, "manifest.json")
    if sadece and os.path.exists(mf):
        old = [p for p in json.load(open(mf, encoding="utf-8")) if p["id"] not in sadece]
    posts = []

    def add(pid, kind, title, files):
        posts.append({"id": pid, "tur": kind, "baslik": title, "dosyalar": files})

    banks = d["bankalar"]
    sts = [s for s in d["istasyonlar"] if s["own"]]  # kendi indirimi olmayan ağa ayrı post yok (banka postlarında geçiyor)
    if want("ozet_bankalar"):
        p = f"{out}/ozet_bankalar"
        shot(cover_html("Banka<br>kampanyaları", f'{len(banks)} banka · {d["donem"].split()[0]}', " · ".join(b["name"].replace(" Bankası", "") for b in banks),
                        "Sabit post · Tümü burada", "Liste için kaydır →", "sum_bank"), f"{p}/1_kapak.jpg", 1080, 1350)
        yok = ", ".join(x.split(" (")[0] for x in d["kampanyasiz_bankalar"][:2])
        shot(list_html('Şarjda bu ay<br><b style="color:#FFD400">hangi banka?</b>', f'{len(banks)} bankanın {d["donem"]} şarj kampanyaları',
                       [(b["name"], " / ".join(o["big"] for o in banka_teklifleri(d, b))) for b in banks], d,
                       f'<div class="foot" style="margin-top:14px;font-size:22px">Bu ay şarj kampanyası bulunamayan: {esc(yok)}.</div>'),
             f"{p}/2_liste.jpg", 1080, 1350)
        add("ozet_bankalar", "ozet", "Banka kampanyaları özeti", ["1_kapak.jpg", "2_liste.jpg"])
    if want("ozet_istasyonlar"):
        p = f"{out}/ozet_istasyonlar"
        shot(cover_html("Şarj ağı<br>kampanyaları", f'{len(sts)} ağ · {d["donem"].split()[0]}', " · ".join(s["name"] for s in sts),
                        "Sabit post · Tümü burada", "Liste için kaydır →", "sum_station"), f"{p}/1_kapak.jpg", 1080, 1350)
        shot(list_html('Şarj ağlarında<br><b style="color:#FFD400">bu ay ne var?</b>', "Ağların kendi indirimleri",
                       [(s["name"], s["own"][0]["big"]) for s in sts], d),
             f"{p}/2_liste.jpg", 1080, 1350)
        add("ozet_istasyonlar", "ozet", "Şarj ağı kampanyaları özeti", ["1_kapak.jpg", "2_liste.jpg"])
    for b in banks:
        pid = f"banka_{b['id']}"
        if not want(pid):
            continue
        p, c = f"{out}/{pid}", b["cover"]
        shot(cover_html(b["name"], c["big"], c["sub"], son_txt(c['son'], "Son gün: "), "Detay için kaydır →", "bank"), f"{p}/1_kapak.jpg", 1080, 1350)
        shot(bank_html(b, d, False), f"{p}/2_detay.jpg", 1080, 1350)
        shot(bank_html(b, d, True), f"{p}/hikaye.jpg", 1080, 1920)
        add(pid, "banka", b["name"], ["1_kapak.jpg", "2_detay.jpg", "hikaye.jpg"])
    # Uygulama postu: yalnızca kart koşulu olmayan uygulama kampanyası varsa (kartlı olanlar banka postunda)
    for u in [u for u in d.get("uygulamalar", []) if uygulama_teklifleri(u)]:
        pid = f"uygulama_{u['id']}"
        if not want(pid):
            continue
        o0 = uygulama_teklifleri(u)[0]
        c = u.get("cover") or {"big": o0["big"], "son": o0["son"],
                               "sub": " · ".join(x for x in (gun_txt(o0), f"{len(o0['st'])} şarj ağında") if x)}
        p = f"{out}/{pid}"
        if o0.get("fiyatlar"):  # fiyat tablolu düzen: kapak + tablo slaytları + katılım + hikâye
            shot(app_cover_fiyat_html(u, o0, d), f"{p}/1_kapak.jpg", 1080, 1350)
            files, parts, bas = ["1_kapak.jpg"], bolumler(fiyat_satirlari(o0)), 1
            for i, part in enumerate(parts, 1):
                fn = f"{i + 1}_fiyatlar{i}.jpg" if len(parts) > 1 else "2_fiyatlar.jpg"
                shot(app_tablo_html(u, o0, part, bas, i, len(parts), d), f"{p}/{fn}", 1080, 1350)
                files.append(fn)
                bas += len(part)
            fn = f"{len(files) + 1}_katilim.jpg"
            shot(app_katilim_html(u, o0, d), f"{p}/{fn}", 1080, 1350)
            shot(app_hikaye_fiyat_html(u, o0, d), f"{p}/hikaye.jpg", 1080, 1920)
            add(pid, "uygulama", u["name"], files + [fn, "hikaye.jpg"])
            continue
        shot(cover_html(u["name"], c["big"], c["sub"], son_txt(c["son"], "Son gün: "), "Detay için kaydır →", "app"), f"{p}/1_kapak.jpg", 1080, 1350)
        shot(app_html(u, d, False), f"{p}/2_detay.jpg", 1080, 1350)
        shot(app_html(u, d, True), f"{p}/hikaye.jpg", 1080, 1920)
        add(pid, "uygulama", u["name"], ["1_kapak.jpg", "2_detay.jpg", "hikaye.jpg"])
    for s in sts:
        pid = f"istasyon_{s['id']}"
        if not want(pid):
            continue
        p, c = f"{out}/{pid}", s["cover"]
        shot(cover_html(s["name"], c["big"], c["sub"], son_txt(c['son'], "Son gün: "), "Detay için kaydır →", "station"), f"{p}/1_kapak.jpg", 1080, 1350)
        shot(station_html(s, d, False), f"{p}/2_detay.jpg", 1080, 1350)
        shot(station_html(s, d, True), f"{p}/hikaye.jpg", 1080, 1920)
        files = ["1_kapak.jpg", "2_detay.jpg"]
        lst = s.get("istasyon_listesi") or []
        if lst:  # ~38 satıra bir slayt; il bloğu bölünmez
            parts, cur, cnt = [], [], 0
            for x in lst:
                if cur and cnt + len(x["yerler"]) + 1 > 56:
                    parts.append(cur); cur, cnt = [], 0
                cur.append(x); cnt += len(x["yerler"]) + 1
            parts.append(cur)
            for i, part in enumerate(parts, 1):
                shot(stlist_html(s, d, part, i, len(parts)), f"{p}/3_liste{i}.jpg", 1080, 1350)
                files.append(f"3_liste{i}.jpg")
        add(pid, "istasyon", s["name"], files + ["hikaye.jpg"])
    os.makedirs(out, exist_ok=True)
    json.dump(old + posts, open(f"{out}/manifest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return posts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiket", required=True, help="ör. 2026-11 veya güncelleme için 2026-11-15")
    ap.add_argument("--sadece", default="", help="virgülle post id'leri, ör. banka_garanti,istasyon_zes,uygulama_rotawatt (boş = hepsi)")
    a = ap.parse_args()
    data = json.load(open(os.path.join(ROOT, "data", "kampanyalar.json"), encoding="utf-8"))
    y, m, g = data["guncelleme"].split("-")
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    data["guncelleme_txt"] = f"{int(g)} {aylar[int(m) - 1]} {y}"
    posts = render_all(data, a.etiket, set(x for x in a.sadece.split(",") if x))
    print(f"{len(posts)} post üretildi → media/{a.etiket}")
