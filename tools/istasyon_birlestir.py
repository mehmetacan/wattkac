#!/usr/bin/env python3
"""EPDK şarj istasyonu listesi (+ konum önbelleği) ile OpenStreetMap kayıtlarını birleştirip
site/istasyonlar.json üretir.

Girdiler : data/epdk/epdk_sarj_istasyonlari.csv, data/epdk/konum_onbellek.json, data/osm/istasyonlar_osm.json
Çıktı    : site/istasyonlar.json
Kayıt alanları: i=kimlik, e=EPDK no, a/o=enlem/boylam, q=konum kalitesi (o OSM, a adres, m mahalle, i ilçe),
                n=ad, b=marka, p=işletmeci (isletmeciler tablosuna indeks ya da OSM'de metin), k=kW, t=soketler, ac/dc, c=adet, ad=adres, h=saat, u=web
"""
import csv, json, math, pathlib, re, sys, datetime

EPDK = pathlib.Path("data/epdk/epdk_sarj_istasyonlari.csv")
CACHE = pathlib.Path("data/epdk/konum_onbellek.json")
OSM = pathlib.Path("data/osm/istasyonlar_osm.json")
AGLAR = pathlib.Path("data/aglar")
# Resmi listesi olan ağlar: bu ağlara ait EPDK/OSM kayıtları atlanır, ağın kendi listesi kullanılır
RESMI = {"zes": r"\bzes\b", "ovolt": r"ovolt|sharz", "wat": r"wat mobilite|watmobilite|\bwat\b", "astor": r"astor"}
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site/istasyonlar.json")
TR = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
fold = lambda s: s.translate(TR).lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
key = lambda s: (re.sub(r"[^a-z0-9 ]", " ", fold(s)).split() or [""])[0]


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
    osm = json.loads(OSM.read_text(encoding="utf-8"))["istasyonlar"] if OSM.exists() else []
    ops, opi = [], {}
    def op(name):
        if name not in opi:
            opi[name] = len(ops); ops.append(name)
        return opi[name]

    seen, recs, ozel = set(), [], 0
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
        if loc:
            rec["a"], rec["o"], rec["q"] = loc
        recs.append(rec)

    # OSM kayıtlarını eşle: aynı marka anahtarı + 300 m (adres düzeyi konumlarda), en yakın EPDK kaydı
    grid = {}
    for r in recs:
        if "a" in r and r["q"] in ("a", "m"):
            grid.setdefault((round(r["a"], 2), round(r["o"], 2)), []).append(r)
    matched, extra = 0, []
    used = set()
    for s in osm:
        if is_covered(s.get("b"), s.get("p"), s.get("w"), s.get("n")):
            continue
        k = key(s.get("b") or s.get("p") or s.get("w") or s.get("n") or "")
        best, bd = None, 300
        cx, cy = round(s["a"], 2), round(s["o"], 2)
        for dx in (-.01, 0, .01):
            for dy in (-.01, 0, .01):
                for r in grid.get((round(cx + dx, 2), round(cy + dy, 2)), []):
                    if r["i"] in used or key(r["b"]) != k:
                        continue
                    d = dist(s["a"], s["o"], r["a"], r["o"])
                    if d < bd:
                        best, bd = r, d
        if best:
            used.add(best["i"]); matched += 1
            best.update({x: s[x] for x in ("k", "t", "ac", "dc", "c", "h", "u") if x in s})
            best["a"], best["o"], best["q"] = s["a"], s["o"], "o"
            if s.get("n") and not best.get("n"):
                best["n"] = s["n"]
        else:
            s = dict(s); s["q"] = "o"
            if s.get("p"):
                s["p"] = op(s["p"])
            extra.append(s)
    recs += extra + resmi
    located = [r for r in recs if "a" in r]
    recs = located  # konumu bilinmeyenler haritada gösterilemez
    recs.sort(key=lambda r: (round(r["a"], 1), r["o"], r["i"]))
    cnt = {}
    for r in recs:
        b = r.get("b") or ""
        if b:
            cnt[b.lower()] = cnt.get(b.lower(), 0) + 1
    data = {"guncelleme": datetime.date.today().isoformat(),
            "kaynak": "EPDK Şarj İstasyonları kaydı ve © OpenStreetMap katkıda bulunanlar (ODbL)",
            "sayi": len(recs), "resmi_kaynaklar": kaynaklar,
            "isletmeciler": ops, "istasyonlar": recs}
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(txt, encoding="utf-8")
    ozet = ", ".join("%s %d" % (k, v["sayi"]) for k, v in kaynaklar.items())
    print(f"resmi ağ listeleri {len(resmi)} ({ozet}); EPDK {len(seen)} kayıt (özel {ozel} çıkarıldı), önbellekten konumlanan {sum(1 for r in recs if r.get('e'))}, OSM ile eşleşen {matched}, yalnız OSM {len(extra)}, toplam {len(recs)}, {len(txt)//1024} KB")


if __name__ == "__main__":
    main()
