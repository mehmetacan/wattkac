#!/usr/bin/env python3
"""Şarj ağlarının KENDİ resmi web sitelerindeki haritaların herkese açık (giriş/anahtar gerektirmeyen)
veri kaynaklarından istasyon listelerini çeker ve data/aglar/<ag>.json olarak kaydeder.

Kaynaklar (her biri ağın kendi sitesindeki haritanın kullandığı adres):
  ZES          https://zes.net/Station/MarkerSet                       (zes.net/tr/sarj-istasyonlari)
  Ovolt/Sharz  https://mobil-api.ovolt.com.tr/api/App/stations/cards   (ovolt.com.tr/istasyon-haritasi)
  WAT Mobilite https://www.watmobilite.com/istasyon-haritasi           (sayfa içindeki istasyon kartları)
  Trugo        https://trugo.com.tr/individual/network                  (sayfanın kendi içindeki __NUXT_DATA__ istasyon listesi)
  (ASTOR Şarj'ın haritası map-api.echargo.com kullanıyor ama sunucudan yapılan istekleri reddediyor (HTTP 404);
   erişim kısıtını aşmaya çalışmıyoruz, ASTOR istasyonları EPDK + OSM'den gelir.)

Kurallar: günde bir kez, her kaynağa tek istek; anahtar/oturum gerektiren kaynaklar KULLANILMAZ.
Bir ağın çekimi başarısız olursa o ağın önceki dosyası korunur.
Kayıt alanları istasyon_cek.py ile aynıdır (i, a, o, n, b, k, t, ac, dc, c, ad) + pr (soket fiyatları, varsa).
"""
import html, json, pathlib, re, sys, urllib.request, datetime

OUT = pathlib.Path("data/aglar")
UA = "WattKac/1.0 (+https://wattkac.com; gunluk istasyon listesi)"


def get(url, data=None, headers=None, timeout=60):
    h = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9"}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def ok_coord(a, o):
    return isinstance(a, (int, float)) and isinstance(o, (int, float)) and 35 < a < 43 and 25 < o < 45.5


def clean(d):
    return {k: v for k, v in d.items() if v not in ("", None, [], 0) or k in ("a", "o", "i")}


def zes():
    j = json.loads(get("https://zes.net/Station/MarkerSet"))
    out = []
    for s in j:
        a, o = s.get("latitude"), s.get("longitude")
        if not ok_coord(a, o):
            continue
        ac, dc, hpc = s.get("acConnectorCount") or 0, s.get("dcConnectorCount") or 0, s.get("hpcConnectorCount") or 0
        t = (["Type 2"] if ac else []) + (["CCS"] if dc or hpc else [])
        out.append(clean({"i": f"zes{s['id']}", "a": round(a, 5), "o": round(o, 5), "n": (s.get("name") or "").strip(), "b": "ZES",
                          "ac": int(ac > 0), "dc": int(dc + hpc > 0), "c": ac + dc + hpc, "t": t, "k": 150 if hpc else 0,
                          "bakim": int(bool(s.get("isInMaintenance")))}))
    return out


def ovolt():
    j = json.loads(get("https://mobil-api.ovolt.com.tr/api/App/stations/cards", data=[]))
    items = (j.get("result") or {}).get("stations") or j.get("stations") or []
    out = []
    tot = lambda x: int(str((x or {}).get("text", "0/0")).split("/")[-1] or 0) if re.match(r"^\d+/\d+$", str((x or {}).get("text", ""))) else 0
    for s in items:
        a, o = s.get("lat"), s.get("lon")
        if not ok_coord(a, o):
            continue
        nac, ndc = tot(s.get("ac")), tot(s.get("dc"))
        powers = [p for p in (s.get("powers") or []) if isinstance(p, (int, float))]
        adr = " ".join(x.replace("\t", " ").strip() for x in (s.get("address") or []) if isinstance(x, str))
        out.append(clean({"i": f"ovolt{s['id']}", "a": round(a, 5), "o": round(o, 5), "n": (s.get("name") or "").strip(), "b": "Ovolt",
                          "ac": int(nac > 0), "dc": int(ndc > 0), "c": nac + ndc, "k": round(max(powers)) if powers else 0,
                          "t": (["Type 2"] if nac else []) + (["CCS"] if ndc else []), "ad": re.sub(r"\s+", " ", adr)}))
    return out


def wat():
    page = get("https://www.watmobilite.com/istasyon-haritasi")
    out = []
    for part in page.split('<div class="kart ')[1:]:
        end = part.find(">")
        head, inner = part[:end], part[end + 1:part.find('<div class="right">')]
        cls = head.split('"')[0].split()
        la = re.search(r'data-lat="\s*([-\d.]+)\s*"', head)
        lo = re.search(r'data-lng="\s*([-\d.]+)\s*"', head)
        kid = re.search(r'kart-id="\s*(\d+)', head)
        if not (la and lo and kid):
            continue
        try:
            a, o = float(la.group(1)), float(lo.group(1))
        except ValueError:
            continue
        kid = kid.group(1)
        if "ozel-kullanim" in cls or not ok_coord(a, o):
            continue
        txt = lambda c: html.unescape(re.sub(r"<[^>]+>", "", (re.search(rf'class="{c}">(.*?)</', inner, re.S) or [None, ""])[1])).strip()
        has_ac, has_dc = "ac" in cls or "ac-dc" in cls, "dc" in cls or "ac-dc" in cls
        adr = ", ".join(x for x in [re.sub(r"\s+", " ", txt("adres")), txt("sehir")] if x)
        out.append(clean({"i": f"wat{kid}", "a": round(a, 5), "o": round(o, 5), "n": txt("baslik"), "b": "WAT Mobilite",
                          "ac": int(has_ac), "dc": int(has_dc), "t": (["Type 2"] if has_ac else []) + (["CCS"] if has_dc else []), "ad": adr}))
    return out


