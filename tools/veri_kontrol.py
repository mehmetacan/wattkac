#!/usr/bin/env python3
"""Kampanya ve fiyat verisinin sağlığını denetler; hiçbir dosyayı değiştirmez.

  python3 tools/veri_kontrol.py            # yapı + güncellik denetimi
  python3 tools/veri_kontrol.py --yapi     # yalnızca yapı (push/PR denetimi için)

HATA (çıkış kodu 1): sitede yanlış bilgi gösterecek durumlar
  - eksik/bozuk alan, resmi olmayan (derleme sitesi) bağlantı, süresi dolmuş kampanya, ters fiyat aralığı
  - günlük tarama 2 günden uzun süredir çalışmamış (son_kontrol eski)
UYARI: gözden geçirilmesi iyi olan durumlar
  - "kontrol": true (resmi sayfası açılamamış) kampanyalar, 7 günden eski fiyat kontrolü, fiyatı olmayan ağlar
  - istasyon konum denetimi (tools/konum_denetim.py) haritadan istasyonların %1'inden fazlasını çıkarmış ya da
    %2'sinden fazlasının konumunu değiştirmiş: kaynak verisinde toplu bir bozulma olabilir
  - elle güncellenen ağ kopyası (ELLE_KOPYA: bot korumalı ya da iş akışına 403 veren kaynak, ör. data/aglar/5sarj.json,
    data/aglar/eka.json) KOPYA_GUN günden eski: haritada o ağın listesi/konumları kullanıldığından kullanıcıdan yeni kopya istenmeli

Girdiler: data/kampanyalar.json, site/tarifeler.json, site/uygulamalar.json, data/epdk/konum_duzeltmeleri.json, site/istasyonlar.json
"""
import datetime, json, pathlib, re, sys

KOK = pathlib.Path(__file__).resolve().parent.parent
DERLEME = ("sarjharitasi", "sarjevi", "hangikredi", "sarjkampanya", "arabamsarj", "e-aracsarj", "donanimhaber")
TARIH = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALL = "Tüm şarj istasyonları"
GUNLER = ("pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar")   # 'gunler' alanı: aksansız küçük harf
TARAMA_GUN = 2   # günlük tarama en fazla bu kadar gün gecikebilir
FIYAT_GUN = 7    # fiyatlar en fazla bu kadar gün kontrolsüz kalabilir
KONUM_CIKAN = 0.01    # konum denetiminin haritadan çıkardığı kayıt / istasyon sayısı bu oranı aşarsa uyarı
KONUM_DEGISEN = 0.02  # konumu değiştirilen kayıt oranı bunu aşarsa uyarı
KOPYA_GUN = 60        # elle güncellenen ağ kopyası en fazla bu kadar gün eski olabilir (sonra uyarı)
# Günlük iş akışının çekemediği (bot korumalı), kullanıcının tarayıcısından elle kopyalanan ağ listeleri: dosya → (ağ adı, ne istenmeli)
# (tek liste: yeni kopya ağı buraya eklenir; site metni için istasyon_birlestir.py "not" alanına bakar)
ELLE_KOPYA = {"5sarj": ("5 Şarj", "5sarj.com/api/locations/map-pins kopyası (tools/5sarj_kopya.py ile dönüştürülür)"),
              "eka": ("EKA Enerji", "ekaenerji.mapcontentpartners.service.electroop.io/2.2/locations kopyası "
                                    "(python3 tools/ag_istasyonlari.py eka --dosya <ocpi.json> ile dönüştürülür; electroop Actions'a 403 veriyor)"),
              # Günlük iş akışı electroop'tan çekmeyi dener; electroop GitHub Actions'a 403 verirse önceki dosya korunur ve liste elle
              # yenilenir (13 Kasım 2026'dan beri 403). İş akışı çekebildiği gün 'cekildi' kendiliğinden güncellenir.
              **{ag: (ad, f"{sirket}.mapcontentpartners.service.electroop.io/2.2/locations kopyası (python3 tools/ag_istasyonlari.py {ag} "
                          "--dosya <ocpi.json> ile dönüştürülür; electroop GitHub Actions'a 403 veriyor)")
                 for ag, ad, sirket in (("otopriz", "Otopriz", "otopriz"), ("neva", "Neva Şarj", "nevasarj"),
                                        ("lumicle", "Lumicle", "lumicle"), ("ecojet", "Ecojet", "ecojet"))}}

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
    # isteğe bağlı: yalnızca haftanın belli günlerinde geçerli (sitede bugün listede değilse haritada uygulanmaz)
    if "gunler" in o:
        g = o.get("gunler")
        if not isinstance(g, list) or not g or not all(isinstance(x, str) for x in g):
            hata(f"{yer}: 'gunler' boş olmayan bir liste olmalı")
        else:
            yanlis = [x for x in g if x not in GUNLER]
            if yanlis:
                hata(f"{yer}: 'gunler' geçersiz gün içeriyor ({', '.join(yanlis)}); geçerli: {', '.join(GUNLER)}")
            if len(set(g)) != len(g):
                hata(f"{yer}: 'gunler' tekrar eden gün içeriyor")


