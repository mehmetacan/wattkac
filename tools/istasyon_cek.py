#!/usr/bin/env python3
"""Türkiye'deki tüm şarj istasyonlarını OpenStreetMap'ten (Overpass) çekip
site/istasyonlar.json olarak kaydeder. Yalnızca standart kütüphane kullanır.

Kullanım: python3 tools/istasyon_cek.py [çıktı_dosyası]
Çıktı bozuksa ya da çok az kayıt gelirse mevcut dosyanın üzerine YAZILMAZ.
"""
import json, math, re, sys, time, urllib.parse, urllib.request, datetime, pathlib

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
QUERY = """[out:json][timeout:240];
area["ISO3166-1"="TR"][admin_level=2]->.a;
nwr["amenity"="charging_station"](area.a);
out center tags;"""
MIN_RECORDS = 500            # bunun altı "veri bozuk" sayılır
DC = {"type2_combo", "type1_combo", "chademo", "tesla_supercharger", "tesla_supercharger_ccs"}
AC = {"type2", "type1", "schuko", "tesla_destination"}
NAMES = {"type2": "Type 2", "type2_combo": "CCS", "type1_combo": "CCS 1", "chademo": "CHAdeMO",
         "type1": "Type 1", "tesla_supercharger": "Tesla", "tesla_supercharger_ccs": "Tesla",
         "tesla_destination": "Tesla", "schuko": "Schuko"}


def fetch():
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last = None
    for attempt in range(3):
        for url in SERVERS:
            try:
                req = urllib.request.Request(url, data=body, headers={"User-Agent": "wattkac-istasyon-cek/1.0 (+https://wattkac.com)"})
                with urllib.request.urlopen(req, timeout=300) as r:
                    j = json.load(r)
                rem = str(j.get("remark", ""))
                if rem:
                    print(f"{url} uyarı: {rem[:200]}", file=sys.stderr)
                if re.search(r"error|timed out|out of memory", rem, re.I):
                    raise RuntimeError("kısmi sonuç: " + rem[:120])
                if isinstance(j.get("elements"), list) and len(j["elements"]) >= MIN_RECORDS:
                    print(f"{url}: {len(j['elements'])} kayıt")
                    return j["elements"]
                last = f"{url}: yetersiz kayıt"
            except Exception as e:  # noqa: BLE001
                last = f"{url}: {e}"
            print("başarısız ->", last, file=sys.stderr)
        time.sleep(30 * (attempt + 1))
    raise SystemExit("Overpass'tan veri alınamadı: " + str(last))


def kw_of(v):
    m = re.search(r"([\d.,]+)\s*(k?w)?", str(v), re.I)
    if not m:
        return 0
    try:
        x = float(m.group(1).replace(",", "."))
    except ValueError:
        return 0
    return x / 1000 if (m.group(2) or "").lower() == "w" else x


def parse(el):
    t = el.get("tags") or {}
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    kw, types, ac, dc = 0.0, [], False, False
    for k, v in t.items():
        m = re.fullmatch(r"socket:([a-z0-9_]+):output", k)
        if m:
            kw = max(kw, kw_of(v))
            continue
        m = re.fullmatch(r"socket:([a-z0-9_]+)", k)
        if m and v not in ("no", "0") and m.group(1) in NAMES:
            if NAMES[m.group(1)] not in types:
                types.append(NAMES[m.group(1)])
            dc = dc or m.group(1) in DC
            ac = ac or m.group(1) in AC
    if not ac and not dc and kw > 0:
        dc, ac = (kw >= 40), (kw < 40)
    cap = re.match(r"\d+", t.get("capacity", ""))
    addr = ", ".join(x for x in [t.get("addr:street"), t.get("addr:suburb") or t.get("addr:district"), t.get("addr:city")] if x)
    web = t.get("website") or t.get("contact:website") or ""
    rec = {
        "i": f"{el['type'][0]}{el['id']}",
        "a": round(lat, 5), "o": round(lon, 5),
        "n": (t.get("name") or "").strip(),
        "b": (t.get("brand") or "").strip(),
        "p": (t.get("operator") or "").strip(),
        "w": (t.get("network") or "").strip(),
        "k": round(kw) if kw else 0,
        "t": types,
        "ac": int(ac), "dc": int(dc),
        "c": int(cap.group()) if cap else 0,
        "ad": addr,
        "h": t.get("opening_hours", "")[:80],
        "u": web if re.match(r"https?://", web) else "",
    }
    return {k: v for k, v in rec.items() if v not in ("", 0, [], None) or k in ("a", "o", "i")}


def main():
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site/istasyonlar.json")
    recs = [r for r in (parse(e) for e in fetch()) if r]
    recs.sort(key=lambda r: (round(r["a"], 1), r["o"], r["i"]))
    brands = {}
    for r in recs:
        b = r.get("b") or r.get("p") or r.get("w") or ""
        if b:
            brands[b] = brands.get(b, 0) + 1
    data = {"guncelleme": datetime.date.today().isoformat(), "kaynak": "© OpenStreetMap katkıda bulunanlar (ODbL)",
            "sayi": len(recs), "markalar": dict(sorted(brands.items(), key=lambda x: -x[1])[:60]), "istasyonlar": recs}
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    old = out.read_text(encoding="utf-8") if out.exists() else ""
    # yalnızca içerik değiştiyse (tarih hariç) yaz; gereksiz commit oluşmasın
    strip = lambda s: re.sub(r'"guncelleme":"[^"]*",', "", s, count=1)
    if strip(old) == strip(txt):
        print("Değişiklik yok.")
        return
    out.write_text(txt, encoding="utf-8")
    print(f"{out}: {len(recs)} istasyon, {len(txt) // 1024} KB")


if __name__ == "__main__":
    main()
