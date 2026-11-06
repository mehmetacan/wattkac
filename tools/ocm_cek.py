#!/usr/bin/env python3
"""Open Charge Map (OCM) üzerinden Türkiye'deki şarj istasyonlarını çeker.

Lisans: OCM katkıcı verisi CC BY 4.0 (atıf: "© Open Charge Map"). Bazı kayıtlar başka veri sağlayıcılardan
gelir ve kendi lisansları vardır; yalnızca lisansı açık (CC BY / CC0 / ODbL / Open) sağlayıcıların kayıtları alınır.
API anahtarı OCM_API_KEY ortam değişkeninden okunur (GitHub Actions secret).

Çıktı: data/ocm/istasyonlar_ocm.json  (istasyon_cek.py ile aynı kayıt biçimi)
Kullanım: python3 tools/ocm_cek.py [çıktı] [--ozet]
"""
import json, os, pathlib, re, sys, urllib.parse, urllib.request, datetime, collections

API = "https://api.openchargemap.io/v3/poi/"
UA = "WattKac/1.0 (+https://wattkac.com)"
OPEN_LICENSE = re.compile(r"Creative Commons Attribution|CC[\s-]?BY|CC[\s-]?0|ODbL|Open Data|Public Domain|Open Government", re.I)
DC_TYPES = re.compile(r"CCS|CHAdeMO|Supercharger|Combo|GB/T DC", re.I)


def fetch(key):
    q = {"output": "json", "countrycode": "TR", "maxresults": 20000, "compact": "false", "verbose": "false",
         "includecomments": "false", "key": key}
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={"User-Agent": UA, "X-API-Key": key})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def conv(p):
    ai = p.get("AddressInfo") or {}
    a, o = ai.get("Latitude"), ai.get("Longitude")
    if not isinstance(a, (int, float)) or not isinstance(o, (int, float)):
        return None
    op = ((p.get("OperatorInfo") or {}).get("Title") or "").strip()
    if op.lower() in ("(unknown operator)", "unknown", "(business owner at location)"):
        op = ""
    types, kw, ac, dc, cnt = [], 0.0, False, False, 0
    for c in p.get("Connections") or []:
        t = ((c.get("ConnectionType") or {}).get("Title") or "").strip()
        cur = ((c.get("CurrentType") or {}).get("Title") or "")
        pk = c.get("PowerKW") or 0
        short = "CCS" if re.search(r"CCS|Combo", t, re.I) else "CHAdeMO" if "CHAdeMO" in t else "Type 2" if re.search(r"Type 2|Mennekes", t, re.I) else "Tesla" if "Tesla" in t else ""
        if short and short not in types:
            types.append(short)
        is_dc = "DC" in cur or bool(DC_TYPES.search(t)) or (pk and pk >= 40)
        dc, ac = dc or is_dc, ac or (not is_dc and bool(t or cur))
        kw = max(kw, float(pk or 0))
        cnt += int(c.get("Quantity") or 1)
    addr = ", ".join(x for x in [ai.get("AddressLine1"), ai.get("Town"), ai.get("StateOrProvince")] if x)
    rec = {"i": f"ocm{p['ID']}", "a": round(a, 5), "o": round(o, 5), "n": (ai.get("Title") or "").strip(), "p": op,
           "k": round(kw), "t": types, "ac": int(ac), "dc": int(dc), "c": cnt, "ad": addr.strip()}
    return {k: v for k, v in rec.items() if v not in ("", 0, [], None) or k in ("a", "o", "i")}


def main():
    key = os.environ.get("OCM_API_KEY", "").strip()
    if not key:
        sys.exit("OCM_API_KEY tanımlı değil")
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    out = pathlib.Path(args[0] if args else "data/ocm/istasyonlar_ocm.json")
    pois = fetch(key)
    lic = collections.Counter()
    recs, skipped = [], 0
    for p in pois:
        dp = p.get("DataProvider") or {}
        license_ = dp.get("License") or ""
        lic[f"{dp.get('Title')} | {license_[:60]}"] += 1
        if license_ and (not OPEN_LICENSE.search(license_) or re.search(r"NonCommercial|\bNC\b", license_, re.I)):
            skipped += 1
            continue
        if (p.get("UsageType") or {}).get("IsPrivateIndividuals") or (p.get("StatusType") or {}).get("IsOperational") is False:
            continue
        r = conv(p)
        if r:
            recs.append(r)
    print(f"OCM: {len(pois)} kayıt, alınan {len(recs)}, lisans nedeniyle atlanan {skipped}")
    print("Veri sağlayıcıları:", dict(lic.most_common(8)))
    ops = collections.Counter(r.get("p", "(belirsiz)") for r in recs)
    print("İşletmeciler:", ops.most_common(30))
    if "--ozet" in sys.argv:
        return
    if len(recs) < 50:
        sys.exit("Çok az kayıt; dosya güncellenmedi")
    out.parent.mkdir(parents=True, exist_ok=True)
    recs.sort(key=lambda r: r["i"])
    out.write_text(json.dumps({"kaynak": "© Open Charge Map katkıda bulunanlar (CC BY 4.0)", "cekildi": datetime.date.today().isoformat(),
                               "sayi": len(recs), "istasyonlar": recs}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{out}: {len(recs)} istasyon")


if __name__ == "__main__":
    main()
