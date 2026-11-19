#!/usr/bin/env python3
"""Harita konum araması için il / ilçe listesi üretir: site/yerler.json

Kaynak: geoBoundaries gbOpen TUR ADM1 (iller) ve ADM2 (ilçeler), sadeleştirilmiş sınırlar.
geoBoundaries bu katmanları OpenStreetMap'ten (osm-boundaries.com) alır; lisans ODbL 1.0
(© OpenStreetMap katkıcıları — atıf sitede harita altında zaten var).

Çıktı (küçük tutulur, koordinatlar 3 ondalık ≈ 100 m):
  {"kaynak": ..., "lisans": "ODbL 1.0", "iller": [[ad, lat, lon, güney, batı, kuzey, doğu], ...],
   "ilceler": [[ad, il_sırası, lat, lon, güney, batı, kuzey, doğu], ...]}
lat/lon: sınırın ağırlık merkezi (çok parçalıysa en büyük parça); il_sırası: "iller" dizisindeki sıra.
Bir ilçenin ili, ilçenin merkez noktasını içeren il sınırıdır.

Kullanım: python3 tools/yerler_uret.py  [--yerel KLASÖR]   (KLASÖR'de ADM1.geojson / ADM2.geojson varsa indirilmez)
"""
import json, sys, os, re, urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/TUR/{L}/geoBoundaries-TUR-{L}_simplified.geojson"

# geoBoundaries / OSM yazımı → sitedeki il listesindeki yazım
IL_AD = {"Afyon": "Afyonkarahisar", "Icel": "Mersin", "İçel": "Mersin", "K. Maras": "Kahramanmaraş", "Kahramanmaras": "Kahramanmaraş", "Hakkâri": "Hakkari"}
# OSM'deki İngilizce / bozuk ilçe adları
ILCE_AD = {"Prince Islands": "Adalar", "Giresun District": "Merkez", "Gediz Merkez": "Gediz"}
MERKEZ = re.compile(r"\s*\(?\s*merkez(i|\s+ilçe)?\s*\)?\s*$", re.I)


def ilce_adi(ad, il):
    """Merkez ilçeler tek yazımla: "Bolu Merkez", "Kilis (merkez)", "Rize merkezi", "Ardahan" → "Merkez" """
    ad = ILCE_AD.get(ad, ad)
    k = MERKEZ.sub("", ad).strip()
    return "Merkez" if not k or k == il or IL_AD.get(k) == il else ad


def yukle(L, yerel):
    if yerel and os.path.exists(os.path.join(yerel, L + ".geojson")):
        return json.load(open(os.path.join(yerel, L + ".geojson"), encoding="utf-8"))
    req = urllib.request.Request(URL.format(L=L), headers={"User-Agent": "wattkac-yerler/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def halkalar(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def alan_merkez(ring):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        k = x1 * y2 - x2 * y1
        a += k; cx += (x1 + x2) * k; cy += (y1 + y2) * k
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return abs(a) / 2, cx / (3 * a), cy / (3 * a)


def ozet(geom):
    polys = halkalar(geom)
    pts = [p for poly in polys for p in poly[0]]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    buyuk = max((alan_merkez(poly[0]) for poly in polys), key=lambda t: t[0])
    lon, lat = buyuk[1], buyuk[2]
    # merkez parçanın dışına düşerse (hilal biçimli ilçe) parçadaki bir noktaya yakın kalsın diye kutu ortası kullanılmaz; olduğu gibi bırakılır
    return [round(lat, 3), round(lon, 3), round(min(ys), 3), round(min(xs), 3), round(max(ys), 3), round(max(xs), 3)]


def icinde(lon, lat, geom):
    for poly in halkalar(geom):
        ic = False
        for ring_i, ring in enumerate(poly):
            r = False
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                    r = not r
            if ring_i == 0:
                ic = r
            elif r:
                ic = False
        if ic:
            return True
    return False


def main():
    yerel = sys.argv[sys.argv.index("--yerel") + 1] if "--yerel" in sys.argv else None
    a1, a2 = yukle("ADM1", yerel), yukle("ADM2", yerel)
    iller = []
    for f in sorted(a1["features"], key=lambda f: f["properties"]["shapeName"]):
        ad = f["properties"]["shapeName"].strip()
        iller.append([IL_AD.get(ad, ad)] + ozet(f["geometry"]))
    geo1 = sorted(a1["features"], key=lambda f: f["properties"]["shapeName"])
    ilceler, bos = [], []
    for f in a2["features"]:
        ad = f["properties"]["shapeName"].strip()
        o = ozet(f["geometry"])
        lat, lon = o[0], o[1]
        il = next((i for i, g in enumerate(geo1) if icinde(lon, lat, g["geometry"])), None)
        if il is None:   # merkez noktası sınırın dışında (kıyı, hilal biçimli ilçe): sınır noktası en yakın il
            il = min(range(len(geo1)), key=lambda i: min((x - lon) ** 2 + (y - lat) ** 2
                                                         for poly in halkalar(geo1[i]["geometry"]) for x, y in poly[0]))
            bos.append(ad)
        ilceler.append([ilce_adi(ad, iller[il][0]), il] + o)
    # aynı il + aynı ad (çok parçalı kayıt) tek satır: kutular birleşir
    tek = {}
    for r in ilceler:
        k = (r[0], r[1])
        if k in tek:
            t = tek[k]; t[4] = min(t[4], r[4]); t[5] = min(t[5], r[5]); t[6] = max(t[6], r[6]); t[7] = max(t[7], r[7])
        else:
            tek[k] = r
    ilceler = sorted(tek.values(), key=lambda r: (r[1], r[0]))
    out = {"kaynak": "geoBoundaries gbOpen TUR ADM1/ADM2 (OpenStreetMap, osm-boundaries.com)", "lisans": "ODbL 1.0 · © OpenStreetMap katkıcıları",
           "iller": iller, "ilceler": ilceler}
    yol = os.path.join(KOK, "site", "yerler.json")
    with open(yol, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(iller)} il, {len(ilceler)} ilçe → {yol} ({os.path.getsize(yol)} bayt)")
    if bos:
        print("Merkezi il sınırı dışında kalan (sınırı en yakın ile atanan) ilçeler:", ", ".join(bos))


if __name__ == "__main__":
    main()
