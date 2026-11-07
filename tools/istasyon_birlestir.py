#!/usr/bin/env python3
"""EPDK şarj istasyonu listesi (+ konum önbelleği) ile OpenStreetMap kayıtlarını birleştirip
site/istasyonlar.json üretir.

Girdiler : data/epdk/epdk_sarj_istasyonlari.csv, data/epdk/konum_onbellek.json, data/osm/istasyonlar_osm.json
Çıktı    : site/istasyonlar.json
Kayıt alanları: i=kimlik, e=EPDK no, a/o=enlem/boylam, q=konum kalitesi (p adresteki tesisin OSM konumu, r resmi ağ haritası, o OSM, c Open Charge Map, a adres, m mahalle, i ilçe),
                n=ad, b=marka, p=işletmeci (isletmeciler tablosuna indeks ya da OSM'de metin), k=kW, t=soketler, ac/dc, c=adet, ad=adres, h=saat, u=web
"""
import csv, json, math, pathlib, re, sys, datetime

EPDK = pathlib.Path("data/epdk/epdk_sarj_istasyonlari.csv")
CACHE = pathlib.Path("data/epdk/konum_onbellek.json")
POI = pathlib.Path("data/epdk/poi_eslesme.json")  # tesis (Shell, AVM vb.) üzerinden bulunan kesin konumlar
OSM = pathlib.Path("data/osm/istasyonlar_osm.json")
OCM = pathlib.Path("data/ocm/istasyonlar_ocm.json")
AGLAR = pathlib.Path("data/aglar")
# Resmi listesi olan ağlar: bu ağlara ait EPDK/OSM kayıtları atlanır, ağın kendi listesi kullanılır
RESMI = {"trugo": r"trugo", "zes": r"\bzes\b", "ovolt": r"ovolt|sharz", "wat": r"wat mobilite|watmobilite|\bwat\b", "astor": r"astor"}
SECILI = pathlib.Path("data/secili_istasyonlar.json")  # yalnızca seçili istasyonlarda geçerli ağ kampanyaları
SECILI_AG = {"otopriz": r"otopriz|dicle kok"}
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site/istasyonlar.json")
TR = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
fold = lambda s: s.translate(TR).lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
key = lambda s: (re.sub(r"[^a-z0-9 ]", " ", fold(s)).split() or [""])[0]


# Türkiye'nin kaba sınırı (boylam, enlem). Ege'deki Yunan adalarını ve Kıbrıs'ı dışarıda bırakacak şekilde çizildi.
TR_POLY = [(26.35, 41.72), (26.6, 41.98), (27.0, 42.1), (28.05, 41.98), (28.15, 41.6), (29.1, 41.27), (31.0, 41.32), (32.5, 41.92),
           (33.5, 42.08), (35.2, 42.12), (36.5, 41.45), (38.0, 41.15), (40.0, 41.12), (41.5, 41.58), (42.8, 41.62), (43.5, 41.15),
           (44.85, 41.2), (44.85, 40.0), (44.6, 39.4), (44.45, 39.0), (44.85, 37.25), (44.3, 37.0), (42.3, 37.12), (42.2, 37.1), (41.2, 37.062), (40.0, 36.81),
           (39.0, 36.68), (38.0, 36.83), (37.4, 36.62), (36.7, 36.6), (36.65, 36.2), (36.4, 35.78), (35.85, 35.78), (35.9, 36.3), (35.5, 36.58),
           (34.6, 36.78), (33.9, 36.25), (32.8, 36.0), (32.0, 36.5), (30.6, 36.2), (30.4, 36.18), (29.66, 36.18), (29.38, 36.21), (29.1, 36.55),
           (28.6, 36.75), (27.9, 36.62), (27.35, 36.66), (27.7, 36.8), (27.6, 36.98), (27.2, 37.0), (27.22, 37.15), (27.18, 37.35),
           (27.2, 37.55), (27.15, 37.75), (26.75, 38.2), (26.25, 38.25), (26.22, 38.5), (26.45, 38.7), (26.75, 38.75), (26.65, 39.2),
           (26.58, 39.36), (26.0, 39.45), (26.1, 39.9), (26.15, 40.05), (26.2, 40.3), (26.3, 40.6), (26.6, 40.62), (26.0, 40.72),
           (26.3, 41.25), (26.55, 41.6)]
TR_ISLANDS = [(25.6, 40.08, 26.02, 40.26), (25.95, 39.78, 26.1, 39.87)]  # Gökçeada, Bozcaada


