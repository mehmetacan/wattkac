#!/usr/bin/env python3
"""EPDK şarj istasyonu kaydı, ağların resmi haritaları, OpenStreetMap ve Open Charge Map kayıtlarını birleştirip
site/istasyonlar.json üretir.

EPDK kaynağı: data/epdk/epdk_api.json (tools/epdk_cek.py; kesin koordinat + soket tür/güç) varsa o kullanılır (q="e").
Dosya yoksa eski yönteme düşülür: CSV listesi + adresten bulunan yaklaşık konumlar (konum_onbellek.json, poi_eslesme.json).

Girdiler : data/epdk/epdk_sarj_istasyonlari.csv, data/epdk/konum_onbellek.json, data/osm/istasyonlar_osm.json
Çıktı    : site/istasyonlar.json
Konum denetimi: birleştirmeden önce her kaynaktaki her kayıt tools/konum_denetim.py ile denetlenir (Türkiye sınırı, adresteki
il/ilçe ile tutarlılık, yer değiştirmiş enlem/boylam, tek basamak hatası, başka kaynaktaki aynı istasyon). Düzeltilen ve
çıkarılan kayıtlar data/epdk/konum_duzeltmeleri.json'a yazılır.
Kayıt alanları: i=kimlik, e=EPDK no, a/o=enlem/boylam, q=konum kalitesi (e EPDK kaydındaki resmi koordinat, p adresteki tesisin OSM konumu, r resmi ağ haritası, o OSM, c Open Charge Map, a adres, m mahalle, i ilçe),
                n=ad, b=marka, p=işletmeci (isletmeciler tablosuna indeks ya da OSM'de metin), k=kW, t=soketler, ac/dc, c=adet, ad=adres, h=saat, u=web,
                rl=1 EPDK kaydı ağın kendi (eksik) haritasında da var (DOGRULA), rk=1 bu kaydın konumu ağın kendi haritasından (DOGRULA)
Kaynak önceliği: istasyon listesi ve konumu için ağın kendi sitesi/uygulaması EPDK'dan önce gelir. Ağın güncel listesi varsa (RESMI)
haritada o liste gösterilir, EPDK kayıtları yalnızca eşleşen kaydın soket/güç bilgisini tamamlar; listede olmayan EPDK kaydı
gösterilmez. Liste eksik/eskiyse (DOGRULA) EPDK kayıtları korunur, ama listede karşılığı olan kaydın konumu ağın koordinatıdır.
"""
import csv, json, math, pathlib, re, sys, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konum_denetim  # noqa: E402

