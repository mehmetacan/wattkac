#!/usr/bin/env python3
"""EPDK kaydında konumu yaklaşık (mahalle/ilçe düzeyinde) kalan şarj istasyonlarını, adreslerinde geçen tesise
(akaryakıt istasyonu, AVM, dinlenme tesisi, otel) göre OpenStreetMap'teki o tesisin kesin konumuna yerleştirir.

Örnek: "Shell Ünye Karşıyaka · Karşıyaka Mah. ... Ünye / ORDU" → OSM'deki Ünye'deki Shell akaryakıt istasyonu.

Girdiler: data/epdk/epdk_sarj_istasyonlari.csv, data/epdk/konum_onbellek.json (yaklaşık konum)
Çıktı   : data/epdk/poi_eslesme.json  {EPDK no: [enlem, boylam, tesis adı, OSM kimliği]}
Kurallar: tesis, yaklaşık konumun yakınında olmalı (mahalle 4 km, ilçe 15 km); akaryakıt markasıyla eşleşmede ya
          isimde ortak ayırt edici bir sözcük olmalı ya da çevrede o markanın tek istasyonu olmalı. Emin olunamayan kayıt
          eşleştirilmez, yaklaşık konumda kalır.
Kullanım: python3 tools/poi_konum.py            (Overpass'tan tesisleri çeker)
          python3 tools/poi_konum.py tesisler.json  (önceden indirilmiş Overpass yanıtıyla)
"""
import csv, json, math, pathlib, re, sys, time, urllib.parse, urllib.request

CSV = pathlib.Path("data/epdk/epdk_sarj_istasyonlari.csv")
CACHE = pathlib.Path("data/epdk/konum_onbellek.json")
OUT = pathlib.Path("data/epdk/poi_eslesme.json")
SERVERS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]
QUERY = """[out:json][timeout:300];
area["ISO3166-1"="TR"][admin_level=2]->.a;
(nwr["amenity"="fuel"](area.a);
 nwr["shop"="mall"](area.a);
 nwr["highway"~"^(services|rest_area)$"](area.a);
 nwr["tourism"~"^(hotel|motel)$"]["name"](area.a););
out center tags;"""
UA = "WattKac/1.0 (+https://wattkac.com)"
TRT = str.maketrans({"İ": "i", "I": "ı"})
fold = lambda s: re.sub(r"[^a-z0-9 ]", " ", (s or "").translate(TRT).lower().replace("ı", "i").replace("ş", "s")
                        .replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("â", "a").replace("î", "i"))

FUEL = {  # EPDK metnindeki kalıp → OSM ad/marka/işletmeci içinde aranacak kalıp
    "shell": r"\bshell\b", "opet": r"\bopet\b", "po": r"petrol ofisi|\bpo\b", "bp": r"\bbp\b", "total": r"\btotal",
    "aytemiz": r"aytemiz", "lukoil": r"lukoil", "moil": r"\bm ?oil\b", "alpet": r"alpet", "kadoil": r"kadoil",
    "turkpetrol": r"turkpetrol|turk petrol", "sunpet": r"sunpet", "go": r"\bgo\b", "termopet": r"termopet",
}
FUEL_EPDK = {"shell": r"\bshell\b", "opet": r"\bopet\b", "po": r"petrol ofisi|\bpo\b", "bp": r"\bbp\b", "total": r"\btotal",
             "aytemiz": r"aytemiz", "lukoil": r"lukoil", "moil": r"\bm ?oil\b", "alpet": r"alpet", "kadoil": r"kadoil",
             "turkpetrol": r"turkpetrol|turk petrol", "sunpet": r"sunpet", "termopet": r"termopet"}
KIND_EPDK = {"mall": r"\bavm\b|outlet|alisveris merkezi|\bmall\b|\bpark avm|\bcenter\b|\bcity\b",
             "services": r"dinlenme|tesisleri|\bmola\b", "hotel": r"\botel\b|\bhotel\b|\bresort\b|\bmotel\b"}
STOP = set("""mahallesi mah mh caddesi cad cd sokagi sokak sk sok bulvari bulv no blok kat merkez merkezi istasyonu istasyon akaryakit
petrol sarj trugo esarj zes voltrun otopriz astor wat mobilite ovolt sharz enerji elektrik arac araclari elektrikli dc ac hizli
otopark otoparki ve ile the a b c d sitesi site koyu mevkii yolu yol km kavsagi kavsak tesis tesisleri dinlenme avm alisveris
merkez hotel otel resort shell opet bp total po ofisi aytemiz lukoil moil alpet kadoil turkpetrol sunpet go kuzey guney dogu bati
yonu yonu""".split())