def astor():
    j = json.loads(get("https://map-api.echargo.com/api/app/list", headers={"X-Requested-With": "XMLHttpRequest"},
                       data={"pageNumber": 1, "count": 10000, "isActive": None, "displayName": None, "connectorType": None, "cityId": None, "countyId": None}))
    if j.get("state") != 0:
        raise RuntimeError("ASTOR yanıtı: " + str(j.get("message")))
    out = []
    for s in (j.get("result") or {}).get("items") or []:
        a, o = s.get("latitude"), s.get("longitude")
        if not ok_coord(a, o) or s.get("isPublic") is False:
            continue
        cons = s.get("connectors") or []
        acs = [c for c in cons if c.get("type") == 1]
        dcs = [c for c in cons if c.get("type") == 2]
        price = lambda cs: min([c["tariff"]["energyPrice"] for c in cs if isinstance((c.get("tariff") or {}).get("energyPrice"), (int, float)) and c["tariff"]["energyPrice"] > 0] or [None], key=lambda x: x if x is not None else 1e9)
        pr = {k: v for k, v in (("ac", price(acs)), ("dc", price(dcs))) if v is not None}
        powers = [c.get("power") for c in cons if isinstance(c.get("power"), (int, float))]
        out.append(clean({"i": f"astor{s['id']}", "a": round(a, 5), "o": round(o, 5),
                          "n": (s.get("locationName") or s.get("displayName") or "").strip(), "b": "ASTOR Şarj",
                          "ac": int(bool(acs)), "dc": int(bool(dcs)), "c": len(cons), "k": round(max(powers)) if powers else 0,
                          "t": (["Type 2"] if acs else []) + (["CCS"] if dcs else []), "ad": (s.get("address") or "").strip(), "pr": pr}))
    return out


def trugo():
    page = get("https://trugo.com.tr/individual/network")
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise RuntimeError("__NUXT_DATA__ bulunamadı")
    arr = json.loads(m.group(1))

    def res(v, depth=0):  # Nuxt "devalue" biçimi: değerler dizideki indekslerdir
        if depth > 8 or not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < len(arr):
            return v
        x = arr[v]
        if isinstance(x, dict):
            return {k: res(y, depth + 1) for k, y in x.items()}
        if isinstance(x, list):
            if x and isinstance(x[0], str) and x[0] in ("Reactive", "ShallowReactive", "Ref", "ShallowRef"):
                return res(x[1], depth + 1)
            return [res(y, depth + 1) for y in x]
        return x

    out = []
    for i, x in enumerate(arr):
        if not (isinstance(x, dict) and "coordinates" in x and "chargingTypes" in x and "name" in x):
            continue
        s = res(i)
        co = s.get("coordinates") or []
        if len(co) != 2:
            continue
        o, a = co[0], co[1]
        if not ok_coord(a, o):
            continue
        types = " ".join(s.get("chargingTypes") or [])
        dc, ac = "DC" in types, "AC" in types
        out.append(clean({"i": f"trugo{s['id']}", "a": round(a, 6), "o": round(o, 6), "n": (s.get("name") or "").strip(), "b": "Trugo",
                          "ac": int(ac), "dc": int(dc), "t": (["Type 2"] if ac else []) + (["CCS"] if dc else []),
                          "ad": (s.get("district") or s.get("city") or "").strip(), "pasif": int(s.get("status") == 2)}))
    return out


SOURCES = {"trugo": (trugo, "https://trugo.com.tr/individual/network", 500),
           "zes": (zes, "https://zes.net/tr/sarj-istasyonlari", 500),
           "ovolt": (ovolt, "https://ovolt.com.tr/istasyon-haritasi", 50),
           "wat": (wat, "https://www.watmobilite.com/istasyon-haritasi", 100)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    failed = 0
    for key, (fn, page, minimum) in SOURCES.items():
        try:
            recs = fn()
            if len(recs) < minimum:
                raise RuntimeError(f"yalnızca {len(recs)} kayıt (beklenen ≥{minimum})")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"{key}: BAŞARISIZ ({e}); önceki dosya korunuyor", file=sys.stderr)
            continue
        recs.sort(key=lambda r: r["i"])
        f = OUT / f"{key}.json"
        data = {"ag": key, "kaynak": page, "cekildi": datetime.date.today().isoformat(), "sayi": len(recs), "istasyonlar": recs}
        f.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{key}: {len(recs)} istasyon")
    if failed == len(SOURCES):
        sys.exit("Hiçbir ağdan veri alınamadı")


if __name__ == "__main__":
    main()