EPDK = pathlib.Path("data/epdk/epdk_sarj_istasyonlari.csv")
EPDK_API = pathlib.Path("data/epdk/epdk_api.json")  # EPDK'nın açık servisi: kesin koordinat ve soketler
SOKET_AD = {"AC_TYPE2": "Type 2", "AC_TYPE1": "Type 1", "AC_SCHUKO": "Schuko", "DC_CCS": "CCS", "DC_CCS2": "CCS", "DC_CHADEMO": "CHAdeMO", "DC_GBT": "GB/T"}
CACHE = pathlib.Path("data/epdk/konum_onbellek.json")
POI = pathlib.Path("data/epdk/poi_eslesme.json")  # tesis (Shell, AVM vb.) üzerinden bulunan kesin konumlar
OSM = pathlib.Path("data/osm/istasyonlar_osm.json")
OCM = pathlib.Path("data/ocm/istasyonlar_ocm.json")
AGLAR = pathlib.Path("data/aglar")
# Resmi listesi olan ağlar: bu ağlara ait EPDK/OSM kayıtları atlanır, ağın kendi listesi kullanılır
RESMI = {"trugo": r"trugo", "zes": r"\bzes\b", "ovolt": r"ovolt|sharz", "wat": r"wat mobilite|watmobilite|\bwat\b", "astor": r"astor", "voltup": r"\bvolt ?up\b",
         "rst": r"\brst\b ?(charge|sarj|teknoloji)",  # EPDK "Rst ChargePoint" / "RST TEKNOLOJİ…", OSM "RST Şarj İstasyonu", OCM "RST Charge Point"
         "bigstation": r"windmark|\bbig ?station\b|\bbsx enerji|\bx ?sarj\b",  # EPDK marka "windmark" / "BSX ENERJİ A.Ş."; OCM "Xşarj - …" (cihazların eski adı)
         "cv": r"charging vehicles|\bcv charging\b|\bcw enerji",  # EPDK marka "CHARGING VEHICLES CV" (işletmeci CW ENERJİ…); OCM "CV Charging Vehicles"
         # EPDK marka "ACROPOL" (işletmeci GREENLEAF YENİLENEBİLİR ENERJİ…); OSM operator "acropol"; OCM "Acropol - …". Resmi listede
         # olmayan (konut sitesi, yayında olmayan) EPDK kayıtları gösterilmez: EKSIK_TUT'ta değil.
         "acropol": r"\bacropol\b|\bgreenleaf yenilenebilir",
         # 5 Şarj: 5sarj.com haritasının anlık kopyası (kullanıcının tarayıcısından; site bot korumalı, günlük iş akışı ÇEKEMEZ,
         # data/aglar/5sarj.json elle güncellenir: tools/5sarj_kopya.py; eskiyince veri_kontrol.py uyarır). EPDK marka "5 şarj",
         # işletmeci "BORENCO ŞARJ TEKNOLOJİ YATIRIMLARI…". Listedeki "e" (EPDK numaraları; bir lokasyonda birden çok ünite olabilir)
         # yalnızca soket/güç tamamlamak için kullanılır.
         "5sarj": r"\b5 sarj\b|\bborenco",
         # Ağların kendi haritaları (tools/ag_istasyonlari.py; her birinin kaynağı orada). Desenler sözcük sınırıyla: "lumi" BLADECO
         # ALÜMİNYUM'u, "aksa" Aksa Doğalgaz adlı istasyonları, "d-charge" Doğuş Dijital Enerji'nin (ayrı ağ) kayıtlarını yakalamasın.
         # electroop OCPI: Otopriz (EPDK marka "Otopriz", işletmeci DİCLE KÖK ENERJİ; OCM "Otopriz (Türkiye)"), Neva Şarj (EPDK "NEVA ŞARJ";
         # OSM "Neva Şarj"/"Neva"), EPSIS (işletmeci FORM ELEKTRİK İNŞAAT), Lumicle (EPDK "LUMİCLE", işletmeci LUMHOUSE ENERJİ; OCM
         # "Lumicle (TR)"), Ecojet (işletmeci YENİ SÜRDÜRÜLEBİLİR ENERJİ)
         "otopriz": r"\botopriz\b|\bdicle kok enerji",
         "neva": r"\bneva\b",
         "epsis": r"\bepsis\b|\bform elektrik insaat",
         "lumicle": r"\blumicle\b|\blumhouse enerji",
         "ecojet": r"\becojet\b|\byeni surdurulebilir enerji",  # EPDK "ecojet" ve "ekojet"
         }
# Bu ağların EPDK kayıtları yalnızca resmi listede RESMI_YAKIN_M içinde karşılığı varsa atlanır; karşılığı olmayanlar (listede konumu
# girilmemiş cihazlar) EPDK kaydıyla gösterilmeye devam eder.
EKSIK_TUT = {"bigstation",
             }
# EKSIK_TUT ağlarında listede karşılığı olmayan EPDK kaydı bu desene (ad + adres) uyuyorsa yine gösterilmez: ağın listesinden konut
# olduğu için ayıklanan kayıtlar EPDK üzerinden geri gelmesin (MKS: Batalgazi 5./6. Etap konut blokları, "… Evleri", "Emlak Konut Sitesi").
# MKS'nin haritası EPDK'daki yeni kayıtların bir kısmını (Arapgir Belediyesi, Baykara Petrol, Gezsan Petrol Yazıhan…) henüz içermiyor.
EKSIK_HARIC = {
    }