def dist(a, b, c, d):
    t = math.radians
    h = math.sin(t(c - a) / 2) ** 2 + math.cos(t(a)) * math.cos(t(c)) * math.sin(t(d - b) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def tokens(s):
    return {w for w in fold(s).split() if len(w) >= 4 and w not in STOP and not w.isdigit()}


def fetch():
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last = None
    for attempt in range(3):
        for url in SERVERS:
            try:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=400) as r:
                    j = json.load(r)
                if re.search(r"error|timed out", str(j.get("remark", "")), re.I):
                    raise RuntimeError(j["remark"][:120])
                if len(j.get("elements", [])) > 5000:
                    print(f"{url}: {len(j['elements'])} tesis")
                    return j["elements"]
                last = f"{url}: yetersiz kayıt"
            except Exception as e:  # noqa: BLE001
                last = f"{url}: {e}"
            print("başarısız ->", last, file=sys.stderr)
        time.sleep(30 * (attempt + 1))
    raise SystemExit("Overpass'tan tesis verisi alınamadı: " + str(last))


def load_pois(elements):
    pois = []
    for e in elements:
        t = e.get("tags") or {}
        lat = e.get("lat", (e.get("center") or {}).get("lat"))
        lon = e.get("lon", (e.get("center") or {}).get("lon"))
        if not isinstance(lat, (int, float)):
            continue
        kind = "fuel" if t.get("amenity") == "fuel" else "mall" if t.get("shop") == "mall" else \
            "services" if t.get("highway") in ("services", "rest_area") else "hotel"
        label = " ".join(x for x in (t.get("name"), t.get("brand"), t.get("operator")) if x)
        pois.append({"id": f"{e['type'][0]}{e['id']}", "a": lat, "o": lon, "kind": kind, "name": t.get("name") or t.get("brand") or "",
                     "f": fold(label), "tok": tokens(t.get("name", ""))})
    return pois


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    elements = json.load(open(src, encoding="utf-8"))["elements"] if src else fetch()
    pois = load_pois(elements)
    G = 0.1
    grid = {}
    for p in pois:
        grid.setdefault((int(p["a"] // G), int(p["o"] // G)), []).append(p)

    def near(a, o, r):
        cx, cy, n = int(a // G), int(o // G), int(r / 11000) + 1
        for dx in range(-n, n + 1):
            for dy in range(-n, n + 1):
                for p in grid.get((cx + dx, cy + dy), []):
                    d = dist(a, o, p["a"], p["o"])
                    if d <= r:
                        yield p, d

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    out, stats = {}, {"aday": 0, "eslesen": 0}
    seen = set()
    for r in csv.DictReader(CSV.open(encoding="utf-8-sig")):
        no = r["no"].strip()
        if no in seen or r["hizmet"].strip() == "Özel":
            continue
        seen.add(no)
        loc = cache.get(r["adres"].strip())
        if not loc or loc[2] not in ("m", "i"):
            continue  # konumu zaten adres düzeyinde ya da hiç yok
        text = fold(r["ad"] + " " + r["adres"])
        R = 4000 if loc[2] == "m" else 15000
        want = [("fuel", k) for k, rx in FUEL_EPDK.items() if re.search(rx, text)] + \
               [(k, None) for k, rx in KIND_EPDK.items() if re.search(rx, text)]
        if not want:
            continue
        stats["aday"] += 1
        tok = tokens(r["ad"] + " " + r["adres"].split(" / ")[0])
        best = None
        for kind, brand in want:
            cands = []
            for p, d in near(loc[0], loc[1], R):
                if p["kind"] != kind:
                    continue
                if brand and not re.search(FUEL[brand], p["f"]):
                    continue
                score = len(tok & p["tok"])
                cands.append((score, d, p))
            if not cands:
                continue
            cands.sort(key=lambda x: (-x[0], x[1]))
            score, d, p = cands[0]
            if kind == "fuel":
                ok = score >= 1 or len(cands) == 1  # ortak sözcük ya da çevrede markanın tek istasyonu
            else:
                ok = score >= 1  # AVM/otel/tesiste mutlaka isim benzerliği
            if ok and (best is None or (score, -d) > (best[0], -best[1])):
                best = (score, d, p)
        if best:
            p = best[2]
            out[no] = [round(p["a"], 6), round(p["o"], 6), p["name"][:60], p["id"]]
            stats["eslesen"] += 1
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"Tesis {len(pois)}; yaklaşık konumlu ve tesis adı geçen EPDK kaydı {stats['aday']}, kesin konuma yerleşen {stats['eslesen']}")


if __name__ == "__main__":
    main()