def fiyatlar_denetle(yer, o):
    """İsteğe bağlı 'fiyatlar' (uygulama kampanyası; yalnızca render.py okur, site kullanmaz): kampanya sahibinin kendi
    tablosundaki fiyatlar. {"kaynak", "tarih", "satirlar": [{"ag": <st'deki ad>, "ac": [liste, kampanya] | null, "dc": ...}]}.
    'big' "%N indirim" ise kampanya fiyatı liste × (1 − N/100) olmalı (2 hane, ±0,01). Liste fiyatı tarifeler.json'dan
    farklıysa uyarı (ağın fiyatı değişmiş olabilir; tablo yeniden alınmalı)."""
    f = o.get("fiyatlar")
    if not isinstance(f, dict) or not isinstance(f.get("satirlar"), list) or not f["satirlar"]:
        hata(f"{yer}: 'fiyatlar' {{kaynak, tarih, satirlar: [...]}} biçiminde olmalı")
        return
    if not str(f.get("kaynak") or "").strip():
        hata(f"{yer}: 'fiyatlar.kaynak' boş")
    if not TARIH.match(str(f.get("tarih") or "")):
        hata(f"{yer}: 'fiyatlar.tarih' YYYY-AA-GG biçiminde değil")
    m = re.match(r"^%(\d+(?:[.,]\d+)?)\s*indirim", str(o.get("big") or ""))
    oran = float(m.group(1).replace(",", ".")) / 100 if m else None
    t = json.loads((KOK / "site/tarifeler.json").read_text(encoding="utf-8")).get("aglar") or {}
    tarife = {ad_anahtari(a): x for k, x in t.items() for a in [k, *(x.get("adlar") or [])]}
    st, gorulen = set(o.get("st") or []), set()
    for r in f["satirlar"]:
        ag = r.get("ag") if isinstance(r, dict) else None
        if not ag:
            hata(f"{yer}: 'fiyatlar' içinde 'ag' boş satır")
            continue
        if ag not in st:
            hata(f"{yer}: 'fiyatlar' → {ag!r} teklifin st listesinde yok")
        if ag in gorulen:
            hata(f"{yer}: 'fiyatlar' → {ag!r} tekrar ediyor")
        gorulen.add(ag)
        if r.get("ac") is None and r.get("dc") is None:
            hata(f"{yer}: 'fiyatlar' → {ag}: ac ve dc ikisi de boş")
        for tur in ("ac", "dc"):
            p = r.get(tur)
            if p is None:
                continue
            if (not isinstance(p, list) or len(p) != 2 or not all(isinstance(v, (int, float)) for v in p)
                    or not all(1 <= v <= 100 for v in p)):
                hata(f"{yer}: 'fiyatlar' → {ag} {tur}: [liste, kampanya] iki makul sayı olmalı ({p})")
                continue
            liste, yeni = p
            if yeni > liste:
                hata(f"{yer}: 'fiyatlar' → {ag} {tur}: kampanya fiyatı ({yeni}) liste fiyatından ({liste}) yüksek")
            if oran is not None and abs(liste * (1 - oran) - yeni) > 0.0101:
                hata(f"{yer}: 'fiyatlar' → {ag} {tur}: {liste} × {1 - oran:.2f} = {liste * (1 - oran):.2f}, yazılan {yeni}")
            x = (tarife.get(ad_anahtari(ag)) or {}).get(tur)
            if isinstance(x, dict) and isinstance(x.get("min"), (int, float)) and not x["min"] <= liste <= x.get("max", x["min"]):
                uyari(f"{yer}: 'fiyatlar' → {ag} {tur} liste fiyatı {liste}, tarifeler.json'da {x['min']}–{x.get('max')}; "
                      "kampanya tablosu yeniden alınmalı")
    eksik = sorted(st - gorulen - {ALL})
    if eksik:
        uyari(f"{yer}: 'fiyatlar' tablosunda olmayan ağlar: {', '.join(eksik)}")


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
    # Uygulama kampanyaları: birçok ağda (st), uygulama üzerinden başlatılan şarjda; banka teklifiyle aynı denetim.
    # Bağlantı resmi sayfa ya da uygulama sahibinin resmi sosyal medya hesabı/gönderisi olabilir (instagram.com kabul).
    banka_idler = {b.get("id") for b in d.get("bankalar", [])}
    uygulamalar = d.get("uygulamalar", [])
    if not isinstance(uygulamalar, list):
        hata("kampanyalar.json: 'uygulamalar' liste olmalı")
        uygulamalar = []
    for u in uygulamalar:
        yer = f"uygulama {u.get('id')}"
        if u.get("id") in idler:
            hata(f"{yer}: id tekrar ediyor")
        idler.add(u.get("id"))
        for alan in ("id", "name", "offers"):
            if not u.get(alan):
                hata(f"{yer}: '{alan}' boş")
        for i, o in enumerate(u.get("offers", [])):
            ty = f"{yer} #{i + 1} ({o.get('big')})"
            teklif_denetle(ty, o, bugun, True)
            k = o.get("kart")
            if k is not None and k not in banka_idler:
                hata(f"{ty}: 'kart' ({k!r}) bankalar listesindeki bir banka id'si değil")
            if "kisa" in o and (not isinstance(o["kisa"], str) or not o["kisa"].strip()):
                hata(f"{ty}: 'kisa' boş ya da metin değil")
            if "fiyatlar" in o:
                fiyatlar_denetle(ty, o)
            for st in o.get("st", []):
                if k and st != ALL:
                    st_banka.setdefault(st, set()).add(k)
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