# Resmi listesi eksik ya da yalnızca ad + konumdan oluşan ağlar: liste istasyonların yerine geçmez, EPDK kayıtları gösterilmeye devam
# eder. Listede karşılığı olan EPDK kaydı (eşleştirme ag_istasyonlari.py'de yapılır, EPDK numarası listede "e") "rl" ile işaretlenir ve
# konumu ağın koordinatına çekilir ("rk"). Ağın koordinatı konum denetiminden (konum_denetim.py; adres olarak EPDK adresi) geçmezse ya
# da aynı koordinat ağın listesinde farklı adlı birden çok istasyona aitse (resmi haritada kopyalama hatası) güvenilmez sayılır, EPDK
# konumu korunur ve raporlanır.
# K-Şarj: ksarj.com'daki Google My Maps haritası EPDK "K-ŞARJ" (işletmeci HUNAT ENERJİ…) kayıtlarının yarısından azını içeriyor,
# soket/güç/adres yok (konum 4 basamak ≈ 11 m). OSM ve OCM'de K-Şarj kaydı yok.
# AOS Technology: aostechnology.com.tr'deki tabloda 51 istasyon, EPDK'da 124 AOSTECHNOLOGY kaydı (çoğu konut sitesi).
# otoWATT: aydemplus.com.tr'deki listede konum yok: yalnızca ad/adresle "rl" (konum EPDK'dan kalır).
DOGRULA = {"ksarj": r"\bk-sarj\b|\bhunat enerji",
           }
RESMI_YAKIN_M = 300
SECILI = pathlib.Path("data/secili_istasyonlar.json")  # yalnızca seçili istasyonlarda geçerli ağ kampanyaları
SECILI_AG = {"otopriz": r"otopriz|dicle kok"}
SAATLI = pathlib.Path("data/saatli_tarife.json")  # saate göre fiyatın (ör. gece tarifesi) yalnızca listedeki istasyonlarda geçerli olduğu ağlar
SAATLI_AG = {"shell": r"\bshell\b"}
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "site/istasyonlar.json")
TR = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
fold = lambda s: s.translate(TR).lower().replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
key = lambda s: (re.sub(r"[^a-z0-9 ]", " ", fold(s)).split() or [""])[0]


def in_turkey(lat, lon):
    """Türkiye içinde ya da kaba sınıra en fazla konum_denetim.KIYI_KM uzaklıkta (kıyı otelleri, marinalar)."""
    return konum_denetim.in_turkey(lat, lon) or konum_denetim.sinira_km(lat, lon) <= konum_denetim.KIYI_KM


