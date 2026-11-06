#!/usr/bin/env python3
"""EPDK şarj istasyonu adreslerini konuma çevirir (Nominatim, saniyede en fazla 1 istek).

Girdi : data/epdk/epdk_sarj_istasyonlari.csv
Önbellek: data/epdk/konum_onbellek.json   {adres: [lat, lon, kalite] | null}
  kalite: "a" adres/sokak düzeyi, "m" mahalle, "i" ilçe merkezi (yaklaşık)
Her çalıştırmada süre bütçesi (varsayılan 4 saat) bitince durur; kalan adresler sonraki çalıştırmada devam eder.
Kullanım: python3 tools/epdk_konum.py [azami_saniye]
"""
import csv, json, pathlib, re, sys, time, urllib.parse, urllib.request

CSV = pathlib.Path("data/epdk/epdk_sarj_istasyonlari.csv")
CACHE = pathlib.Path("data/epdk/konum_onbellek.json")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Resmi haritasından konumu alınan ağlar burada konumlandırılmaz (istasyon_birlestir.py ile aynı liste)
RESMI = re.compile(r"\bzes\b|ovolt|sharz|wat mobilite|watmobilite|\bwat\b|astor")
UA = "WattKac-konum/1.0 (https://wattkac.com; elektrikli arac sarj haritasi)"
TR = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
fold = lambda s: s.translate(TR).lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")


def parse(adres):
    """-> (sokak_kismi, mahalle, ilce, il) ; bulunamayanlar None"""
    a = re.sub(r"\(\s*Ada:.*?\)", "", adres).strip()
    m = re.match(r"^(.*?)\s+/\s+([^/]+)$", a)
    if not m:
        return None
    left, il = m.group(1).strip(), m.group(2).strip()
    mh = re.match(r"^(.*?\b(?:Mahallesi|Mah\.|Mh\.|Köyü|Mevkii))\b", left, re.I)
    mahalle = mh.group(1) if mh else None
    # ilçe: son bina bilgisinden ("No:12", "BLOK") sonra gelen kısım; yoksa son sözcük
    parts = list(re.finditer(r"(?:No\s*:\s*\S+|\bBLOK\b|Blok\s*\S*)\s*", left))
    tail = left[parts[-1].end():].strip() if parts else ""
    words = left.split()
    ilce = tail if tail and len(tail) <= 40 else (words[-1] if words else None)
    if ilce and (re.search(r"(Mahallesi|Caddesi|Sokağı|Sokak|Cadde|Bulvarı)$", ilce, re.I) or re.match(r"No\s*:", ilce)):
        ilce = None
    return left, mahalle, ilce, il


PHOTON = "https://photon.komoot.io/api/"
PROVIDER = ["nominatim"]  # 503/429 alınca "photon"a geçilir


class Throttled(Exception):
    pass


def search(q, il, rate):
    time.sleep(rate)
    try:
        return (search_nominatim if PROVIDER[0] == "nominatim" else search_photon)(q, il)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            if PROVIDER[0] == "nominatim":
                print(f"Nominatim HTTP {e.code}: Photon'a geçiliyor", file=sys.stderr)
                PROVIDER[0] = "photon"
                time.sleep(rate)
                return search_photon(q, il)
            raise Throttled(f"Photon HTTP {e.code}")
        raise


def search_photon(q, il):
    url = PHOTON + "?" + urllib.parse.urlencode({"q": q.replace(", Türkiye", ""), "limit": 1, "bbox": "25.6,35.8,44.9,42.2"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    f = (j.get("features") or [None])[0]
    if not f:
        return None
    pr = f.get("properties") or {}
    where = " ".join(str(pr.get(k, "")) for k in ("state", "county", "city", "district"))
    if pr.get("countrycode", "TR") != "TR" or fold(il)[:5] not in fold(where):
        return None
    lon, lat = f["geometry"]["coordinates"][:2]
    return float(lat), float(lon), pr.get("type", ""), pr.get("osm_value", "")


def search_nominatim(q, il):
    url = NOMINATIM + "?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "tr", "addressdetails": 0})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    if not j:
        return None
    h = j[0]
    # sonucun doğru ilde olduğunu doğrula
    if fold(il)[:5] not in fold(h.get("display_name", "")):
        return None
    return float(h["lat"]), float(h["lon"]), h.get("type", ""), h.get("addresstype", "")


def clean(s):
    s = re.sub(r"\bNo\s*:\s*", "No ", s)
    s = re.sub(r"\bMahallesi\b", "Mahallesi", s)
    return re.sub(r"\s+", " ", s).strip()


def locate(adres, rate):
    p = parse(adres)
    if not p:
        return None
    left, mahalle, ilce, il = p
    tiers = [("a", clean(f"{left}, {il}, Türkiye"))]
    if mahalle and ilce:
        tiers.append(("m", clean(f"{mahalle}, {ilce}, {il}, Türkiye")))
    if ilce:
        tiers.append(("i", clean(f"{ilce}, {il}, Türkiye")))
    for kal, q in tiers:
        r = search(q, il, rate)
        if r:
            return [round(r[0], 5), round(r[1], 5), kal]
    return None


def main():
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 4 * 3600
    rate = 1.1
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    rows = [r for r in csv.DictReader(CSV.open(encoding="utf-8-sig"))
            if r["hizmet"].strip() != "Özel" and not RESMI.search(fold(r["marka"] + " " + r["ag_isletmecisi"]))]
    size = {}
    for r in rows:
        size[r["ag_isletmecisi"]] = size.get(r["ag_isletmecisi"], 0) + 1
    rows.sort(key=lambda r: -size[r["ag_isletmecisi"]])  # büyük ağlar önce
    adresler, seen = [], set()
    for r in rows:
        a = r["adres"].strip()
        if a and a not in seen:
            seen.add(a)
            adresler.append(a)
    todo = [a for a in adresler if a not in cache]
    print(f"{len(adresler)} adres, önbellekte {len(adresler) - len(todo)}, kalan {len(todo)}")
    t0, done, fails = time.time(), 0, 0
    for a in todo:
        if time.time() - t0 > budget:
            break
        try:
            cache[a] = locate(a, rate)
            fails = 0
        except Throttled as e:
            print(f"{e}: iki servis de sınırladı, çalıştırma durduruluyor", file=sys.stderr)
            break
        except urllib.error.HTTPError as e:
            print("HTTP hatası", e.code, a, file=sys.stderr)
            fails += 1
        except Exception as e:  # noqa: BLE001
            print("hata:", e, a, file=sys.stderr)
            fails += 1
            time.sleep(5)
        if fails >= 20:
            print("art arda 20 hata, durduruluyor", file=sys.stderr)
            break
        done += 1
        if done % 200 == 0:
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"{done} adres işlendi")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ok = sum(1 for v in cache.values() if v)
    kalan = sum(1 for a in adresler if a not in cache)
    print(f"Bitti: bu çalıştırmada {done} ({PROVIDER[0]}), önbellekte {len(cache)} (konumlanan {ok}), bu listede kalan {kalan}")


if __name__ == "__main__":
    main()