def ad_anahtari(s):
    """Sitedeki tarKey(): Türkçe küçük harf, aksansız, yalnızca harf/rakam (ör. "Power Şarj" = "Powerşarj")."""
    s = str(s or "").replace("I", "ı").replace("İ", "i").lower()
    s = s.translate(str.maketrans("ışğüöç", "isguoc"))
    return re.sub(r"[^a-z0-9]", "", s)


def uygulamalar(ag_adlari):
    """site/uygulamalar.json (istasyon detayındaki "Hangi uygulamayla?"): yapı denetimi + ağ adlarının eşleşmesi.
    Ağ adı tarifeler.json'da (anahtar ya da 'adlar'), kampanya verisinde ya da haritadaki istasyon markalarında yoksa uyarı:
    sitede o ağın istasyonlarında uygulama görünmez."""
    p = KOK / "site/uygulamalar.json"
    if not p.exists():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    liste = d.get("uygulamalar")
    if not isinstance(liste, list) or not liste:
        hata("uygulamalar.json: 'uygulamalar' boş ya da liste değil")
        return
    t = json.loads((KOK / "site/tarifeler.json").read_text(encoding="utf-8")).get("aglar") or {}
    bilinen = {ad_anahtari(a) for k, x in t.items() for a in [k, *(x.get("adlar") or [])]}
    bilinen |= {ad_anahtari(a) for a in ag_adlari if a}
    ip = KOK / "site/istasyonlar.json"
    markalar = set()
    if ip.exists():
        markalar = {ad_anahtari(r.get("b")) for r in json.loads(ip.read_text(encoding="utf-8")).get("istasyonlar", []) if r.get("b")}
    kamp = json.loads((KOK / "data/kampanyalar.json").read_text(encoding="utf-8"))
    kamp_uyg = {ad_anahtari(u.get("name")): u.get("id") for u in kamp.get("uygulamalar", [])}
    idler = set()
    for u in liste:
        yer = f"uygulamalar.json {u.get('id')}"
        if not u.get("id") or not u.get("ad"):
            hata(f"{yer}: 'id' ya da 'ad' boş")
        if u.get("id") in idler:
            hata(f"{yer}: id tekrar ediyor")
        idler.add(u.get("id"))
        if str(u.get("id", "")).startswith("ag:"):
            hata(f"{yer}: 'ag:' ile başlayan id ağların örtük kendi uygulamasına ayrılmış")
        tur = u.get("tur")
        if tur not in ("ag", "coklu"):
            hata(f"{yer}: 'tur' 'ag' ya da 'coklu' olmalı")
        if tur == "ag" and not u.get("ag"):
            hata(f"{yer}: ağın uygulaması ('tur': 'ag') için 'ag' (sahibi olan ağ) yazılmalı")
        if tur == "coklu" and u.get("ag"):
            hata(f"{yer}: çok ağlı uygulamada 'ag' null olmalı")
        for alan in ("app_store", "play"):
            v = u.get(alan) or ""
            if v and not v.startswith("https://"):
                hata(f"{yer}: '{alan}' https:// ile başlamalı")
        for k in u.get("kaynak") or []:
            if not str(k).startswith("https://") or any(h in k for h in DERLEME):
                hata(f"{yer}: kaynak resmi bir https bağlantısı olmalı ({k})")
        ki = kamp_uyg.get(ad_anahtari(u.get("ad")))
        if ki and ki != u.get("id"):
            hata(f"{yer}: kampanyalar.json'da bu uygulamanın id'si {ki!r}; kart/uygulama kampanyaları id ile eşleşir, aynı yazılmalı")
        aglar = u.get("aglar")
        if not isinstance(aglar, list) or not aglar:
            hata(f"{yer}: 'aglar' boş")
            continue
        if tur == "ag" and not any(ad_anahtari(x.get("ag")) == ad_anahtari(u.get("ag")) for x in aglar):
            uyari(f"{yer}: kendi ağı ({u.get('ag')}) 'aglar' listesinde yok")
        for x in aglar:
            ag = x.get("ag")
            if not ag:
                hata(f"{yer}: 'aglar' içinde 'ag' boş kayıt")
                continue
            if x.get("akim") not in (None, "ac", "dc"):
                hata(f"{yer} → {ag}: 'akim' 'ac' ya da 'dc' olmalı")
            if x.get("ad_desen") is not None:
                try:
                    re.compile(x["ad_desen"])
                except re.error as ex:
                    hata(f"{yer} → {ag}: 'ad_desen' geçersiz ({ex})")
            k = ad_anahtari(ag)
            if k not in bilinen and k not in markalar:
                uyari(f"{yer} → {ag!r}: tarifeler.json'da, kampanya verisinde ya da haritadaki markalarda eşleşmiyor; "
                      "sitede bu ağın istasyonlarında uygulama görünmeyebilir")