def dist(a, b, c, d):
    t = math.radians
    h = math.sin(t(c - a) / 2) ** 2 + math.cos(t(a)) * math.cos(t(c)) * math.sin(t(d - b) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def soket_ekle(rec, soketler):
    """EPDK soket listesini ([[tur, kW, adet], ...]) kayda işler: ac/dc adetleri, en yüksek güç, soket adları, toplam soket."""
    for tur, kw, n in soketler:
        tip = "dc" if tur.startswith("DC") else "ac"
        rec[tip] = rec.get(tip, 0) + n
        rec["c"] = rec.get("c", 0) + n
        if kw and kw > rec.get("k", 0):
            rec["k"] = kw
        ad = SOKET_AD.get(tur) or tur.split("_", 1)[-1].title()
        if ad not in rec.setdefault("t", []):
            rec["t"].append(ad)


def epdk_kayitlari():
    """EPDK satırlarını ortak biçimde verir: (no, ad, marka, işletmeci, adres, halka_açık, konum|None, soketler)."""
    if EPDK_API.exists():
        j = json.loads(EPDK_API.read_text(encoding="utf-8"))
        for x in j.get("istasyonlar", []):
            yield x["no"], x.get("ad", ""), x.get("marka", ""), x.get("isletmeci", ""), x.get("adres", ""), True, (x["a"], x["o"]), x.get("s") or []
        return
    for r in csv.DictReader(EPDK.open(encoding="utf-8-sig")):
        yield r["no"].strip(), r["ad"].strip(), r["marka"].strip(), r["ag_isletmecisi"].strip(), r["adres"].strip(), r["hizmet"].strip() != "Özel", None, []


def main():
    api = EPDK_API.exists()
    resmi, kaynaklar, resmi_ag = [], {}, {}
    for f in sorted(AGLAR.glob("*.json")) if AGLAR.exists() else []:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("ag") in RESMI and d.get("istasyonlar"):
            kaynaklar[d["ag"]] = {"sayfa": d.get("kaynak"), "cekildi": d.get("cekildi"), "sayi": len(d["istasyonlar"])}
            for r in d["istasyonlar"]:
                r = dict(r); r["q"] = "r"; resmi.append(r); resmi_ag.setdefault(d["ag"], []).append(r)
    dogrulanan, dogrula_say, dogrula_kayit = {}, {}, {}  # dogrula_kayit: EPDK no → ağın listesindeki kayıt
    for ag in DOGRULA:
        f = AGLAR / f"{ag}.json"
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if d.get("istasyonlar"):
            dogrulanan[ag] = set()
            for r in d["istasyonlar"]:
                for e in ([r["e"]] if isinstance(r.get("e"), str) else r.get("e") or []):
                    dogrulanan[ag].add(e)
                    dogrula_kayit[e] = dict(r, ag=ag)
            dogrula_say[ag] = [len(d["istasyonlar"]), 0, 0, 0]  # resmi liste, işaretlenen EPDK kaydı, listede olmayan, konumu ağdan alınan
    covered = re.compile("|".join(RESMI[k] for k in kaynaklar)) if kaynaklar else None
    is_covered = lambda *names: bool(covered and covered.search(fold(" ".join(x for x in names if x))))

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    poi = json.loads(POI.read_text(encoding="utf-8")) if POI.exists() else {}
    osm = json.loads(OSM.read_text(encoding="utf-8"))["istasyonlar"] if OSM.exists() else []
    ocm = json.loads(OCM.read_text(encoding="utf-8"))["istasyonlar"] if OCM.exists() else []
    epdk = list(epdk_kayitlari())

    # Konum denetimi: hatalı koordinatlar birleştirmeden önce düzeltilir ya da çıkarılır (mükerrer eşleşmesi de doğru konumla yapılır)
    ilk = {}
    for x in epdk:
        if x[6] and x[0] not in ilk:
            ilk[x[0]] = {"no": x[0], "ad": x[1], "marka": x[2], "adres": x[4], "a": x[6][0], "o": x[6][1]}
    # DOGRULA ağlarının koordinatları da denetlenir; ağın listesinde adres olmadığından eşleşen EPDK kaydının adresi (il/ilçe) kullanılır.
    # Aynı koordinat ağın listesinde farklı adlı birden çok istasyona aitse (resmi haritada kopyalama hatası) güvenilmez sayılır.
    # Konumsuz listeler (otoWATT) yalnızca "rl" verir, konum değiştirmez.
    ayni_yer = {}
    yer = lambda r: (r["ag"], round(r["a"], 5), round(r["o"], 5))
    for r in dogrula_kayit.values():
        if "a" in r:
            ayni_yer.setdefault(yer(r), set()).add(fold(r.get("n") or ""))
    guvenilmez = {no for no, r in dogrula_kayit.items() if "a" in r and len(ayni_yer[yer(r)]) > 1}
    dogrula_denetim = [dict(r, i=r["i"] + "|" + no, ad=ilk[no]["adres"], b=ilk[no]["marka"] or r.get("b"))
                       for no, r in sorted(dogrula_kayit.items()) if no in ilk and no not in guvenilmez and "a" in r]
    duzelt, sil, gecersiz, rapor = konum_denetim.denetle(list(ilk.values()), resmi + dogrula_denetim, osm, ocm, poi, cache, key)
    dogrula_konum = {r["i"].split("|", 1)[1]: (r["a"], r["o"]) for r in dogrula_denetim if r["i"] not in sil}  # EPDK no → ağın koordinatı
    guvenilmez_rapor = sorted("%s: %s (%s, %s) ↔ %s %s" % (dogrula_kayit[no]["ag"], dogrula_kayit[no]["n"], dogrula_kayit[no]["a"],
                                                         dogrula_kayit[no]["o"], no, ilk[no]["ad"] if no in ilk else "") for no in guvenilmez)
    denetim_dusen = sorted("%s ↔ %s" % (r["n"], r["i"].split("|", 1)[1]) for r in dogrula_denetim if r["i"] in sil)
    konum_cekilen = []  # (mesafe m, ağ, EPDK no, ad)
    resmi = [r for r in resmi if r["i"] not in sil]
    osm = [s for s in osm if s["i"] not in sil]
    ocm = [s for s in ocm if s["i"] not in sil]
    poi = {k: v for k, v in poi.items() if k not in gecersiz}
    cache = {k: v for k, v in cache.items() if k not in gecersiz}
    konum_cikan = 0
    ops, opi = [], {}
    def op(name):
        if name not in opi:
            opi[name] = len(ops); ops.append(name)
        return opi[name]

    seen, recs, ozel, groups, birlesen, resmi_disi = set(), [], 0, {}, 0, []
    epdk_resmi = []  # resmi listesi olan ağların EPDK kayıtları: yalnızca o listedeki eksik güç/soket bilgisini tamamlamak için
    epdk_soket = {}  # EPDK no → soketler (listesi EPDK numarasıyla eşleştirilmiş ağlar için, ör. 5 Şarj "e")
    for no, ad, marka, isletmeci, adres, acik, konum, soketler in epdk:
        if no in seen:
            continue
        seen.add(no)
        if not acik:
            ozel += 1
            continue  # halka açık olmayan (özel) istasyonlar haritada gösterilmez
        kalite = "e"
        dag = next((k for k in dogrulanan if re.search(DOGRULA[k], fold(marka + " " + isletmeci))), None)
        if dag and no in dogrula_konum:
            # ağın kendi koordinatı EPDK'nınkinden önce gelir (konum denetiminden geçmiş ve güvenilir sayılmışsa)
            yeni = dogrula_konum[no]
            if konum:
                konum_cekilen.append((dist(konum[0], konum[1], yeni[0], yeni[1]), dag, no, ad))
            konum = yeni
            dogrula_say[dag][3] += 1
        elif konum and no in duzelt:
            if duzelt[no] is None:
                konum_cikan += 1
                continue  # makul konumu bulunamadı: yanlış yerde göstermektense gösterilmez
            konum, kalite = duzelt[no][:2], duzelt[no][2]
        tut = next((k for k in EKSIK_TUT if k in kaynaklar and re.search(RESMI[k], fold(marka + " " + isletmeci))), None)
        if tut and konum and not any(dist(konum[0], konum[1], r["a"], r["o"]) <= RESMI_YAKIN_M for r in resmi_ag[tut]):
            if tut in EKSIK_HARIC and re.search(EKSIK_HARIC[tut], fold(ad + " " + adres)):
                continue  # ağın listesinde konut olduğu için ayıklanan türden kayıt
            resmi_disi.append(f"{tut}: {no} {ad}")  # resmi listede karşılığı yok: EPDK kaydı gösterilir
        elif is_covered(marka, isletmeci):
            if konum:
                x = {"a": konum[0], "o": konum[1], "b": marka}
                soket_ekle(x, soketler)
                epdk_resmi.append(x)
                epdk_soket[no] = soketler
            continue  # bu ağın resmi listesi var
        rec = {"i": "e" + re.sub(r"\D", "", no), "e": no, "n": ad, "b": marka, "p": op(isletmeci), "ad": adres}
        if dag:
            dogrula_say[dag][1 if no in dogrulanan[dag] else 2] += 1
            if no in dogrulanan[dag]:
                rec["rl"] = 1  # ağın kendi haritasında da var
            if no in dogrula_konum:
                rec["rk"] = 1  # konum ağın kendi haritasından
        if konum:
            rec["a"], rec["o"], rec["q"] = konum[0], konum[1], kalite
        elif no in poi:
            rec["a"], rec["o"], rec["q"] = poi[no][0], poi[no][1], "p"
            rec["tesis"] = poi[no][2]
        elif cache.get(adres):
            rec["a"], rec["o"], rec["q"] = cache[adres]
        # Aynı markanın aynı adresteki üniteleri tek istasyonda toplanır (EPDK koordinatı varsa ayrıca 150 m içinde olmalı)
        g = (fold(marka).strip(), fold(adres).strip())
        ana = groups.get(g)
        if ana is not None and (not konum or dist(ana["a"], ana["o"], konum[0], konum[1]) < 150):
            birlesen += 1
            if rec.get("rl"):
                ana["rl"] = 1
            if rec.get("rk"):
                ana["rk"] = 1
            if soketler:
                soket_ekle(ana, soketler)
            else:
                ana["c"] = ana.get("c", 1) + 1
            continue
        if soketler:
            soket_ekle(rec, soketler)
        rec["n"] = re.sub(r"[\s\-_]+(\d{1,2}|[A-Z])$", "", rec["n"]).strip() or rec["n"]
        groups.setdefault(g, rec)
        recs.append(rec)

    # OSM ve Open Charge Map kayıtlarını EPDK kayıtlarıyla eşle: aynı marka anahtarı, en yakın kayıt.
    # Arama yarıçapı EPDK konumunun kalitesine göre: adres 300 m, mahalle 2,5 km, ilçe 8 km.
    # Eşleşince EPDK kaydı kesin konum ve soket bilgisini alır; eşleşmeyenler ayrı istasyon olarak eklenir.
    # EPDK koordinatı (e) kesin olduğundan konum ve soket bilgisi korunur; OSM/OCM'den yalnızca saat ve web adresi alınır.
    RADIUS = {"e": 150, "p": 300, "a": 300, "m": 2500, "i": 8000}
    G = 0.1
    cell = lambda a, o: (int(a // G), int(o // G))
    grid = {}
    for r in recs:
        if "a" in r and r.get("q") in RADIUS:
            grid.setdefault(cell(r["a"], r["o"]), []).append(r)
    used, extra, stats = set(), [], {}
    xgrid = {}
    for r in resmi:
        xgrid.setdefault(cell(r["a"], r["o"]), []).append((key(r.get("b") or ""), r))

    def near_extra(s, k, lim=80):
        cx, cy = cell(s["a"], s["o"])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for kk, r in xgrid.get((cx + dx, cy + dy), []):
                    if kk == k and dist(s["a"], s["o"], r["a"], r["o"]) < lim:
                        return True
        return False

    for q, src in (("o", osm), ("c", ocm)):
        st = stats.setdefault(q, [0, 0])
        for s in src:
            names = (s.get("b"), s.get("p"), s.get("w"), s.get("n"))
            if is_covered(*names):
                continue
            k = key(s.get("b") or s.get("p") or s.get("w") or s.get("n") or "")
            best, bd = None, None
            cx, cy = cell(s["a"], s["o"])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for r in grid.get((cx + dx, cy + dy), []):
                        if r["i"] in used or key(r["b"]) != k:
                            continue
                        d = dist(s["a"], s["o"], r["a"], r["o"])
                        if d <= RADIUS[r["q"]] and (bd is None or d < bd):
                            best, bd = r, d
            if best:
                used.add(best["i"]); st[0] += 1
                if best["q"] == "e":
                    best.update({x: s[x] for x in ("h", "u") if x in s and x not in best})
                else:
                    best.update({x: s[x] for x in ("k", "t", "ac", "dc", "c", "h", "u") if x in s})
                    best["a"], best["o"], best["q"] = s["a"], s["o"], q
            elif k and near_extra(s, k):
                continue  # aynı istasyon başka kaynaktan zaten eklendi
            else:
                s = dict(s); s["q"] = q; st[1] += 1
                if s.get("p"):
                    s["p"] = op(s["p"])
                extra.append(s)
                xgrid.setdefault(cell(s["a"], s["o"]), []).append((k, s))
    # Resmi ağ listelerindeki eksik güç / soket / akım türü bilgisini aynı ağın 150 m içindeki EPDK kaydından tamamla. Liste EPDK
    # numarasıyla eşleştirilmişse ("e", ör. 5 Şarj) yalnızca o kayıtlar kullanılır (konumdan bağımsız; birden çok ünite toplanır).
    egrid, tamam = {}, 0
    for x in epdk_resmi:
        egrid.setdefault(cell(x["a"], x["o"]), []).append(x)
    for r in resmi:
        if r.get("k") and r.get("t") and (r.get("ac") or r.get("dc")):
            continue
        cx, cy = cell(r["a"], r["o"]); k = key(r.get("b") or ""); best, bd = None, 150
        nolar = [e for e in ([r["e"]] if isinstance(r.get("e"), str) else r.get("e") or []) if e in epdk_soket]
        for e in nolar:
            best = best or {}
            soket_ekle(best, epdk_soket[e])
        for dx in () if nolar else (-1, 0, 1):
            for dy in (-1, 0, 1):
                for x in egrid.get((cx + dx, cy + dy), []):
                    d = dist(r["a"], r["o"], x["a"], x["o"])
                    if d < bd and key(x["b"]) == k:
                        best, bd = x, d
        if best:
            tamam += 1
            for f in ("k", "t", "c"):
                if not r.get(f) and best.get(f):
                    r[f] = best[f]
            if not r.get("ac") and not r.get("dc"):
                for f in ("ac", "dc"):
                    if best.get(f):
                        r[f] = best[f]
    # EPDK kaydı lisanslı tüm halka açık istasyonları kesin konumla içerdiğinden, OSM/OCM'den gelen ek kayıtlar yalnızca
    # yakınında karşılığı yoksa tutulur: aynı marka 500 m içinde ya da herhangi bir resmi kayıt 60 m içindeyse mükerrer sayılır.
    mukerrer = 0
    if api:
        rgrid = {}
        for r in recs + resmi:
            if "a" in r:
                rgrid.setdefault(cell(r["a"], r["o"]), []).append((key(r.get("b") or ""), r))
        kalan = []
        for s in extra:
            k = key(s.get("b") or (ops[s["p"]] if isinstance(s.get("p"), int) else "") or s.get("w") or s.get("n") or "")
            cx, cy = cell(s["a"], s["o"])
            es = any((d < 60 or (kk == k and d < 500))
                     for dx in (-1, 0, 1) for dy in (-1, 0, 1) for kk, r in rgrid.get((cx + dx, cy + dy), [])
                     for d in (dist(s["a"], s["o"], r["a"], r["o"]),))
            if es:
                mukerrer += 1
            else:
                kalan.append(s)
        extra = kalan
    for r in resmi:
        for f in ("e", "il", "ilce"):  # yalnızca eşleştirme için (EPDK numaraları, ağın il/ilçe alanı)
            r.pop(f, None)
    recs += extra + resmi
    # Seçili istasyon kampanyaları: resmi listedeki "Ad, İlçe" kayıtlarını istasyon adı/ilçe/il ile eşleştir
    secili = json.loads(SECILI.read_text(encoding="utf-8")) if SECILI.exists() else {}
    toks = lambda x: set(re.sub(r"[^a-z0-9 ]", " ", fold(x or "")).split())
    sk_hits = {}
    for ag, d in secili.items():
        rx = re.compile(SECILI_AG.get(ag, re.escape(ag)))
        GENEL = {"petrol", "akaryakit", "otel", "hotel", "restaurant", "restoran", "avm", "dinlenme", "tesisi", "tesisleri", "otopark", "the"}
        items = [(toks(i["ad"]) - GENEL or toks(i["ad"]), toks(i.get("ilce", "")) - {"merkez"}, toks(i.get("il", ""))) for i in d.get("istasyonlar", [])]
        hit = 0
        for r in recs:
            opn = ops[r["p"]] if isinstance(r.get("p"), int) else (r.get("p") or "")
            if not rx.search(fold(" ".join([r.get("b") or "", opn]))):
                continue
            nm = re.split(r"\s+-\s+", r.get("n") or "")[0]
            name_part, _, dist_part = nm.rpartition(",") if "," in nm else (nm, "", "")
            # ad "Ad, İlçe - DC" biçimindeyse ilçe adın içindekiyle eşleşmeli; değilse adresteki ilçeye bakılır
            nt, place = toks(name_part) - {"otopriz"}, (toks(dist_part) if dist_part.strip() else toks(r.get("ad")))
            for L, D, IL in items:
                if L and L <= nt and (not D or D <= place) and (not IL or IL & place or D):
                    r.setdefault("sk", []).append(ag); hit += 1
                    break
        sk_hits[ag] = hit
    # Saatli tarife (ör. Shell gece tarifesi): listedeki "Shell Ad" kayıtları istasyon adıyla ve ildeki adresle eşleşir → "tz"
    saatli = json.loads(SAATLI.read_text(encoding="utf-8")) if SAATLI.exists() else {}
    tz_hits = {}
    for ag, d in saatli.items():
        rx = re.compile(SAATLI_AG.get(ag, re.escape(ag)))
        items = [(toks(i["ad"]) - {"shell"}, toks(i.get("il", ""))) for i in d.get("istasyonlar", [])]
        hit = 0
        for r in recs:
            opn = ops[r["p"]] if isinstance(r.get("p"), int) else (r.get("p") or "")
            if not rx.search(fold(" ".join([r.get("b") or "", opn, r.get("n") or ""]))):
                continue
            nt, place = toks(r.get("n")), toks(r.get("ad"))
            if any(L and L <= nt and (not IL or IL <= place) for L, IL in items):
                r.setdefault("tz", []).append(ag); hit += 1
        tz_hits[ag] = hit
    located = [r for r in recs if "a" in r]
    # konumu bilinmeyen ve Türkiye dışı kayıtlar gösterilmez. Kayıtlar konum_denetim'den geçtiği için bu yalnızca güvenlik ağıdır;
    # kıyı ilçelerindeki noktalar (Bodrum, Gazipaşa) kaba sınırın birkaç km dışında kalabildiğinden sınıra yakınlık da kabul edilir.
    recs = [r for r in located if in_turkey(r["a"], r["o"])]
    disari = len(located) - len(recs)
    recs.sort(key=lambda r: (round(r["a"], 1), r["o"], r["i"]))
    cnt = {}
    for r in recs:
        b = r.get("b") or ""
        if b:
            cnt[b.lower()] = cnt.get(b.lower(), 0) + 1
    data = {"guncelleme": datetime.date.today().isoformat(),
            "kaynak": "EPDK Şarj İstasyonları kaydı, ağların resmi haritaları, © OpenStreetMap katkıda bulunanlar (ODbL), © Open Charge Map (CC BY 4.0)",
            "sayi": len(recs), "resmi_kaynaklar": kaynaklar, "secili_aglar": sorted(secili.keys()),
            "isletmeciler": ops, "istasyonlar": recs}
    txt = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(txt, encoding="utf-8")
    print(konum_denetim.ozet_satiri(rapor) + f" (EPDK'dan çıkarılan {konum_cikan}; ayrıntı: {konum_denetim.RAPOR})")
    if resmi_disi:
        print(f"resmi listede karşılığı olmayan, EPDK kaydıyla gösterilen ({len(resmi_disi)}): " + "; ".join(resmi_disi))
    for ag, (n, var, yok, cek) in dogrula_say.items():
        print(f"{ag}: resmi liste {n} istasyon (eksik liste: EPDK kayıtları korunur); EPDK kaydı listede var {var}, listede yok {yok} "
              f"(ikisi de gösterilir); konumu ağın koordinatına çekilen {cek}")
    if konum_cekilen:
        konum_cekilen.sort(reverse=True)
        print(f"ağ koordinatına çekilen EPDK kaydı {len(konum_cekilen)}, 100 m'den fazla değişen {sum(1 for d, *_ in konum_cekilen if d > 100)}; en büyük: "
              + "; ".join(f"{ag} {no} {ad} {d:.0f} m" for d, ag, no, ad in konum_cekilen[:5]))
    if guvenilmez_rapor:
        print(f"güvenilmez ağ koordinatı (aynı koordinat farklı adlı birden çok istasyonda; EPDK konumu korundu) ({len(guvenilmez_rapor)}): " + "; ".join(guvenilmez_rapor))
    if denetim_dusen:
        print(f"konum denetiminden geçmeyen ağ koordinatı (EPDK konumu korundu) ({len(denetim_dusen)}): " + "; ".join(denetim_dusen))
    print("seçili kampanya eşleşmeleri:", sk_hits)
    print("saatli tarife eşleşmeleri:", tz_hits)
    ozet = ", ".join("%s %d" % (k, v["sayi"]) for k, v in kaynaklar.items())
    print(f"resmi ağ listeleri {len(resmi)} ({ozet}); EPDK {len(seen)} kayıt (özel {ozel} çıkarıldı), EPDK'dan gelen {sum(1 for r in recs if r.get('e'))}, eşleşen/eklenen OSM {stats.get('o')}, OCM {stats.get('c')}, Türkiye dışı {disari}, aynı adreste birleştirilen EPDK ünitesi {birlesen}, EPDK ile tamamlanan resmi ağ kaydı {tamam}, mükerrer sayılıp atılan OSM/OCM {mukerrer}, EPDK kaynağı {'açık servis (kesin koordinat)' if api else 'CSV + adres araması'}, toplam {len(recs)}, {len(txt)//1024} KB")


if __name__ == "__main__":
    main()
