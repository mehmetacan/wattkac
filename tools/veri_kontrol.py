#!/usr/bin/env python3
"""Kampanya ve fiyat verisinin sağlığını denetler; hiçbir dosyayı değiştirmez.

  python3 tools/veri_kontrol.py            # yapı + güncellik denetimi
  python3 tools/veri_kontrol.py --yapi     # yalnızca yapı (push/PR denetimi için)

HATA (çıkış kodu 1): sitede yanlış bilgi gösterecek durumlar
  - eksik/bozuk alan, resmi olmayan (derleme sitesi) bağlantı, süresi dolmuş kampanya, ters fiyat aralığı
  - günlük tarama 2 günden uzun süredir çalışmamış (son_kontrol eski)
UYARI: gözden geçirilmesi iyi olan durumlar
  - "kontrol": true (resmi sayfası açılamamış) kampanyalar, 7 günden eski fiyat kontrolü, fiyatı olmayan ağlar

Girdiler: data/kampanyalar.json, site/tarifeler.json
"""
import datetime, json, pathlib, re, sys

KOK = pathlib.Path(__file__).resolve().parent.parent
DERLEME = ("sarjharitasi", "sarjevi", "hangikredi", "sarjkampanya", "arabamsarj", "e-aracsarj", "donanimhaber")
TARIH = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALL = "Tüm şarj istasyonları"
TARAMA_GUN = 2   # günlük tarama en fazla bu kadar gün gecikebilir
FIYAT_GUN = 7    # fiyatlar en fazla bu kadar gün kontrolsüz kalabilir

hatalar, uyarilar = [], []
hata, uyari = hatalar.append, uyarilar.append


def bugun_tr():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)).date()


def gun_farki(iso, bugun):
    return (bugun - datetime.date.fromisoformat(iso)).days


def teklif_denetle(yer, o, bugun, banka):
    for alan in ("big", "det", "link"):
        if not str(o.get(alan) or "").strip():
            hata(f"{yer}: '{alan}' boş")
    link = str(o.get("link") or "")
    if link and not link.startswith("https://"):
        hata(f"{yer}: bağlantı https:// ile başlamıyor ({link[:60]})")
    if any(d in link for d in DERLEME):
        hata(f"{yer}: bağlantı derleme sitesine gidiyor, resmi sayfa olmalı ({link[:60]})")
    bas, bit = o.get("bas") or "", o.get("bit") or ""
    for ad, v in (("bas", bas), ("bit", bit)):
        if v and not TARIH.match(v):
            hata(f"{yer}: '{ad}' YYYY-AA-GG biçiminde değil ({v})")
    if bit and TARIH.match(bit):
        if datetime.date.fromisoformat(bit) < bugun:
            hata(f"{yer}: süresi dolmuş ({bit}); veriden çıkarılmalı")
        if bas and TARIH.match(bas) and bas > bit:
            hata(f"{yer}: başlangıç ({bas}) bitişten ({bit}) sonra")
    if not bit and o.get("son") != "Süreli değil":
        uyari(f"{yer}: bitiş tarihi yok ama 'son' alanı \"Süreli değil\" değil ({o.get('son')!r})")
    ek = o.get("eklendi")
    if ek and not TARIH.match(ek):
        hata(f"{yer}: 'eklendi' YYYY-AA-GG biçiminde değil ({ek})")
    if banka and not o.get("st"):
        hata(f"{yer}: geçerli istasyon listesi (st) boş")
    if o.get("kontrol"):
        uyari(f"{yer}: resmi sayfası açılamamış (\"kontrol\": true); sitede 'Doğrulanıyor' etiketiyle görünür")