def konum_denetimi():
    """İstasyon konum denetiminin raporu: çıkarılan ya da taşınan kayıt sayısı birden artarsa uyarır (hata değil)."""
    rp, ip = KOK / "data/epdk/konum_duzeltmeleri.json", KOK / "site/istasyonlar.json"
    if not rp.exists() or not ip.exists():
        return
    ozet = json.loads(rp.read_text(encoding="utf-8")).get("ozet", {})
    sayi = json.loads(ip.read_text(encoding="utf-8")).get("sayi") or 0
    d = ozet.get("duzeltme", {})
    cikan = d.get("cikarildi", 0)
    degisen = sum(v for k, v in d.items() if k not in ("cikarildi", "birakildi"))
    if sayi and cikan > KONUM_CIKAN * sayi:
        uyari(f"konum denetimi {cikan} istasyon kaydını haritadan çıkardı (istasyonların %{100 * cikan / sayi:.1f}'i); "
              "data/epdk/konum_duzeltmeleri.json'a bakılmalı")
    if sayi and degisen > KONUM_DEGISEN * sayi:
        uyari(f"konum denetimi {degisen} istasyonun konumunu değiştirdi (%{100 * degisen / sayi:.1f}); "
              "data/epdk/konum_duzeltmeleri.json'a bakılmalı")


def elle_kopyalar(bugun):
    """Elle güncellenen ağ kopyaları eskidiyse uyarır (hata değil: veri haritada gösterilmeye devam eder)."""
    for ag, (ad, iste) in ELLE_KOPYA.items():
        f = KOK / "data/aglar" / f"{ag}.json"
        if not f.exists():
            continue
        c = json.loads(f.read_text(encoding="utf-8")).get("cekildi") or ""
        if not TARIH.match(c):
            uyari(f"{ad} kopyası ({f.relative_to(KOK)}): 'cekildi' tarihi yok; kullanıcıdan {iste} istenmeli")
        elif gun_farki(c, bugun) > KOPYA_GUN:
            uyari(f"{ad} kopyası {gun_farki(c, bugun)} gündür güncellenmedi (son: {c}); kullanıcıdan {iste} istenmeli")


def main():
    guncellik = "--yapi" not in sys.argv
    bugun = bugun_tr()
    try:
        aglar = kampanyalar(bugun, guncellik)
        tarifeler(bugun, guncellik, aglar)
        uygulamalar(aglar)
        konum_denetimi()
        if guncellik:
            elle_kopyalar(bugun)
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