def in_turkey(lat, lon):
    if any(x0 <= lon <= x1 and y0 <= lat <= y1 for x0, y0, x1, y1 in TR_ISLANDS):
        return True
    inside, n = False, len(TR_POLY)
    for k in range(n):
        x1, y1 = TR_POLY[k]; x2, y2 = TR_POLY[(k + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def dist(a, b, c, d):
    t = math.radians
    h = math.sin(t(c - a) / 2) ** 2 + math.cos(t(a)) * math.cos(t(c)) * math.sin(t(d - b) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def main():
    resmi, kaynaklar = [], {}
    for f in sorted(AGLAR.glob("*.json")) if AGLAR.exists() else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("ag") in RESMI and d.get("istasyonlar"):
            kaynaklar[d["ag"]] = {"sayfa": d.get("kaynak"), "cekildi": d.get("cekildi"), "sayi": len(d["istasyonlar"])}
            for r in d["istasyonlar"]:
                r = dict(r); r["q"] = "r"; resmi.append(r)
    covered = re.compile("|".join(RESMI[k] for k in kaynaklar)) if kaynaklar else None
    is_covered = lambda *names: bool(covered and covered.search(fold(" ".join(x for x in names if x))))

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    poi = json.loads(POI.read_text(encoding="utf-8")) if POI.exists() else {}
    osm = json.loads(OSM.read_text(encoding="utf-8"))["istasyonlar"] if OSM.exists() else []
    ocm = json.loads(OCM.read_text(encoding="utf-8"))["istasyonlar"] if OCM.exists() else []
    ops, opi = [], {}
    def op(name):
        if name not in opi:
            opi[name] = len(ops); ops.append(name)
        return opi[name]

    seen, recs, ozel, groups = set(), [], 0, {}
    for r in csv.DictReader(EPDK.open(encoding="utf-8-sig")):
        no = r["no"].strip()
        if no in seen:
            continue
        seen.add(no)
        loc = cache.get(r["adres"].strip())
        rec = {"i": "e" + re.sub(r"\D", "", no), "e": no, "n": r["ad"].strip(), "b": r["marka"].strip(), "p": op(r["ag_isletmecisi"].strip()),
               "ad": r["adres"].strip()}
        if is_covered(r["marka"], r["ag_isletmecisi"]):
            continue  # bu ağın resmi listesi var
        if r["hizmet"].strip() == "Özel":
            ozel += 1
            continue  # halka açık olmayan (özel) istasyonlar haritada gösterilmez
        if no in poi:
            rec["a"], rec["o"], rec["q"] = poi[no][0], poi[no][1], "p"
            rec["tesis"] = poi[no][2]
        elif loc:
            rec["a"], rec["o"], rec["q"] = loc
        g = (fold(r["marka"]).strip(), fold(r["adres"]).strip())
        if g in groups:
            groups[g]["c"] = groups[g].get("c", 1) + 1
            continue
        rec["n"] = re.sub(r"[\s\-_]+(\d{1,2}|[A-Z])$", "", rec["n"]).strip() or rec["n"]
        groups[g] = rec
        recs.append(rec)

    # OSM ve Open Charge Map kayıtlarını EPDK kayıtlarıyla eşle: aynı marka anahtarı, en yakın kayıt.
    # Arama yarıçapı EPDK konumunun kalitesine göre: adres 300 m, mahalle 2,5 km, ilçe 8 km.
    # Eşleşince EPDK kaydı kesin konum ve soket bilgisini alır; eşleşmeyenler ayrı istasyon olarak eklenir.
    RADIUS = {"p": 300, "a": 300, "m": 2500, "i": 8000}
    G = 0.1
    cell = lambda a, o: (int(a // G), int(o // G))
    grid = {}
    for r in recs:
        if "a" in r and r.get("q") in RADIUS:
            grid.setdefault(cell(r["a"], r["o"]), []).append(r)
    used, extra, stats = set(), [], {}
    xgrid = {}
    for r in resmi:
        xgrid.setdefault(cell(r["a"], r["o"]), []).append((key(r.get("b") or ""), r))

    def near_extra(s, k, lim=80):
        cx, cy = cell(s["a"], s["o"])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for kk, r in xgrid.get((cx + dx, cy + dy), []):
                    if kk == k and dist(s["a"], s["o"], r["a"], r["o"]) < lim:
                        return True
        return False

    for q, src in (("o", osm), ("c", ocm)):
        st = stats.setdefault(q, [0, 0])
        for s in src:
            names = (s.get("b"), s.get("p"), s.get("w"), s.get("n"))
            if is_covered(*names):
                continue
            k = key(s.get("b") or s.get("p") or s.get("w") or s.get("n") or "")
            best, bd = None, None
            cx, cy = cell(s["a"], s["o"])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for r in grid.get((cx + dx, cy + dy), []):
                        if r["i"] in used or key(r["b"]) != k:
                            continue
                        d = dist(s["a"], s["o"], r["a"], r["o"])
                        if d <= RADIUS[r["q"]] and (bd is None or d < bd):
                            best, bd = r, d
            if best:
                used.add(best["i"]); st[0] += 1
                best.update({x: s[x] for x in ("k", "t", "ac", "dc", "c", "h", "u") if x in s})
                best["a"], best["o"], best["q"] = s["a"], s["o"], q
            elif k and near_extra(s, k):
                continue  # aynı istasyon başka kaynaktan zaten eklendi
            else:
                s = dict(s); s["q"] = q; st[1] += 1
                if s.get("p"):
                    s["p"] = op(s["p"])
                extra.append(s)
                xgrid.setdefault(cell(s["a"], s["o"]), []).append((k, s))
    recs += extra + resmi
    # Seçili istasyon kampanyaları: resmi listedeki "Ad, İlçe" kayıtlarını istasyon adı/ilçe/il ile eşleştir
    secili = json.loads(SECILI.read_text(encoding="utf-8")) if SECILI.exists() else {}
    toks = lambda x: set(re.sub(r"[^a-z0-9 ]", " ", fold(x or "")).split())
    sk_hits = {}
    for ag, d in secili.items():
        rx = re.compile(SECILI_AG.get(ag, re.escape(ag)))
        GENEL = {"petrol", "akaryakit", "otel", "hotel", "restaurant", "restoran", "avm", "dinlenme", "tesisi", "tesisleri", "otopark", "the"}
        items = [(toks(i["ad"]) - GENEL or toks(i["ad"]), toks(i.get("ilce", "")) - {"merkez"}, toks(i.get("il", ""))) for i in d.get("istasyonlar", [])]
        hit = 0
        for r in recs:
            opn = ops[r["p"]] if isinstance(r.get("p"), int) else (r.get("p") or "")
            if not rx.search(fold(" ".join([r.get("b") or "", opn]))):
                continue
            nm = re.split(r"\s+-\s+", r.get("n") or "")[0]
            name_part, _, dist_part = nm.rpartition(",") if "," in nm else (nm, "", "")
            nt, place = toks(name_part) - {"otopriz"}, toks(dist_part) | toks(r.get("ad"))
            for L, D, IL in items:
                if L and L <= nt and (not D or D <= place) and (not IL or IL & place or D):
                    r.setdefault("sk", []).append(ag); hit += 1
                    break
        sk_hits[ag] = hit
    located = [r for r in recs if "a" in r]
    recs = [r for r in located if in_turkey(r["a"], r["o"])]  # konumu bilinmeyen ve Türkiye dışı kayıtlar gösterilmez
    disari = len(located) - len(recs)
    recs.sort(key=lambda r: (round(r["a"], 1), r["o"], r["i"]))
    cnt = {}
    for r in recs:
        b = r.get("b") or ""
        if b:
            cnt[b.lower()] = cnt.get(b.lower(), 0) + 1
    data = {"guncelleme": datetime.date.today().isoformat(),
            "kaynak": "EPDK Şarj İstasyonları kaydı, ağların resmi haritaları, © OpenStreetMap katkıda bulunanlar (ODbL), © Open Charge Map (CC BY 4.0)",
            "sayi": len(recs), "resmi_kaynaklar": kaynaklar, "secili_aglar": sorted(secili.keys()),
            "isletmeciler": ops, "istasyonlar": recs}
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(txt, encoding="utf-8")
    print("seçili kampanya eşleşmeleri:", sk_hits)
    ozet = ", ".join("%s %d" % (k, v["sayi"]) for k, v in kaynaklar.items())
    print(f"resmi ağ listeleri {len(resmi)} ({ozet}); EPDK {len(seen)} kayıt (özel {ozel} çıkarıldı), önbellekten konumlanan {sum(1 for r in recs if r.get('e'))}, eşleşen/eklenen OSM {stats.get('o')}, OCM {stats.get('c')}, Türkiye dışı {disari}, aynı adreste birleştirilen EPDK ünitesi {sum(g.get('c', 1) - 1 for g in groups.values())}, toplam {len(recs)}, {len(txt)//1024} KB")


if __name__ == "__main__":
    main()