def kampanyalar(bugun, guncellik):
    d = json.loads((KOK / "data/kampanyalar.json").read_text(encoding="utf-8"))
    for alan in ("donem", "guncelleme", "bankalar", "istasyonlar"):
        if alan not in d:
            hata(f"kampanyalar.json: '{alan}' yok")
    if not TARIH.match(d.get("guncelleme") or ""):
        hata("kampanyalar.json: 'guncelleme' YYYY-AA-GG biçiminde değil")
    idler, ag_adlari, st_banka = set(), set(), {}
    for s in d.get("istasyonlar", []):
        ag_adlari.add(s.get("name"))
    for b in d.get("bankalar", []):
        yer = f"banka {b.get('id')}"
        if b.get("id") in idler:
            hata(f"{yer}: id tekrar ediyor")
        idler.add(b.get("id"))
        for alan in ("id", "name", "offers"):
            if not b.get(alan):
                hata(f"{yer}: '{alan}' boş")
        for i, o in enumerate(b.get("offers", [])):
            teklif_denetle(f"{yer} #{i + 1} ({o.get('big')})", o, bugun, True)
            for st in o.get("st", []):
                if st != ALL:
                    st_banka.setdefault(st, set()).add(b.get("id"))
    for s in d.get("istasyonlar", []):
        yer = f"ağ {s.get('id')}"
        if s.get("id") in idler:
            hata(f"{yer}: id tekrar ediyor")
        idler.add(s.get("id"))
        for i, o in enumerate(s.get("own", [])):
            teklif_denetle(f"{yer} #{i + 1} ({o.get('big')})", o, bugun, False)
            # isteğe bağlı kısa koşul etiketi (sitede istasyon detayında): 1–3 kelime, yüzde yok
            if "kisa" in o:
                k = o.get("kisa")
                if not isinstance(k, str) or not k.strip():
                    hata(f"{yer} #{i + 1}: 'kisa' boş ya da metin değil")
                elif len(k) > 32 or len(k.split()) > 4:
                    uyari(f"{yer} #{i + 1}: 'kisa' uzun ({k!r}); 1–3 kelimelik koşul olmalı")
                elif "%" in k:
                    uyari(f"{yer} #{i + 1}: 'kisa' yüzde içeriyor ({k!r}); oran sitede ayrıca hesaplanır")
        if not s.get("own") and not s.get("banks"):
            uyari(f"{yer}: ne kendi indirimi ne banka kampanyası var; listeden çıkarılabilir")
        if s.get("banks") and not any(str(s.get("name")) in st for st in st_banka):
            uyari(f"{yer}: 'banks' dolu ama hiçbir banka kampanyasının st listesinde {s.get('name')!r} yok")
    sk = d.get("son_kontrol")
    if sk and not TARIH.match(sk):
        hata("kampanyalar.json: 'son_kontrol' YYYY-AA-GG biçiminde değil")
    if guncellik:
        son = sk or d.get("guncelleme")
        if son and TARIH.match(son) and gun_farki(son, bugun) > TARAMA_GUN:
            hata(f"Günlük tarama {gun_farki(son, bugun)} gündür çalışmamış (son kontrol: {son}); zamanlanmış görevi kontrol et")
    return ag_adlari


def tarifeler(bugun, guncellik, ag_adlari):
    t = json.loads((KOK / "site/tarifeler.json").read_text(encoding="utf-8"))
    for ag, x in (t.get("aglar") or {}).items():
        yer = f"fiyat {ag}"
        if not str(x.get("kaynak") or "").startswith("https://"):
            hata(f"{yer}: resmi 'kaynak' bağlantısı yok")
        dolu = False
        for tur in ("ac", "dc"):
            p = x.get(tur)
            if p is None:
                continue
            dolu = True
            mn, mx = (p, p) if isinstance(p, (int, float)) else (p.get("min"), p.get("max", p.get("min")))
            if not isinstance(mn, (int, float)) or not isinstance(mx, (int, float)):
                hata(f"{yer}: {tur} fiyatı sayı değil")
            elif mn > mx:
                hata(f"{yer}: {tur} en düşük fiyat ({mn}) en yüksekten ({mx}) büyük")
            elif not 1 <= mn <= 100 or not 1 <= mx <= 100:
                hata(f"{yer}: {tur} fiyatı makul aralıkta değil ({mn}–{mx} TL/kWh)")
        if not dolu:
            uyari(f"{yer}: fiyat yok (haritada 'fiyat yok' görünür); elle doğrulanmalı")
            continue
        k = x.get("kontrol")
        if not k or not TARIH.match(k):
            hata(f"{yer}: fiyat var ama 'kontrol' tarihi yok")
        elif guncellik and gun_farki(k, bugun) > FIYAT_GUN:
            uyari(f"{yer}: fiyat {gun_farki(k, bugun)} gündür kontrol edilmemiş (son: {k})")
    for ag in sorted(a for a in ag_adlari if a and a not in (t.get("aglar") or {})):
        uyari(f"fiyat {ag}: tarifeler.json'da kaydı yok")


def main():
    guncellik = "--yapi" not in sys.argv
    bugun = bugun_tr()
    try:
        aglar = kampanyalar(bugun, guncellik)
        tarifeler(bugun, guncellik, aglar)
    except (OSError, ValueError) as ex:
        hata(f"Dosya okunamadı: {ex}")
    for u in uyarilar:
        print(f"::warning::{u}")
    for h in hatalar:
        print(f"::error::{h}")
    print(f"\n{bugun}: {len(hatalar)} hata, {len(uyarilar)} uyarı")
    return 1 if hatalar else 0


if __name__ == "__main__":
    sys.exit(main())
