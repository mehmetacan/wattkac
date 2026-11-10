#!/usr/bin/env python3
"""EPDK'nın herkese açık şarj istasyonu servisinden halka açık istasyonları çeker → data/epdk/epdk_api.json

Kaynak : https://apigateway.epdk.gov.tr/sarjIstasyonlari (Şarj@TR / Serbest Erişim Platformu verisi; giriş ya da anahtar gerektirmez)
Verdiği: istasyon no, ad, marka, şarj ağı işletmecisi, adres, KESİN koordinat, soketler (tür + güç). Fiyat ve anlık durum YOK.

Servis gövdeli GET ({} = filtresiz) bekler ve kotası dardır (istemci başına yaklaşık günde bir tam indirme; aşılınca 429).
Bu yüzden her çalıştırmada TEK istek atılır, tekrar denenmez; hata olursa önceki dosya olduğu gibi korunur.
"sarjIstasyonuIsletmecisi" alanı kişi adı içerebildiği için (KVKK) alınmaz. Özel (halka açık olmayan) istasyonlar kaydedilmez.

Kullanım:
  python3 tools/epdk_cek.py                   # EPDK'dan çek
  python3 tools/epdk_cek.py --ham dosya.json  # istek atmadan, kayıtlı ham yanıttan üret (test için)

Kayıt: {"no","ad","marka","isletmeci","adres","a","o","yesil"?, "s":[[tur, kW, adet], ...]}   tur: AC_TYPE2 | DC_CCS | DC_CHADEMO ...
"""
import datetime, http.client, json, pathlib, sys

HOST, YOL = "apigateway.epdk.gov.tr", "/sarjIstasyonlari"
OUT = pathlib.Path("data/epdk/epdk_api.json")
UA = "WattKac/1.0 (+https://wattkac.com; gunluk istasyon listesi)"
EN_AZ = 5000  # bundan az halka açık istasyon dönerse yanıt eksik sayılır, eski veri korunur


def cek():
    c = http.client.HTTPSConnection(HOST, timeout=180)
    try:
        c.request("GET", YOL, body=b"{}", headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA})
        r = c.getresponse()
        govde = r.read()
    finally:
        c.close()
    if r.status != 200:
        raise RuntimeError(f"HTTP {r.status}: {govde[:200]!r}")
    return govde


def sayi(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def donustur(ham):
    j = json.loads(ham)
    satirlar = j.get("data") if isinstance(j, dict) else j
    if not isinstance(satirlar, list) or not satirlar:
        raise RuntimeError(f"beklenmeyen yanıt: {str(j)[:200]}")
    out, ozel, konumsuz = [], 0, 0
    for x in satirlar:
        if str(x.get("hizmetSekli") or "").upper() != "HALKA_ACIK":
            ozel += 1
            continue
        a, o, no = x.get("enlem"), x.get("boylam"), str(x.get("sarjIstasyonuNo") or "").strip()
        if not no or not isinstance(a, (int, float)) or not isinstance(o, (int, float)) or not (35 < a < 43 and 25 < o < 45.5):
            konumsuz += 1
            continue
        grup = {}
        for s in x.get("soketler") or []:
            tur = str(s.get("soketTuru") or s.get("soketTipi") or "").strip().upper()
            kw = sayi(s.get("soketGucu"))
            if tur:
                k = (tur, kw if kw and 0 < kw <= 1000 else None)
                grup[k] = grup.get(k, 0) + 1
        rec = {"no": no, "ad": str(x.get("sarjIstasyonuAdi") or "").strip(), "marka": str(x.get("marka") or "").strip(),
               "isletmeci": str(x.get("sarjAgiIsletmecisiUnvan") or "").strip(), "adres": str(x.get("adres") or "").strip(),
               "a": round(a, 6), "o": round(o, 6),
               "s": [[t, (int(k) if k is not None and k == int(k) else k), n] for (t, k), n in sorted(grup.items(), key=lambda z: (z[0][0], z[0][1] or 0))]}
        if str(x.get("yesilSarjIstasyonuMu") or "").upper() == "EVET":
            rec["yesil"] = 1
        out.append(rec)
    out.sort(key=lambda r: r["no"])
    return out, ozel, konumsuz


def main():
    try:
        ham = pathlib.Path(sys.argv[2]).read_bytes() if len(sys.argv) > 2 and sys.argv[1] == "--ham" else cek()
        kayitlar, ozel, konumsuz = donustur(ham)
        if len(kayitlar) < EN_AZ:
            raise RuntimeError(f"yalnızca {len(kayitlar)} halka açık istasyon döndü (en az {EN_AZ} bekleniyor)")
    except Exception as ex:  # noqa: BLE001 - önceki veri korunur; iş akışı durmaz
        print(f"::warning::EPDK verisi alınamadı, önceki veri korunuyor: {ex}")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    veri = {"kaynak": f"https://{HOST}{YOL}", "cekildi": datetime.date.today().isoformat(), "sayi": len(kayitlar), "istasyonlar": kayitlar}
    OUT.write_text(json.dumps(veri, ensure_ascii=False, separators=(",", ":")).replace('},{"no"', '},\n{"no"'), encoding="utf-8")
    soket = sum(n for r in kayitlar for _, _, n in r["s"])
    print(f"EPDK: {len(kayitlar)} halka açık istasyon, {soket} soket (özel {ozel}, konumsuz {konumsuz} atlandı) → {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
