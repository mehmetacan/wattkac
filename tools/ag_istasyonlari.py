#!/usr/bin/env python3
"""Şarj ağlarının KENDİ resmi web sitelerindeki haritaların herkese açık (giriş/anahtar gerektirmeyen)
veri kaynaklarından istasyon listelerini çeker ve data/aglar/<ag>.json olarak kaydeder.

Kaynaklar (her biri ağın kendi sitesindeki haritanın kullandığı adres):
  ZES          https://zes.net/Station/MarkerSet                       (zes.net/tr/sarj-istasyonlari)
  Ovolt/Sharz  https://mobil-api.ovolt.com.tr/api/App/stations/cards   (ovolt.com.tr/istasyon-haritasi)
  WAT Mobilite https://www.watmobilite.com/istasyon-haritasi           (sayfa içindeki istasyon kartları)
  Trugo        https://trugo.com.tr/individual/network                  (sayfanın kendi içindeki __NUXT_DATA__ istasyon listesi)
  VoltUp       https://voltup.com.tr/#istasyonlar                       (istasyon fiyat listesi + ana sayfadaki harita işaretçileri)
               Fiyat listesi (https://voltup.petroo.dev/price-list/true/true) bir Blazor Server sayfasıdır, düz HTTP ile
               okunamaz; tools/voltup_fiyat.mjs onu tarayıcıyla bir kez açıp data/aglar/voltup_fiyat.json'a yazar. Burada
               o dosya okunur, istasyonların konumu ve soketleri EPDK kaydından (data/epdk/epdk_api.json) ad eşleşmesiyle,
               EPDK'da bulunamayanlar ana sayfadaki işaretçilerden alınır.
  RST Charge Point https://rstchargepoint.com/#fiyatlar               (ana sayfadaki haritanın kendi içindeki istasyon dizisi)
               Soketler EPDK kaydından (konuma, ad ve ilçeye göre birebir eşleşme); listedeki "durum" alanı ağın elle
               güncellediği bir alandır (arizali → pasif, bakimda → bakim), canlı durum değildir.
  BIG Station  https://bsx-reverse.ee-w.workers.dev/api/stations       (eski adı Windmark, işletmeci BSX Enerji)
               Big Station'ın kendi sistemini okuyan, giriş gerektirmeyen üçüncü taraf salt okunur servis. Yalnızca
               GET /api/stations; yalnızca halka açık cihazlar ve kişisel olmayan alanlar tutulur.
  CV Charging  https://cv-charging.com/views/api/get_istasyon_api.php   (cv-charging.com/tr/cv-arac-sarj-istasyonlari)
               Soketler aynı sayfanın istasyon başına çağırdığı get_istasyon_soket_api.php'den (aralarında 0,3 sn).
  (ASTOR Şarj'ın haritası map-api.echargo.com kullanıyor ama sunucudan yapılan istekleri reddediyor (HTTP 404);
   erişim kısıtını aşmaya çalışmıyoruz, ASTOR istasyonları EPDK + OSM'den gelir.)

Kurallar: günde bir kez, her kaynağa tek istek (BIG Station: 100'erlik sayfalar, aralarında 1 sn); anahtar/oturum gerektiren kaynaklar KULLANILMAZ.
Bir ağın çekimi başarısız olursa o ağın önceki dosyası korunur.
Yalnızca bazı ağları çekmek için adlarını verin: python3 tools/ag_istasyonlari.py voltup
Kayıt alanları istasyon_cek.py ile aynıdır (i, a, o, n, b, k, t, ac, dc, c, ad) + pr (soket fiyatları, varsa).
"""
import html, json, math, pathlib, re, sys, urllib.request, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from html.parser import HTMLParser

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
    trugo_prices(out)
    return out


# Trugo fiyatları (resmi): AC 9,95 TL/kWh; DC 14,98 TL/kWh; duyurudaki seçili istasyonlarda DC 12 TL/kWh.
# Kaynaklar: https://trugo.com.tr/price ve https://trugo.com.tr/individual/news/secili-istasyonlarda-12-tl-kwh
TRUGO_AC, TRUGO_DC, TRUGO_12 = 9.95, 14.98, 12.0
TRUGO_12_URL = "https://trugo.com.tr/individual/news/secili-istasyonlarda-12-tl-kwh"


def _tok(s):
    s = s.translate(str.maketrans({"İ": "i", "I": "ı"})).lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c")):
        s = s.replace(a, b)
    return set(re.sub(r"[^a-z0-9 ]", " ", s).replace("bimola", "bi mola").split())


def trugo_prices(recs):
    try:
        page = html.unescape(re.sub(r"<[^>]+>", " ", get(TRUGO_12_URL)))
        m = re.search(r"katılan şarj istasyonları\s*:\s*(.+?)\.\s", page, re.S)
        names = [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []
    except Exception as e:  # noqa: BLE001
        print("trugo 12 TL duyurusu okunamadı:", e, file=sys.stderr)
        return  # fiyat aralığına (tarifeler.json) düşülür
    keys = [_tok(n) - {"akaryakit", "aydin", "soke", "istasyonu"} for n in names]
    hit = 0
    for r in recs:
        tk = _tok(r.get("n", ""))
        special = any(k and k <= tk for k in keys)
        pr = {}
        if r.get("ac"):
            pr["ac"] = TRUGO_AC
        if r.get("dc"):
            pr["dc"] = TRUGO_12 if special else TRUGO_DC
        if special:
            r["prn"] = "Seçili istasyon: DC 12 TL/kWh"
            hit += 1
        if pr:
            r["pr"] = pr
    print(f"trugo: 12 TL duyurusunda {len(names)} istasyon adı, eşleşen {hit} istasyon")


# VoltUp: istasyon bazlı fiyat listesi (tools/voltup_fiyat.mjs) + konum/soket için EPDK kaydı ve sitedeki harita işaretçileri
VOLTUP_FIYAT = OUT / "voltup_fiyat.json"
EPDK_API = pathlib.Path("data/epdk/epdk_api.json")
VOLTUP_ESKI_GUN = 14  # fiyat dosyası bundan eskiyse istasyon fiyatı yazılmaz (sitede tarifeler.json'daki aralık görünür)
SOKET_AD = {"AC_TYPE2": "Type 2", "AC_TYPE1": "Type 1", "AC_SCHUKO": "Schuko", "DC_CCS": "CCS", "DC_CCS2": "CCS", "DC_CHADEMO": "CHAdeMO", "DC_GBT": "GB/T"}
# Ad karşılaştırmasında atılan sözcükler ve tek başına eşleşme için yetmeyen genel sözcükler (ilk 5 harfleriyle)
_AT = {"voltu", "volt", "up", "petro", "sarj", "istas", "ve"}
_GENEL = {"otopa", "opet", "plaza", "hotel", "otel", "petro", "ofisi", "shell", "resto", "resta", "katli", "alani", "yani", "onu",
          "karsi", "mahal", "park", "long", "mola", "antot", "hesap"}


def _kokler(s):
    """Ad → sözcük kökleri kümesi (Türkçe harfler sadeleştirilir, ilk 5 harf; "Petroo/VoltUp/Şarj İstasyonu" atılır)."""
    s = re.sub(r"\bpetroo\b", " ", " ".join(_tok(s)))
    return {w[:5] for w in s.split() if w[:5] not in _AT and not (len(w) == 1 and not w.isdigit())}


def _ilce(adres):
    """Fiyat listesindeki "… - İLÇE / İL" ya da EPDK'daki "… İlçe / İL" adresinden ilçe."""
    m = re.search(r"(?:^|[\s-])([^\s/-]+)\s*/\s*[^/]+$", adres or "")
    return " ".join(_tok(m.group(1))) if m else ""


def _eslestir(adaylar, hedefler, ad, ilce):
    """Ad benzerliğiyle birebir eşleştirme (en iyi eşleşme önce). Dönüş: {aday indeksi: hedef indeksi}.
    Puan = ortak kök / kısa adın kök sayısı; ortak köklerden en az biri genel sözcük olmamalı. İlçeler biliniyor ve
    farklıysa (fiyat listesinde ilçe bazen "Merkez" ya da komşu ilçe yazıyor) yalnızca tam eşleşme kabul edilir."""
    puanlar = []
    for i, a in enumerate(adaylar):
        ka = _kokler(ad(a))
        for j, h in enumerate(hedefler):
            kh = _kokler(ad(h))
            ortak = ka & kh
            if not ortak or not (ortak - _GENEL) or not ka or not kh:
                continue
            p = len(ortak) / min(len(ka), len(kh)) - 0.01 * abs(len(ka) - len(kh))
            ia, ih = ilce(a), ilce(h)
            if ia and ih and ia != ih:
                if len(ortak) < min(len(ka), len(kh)):
                    continue
            else:
                p += 0.05
            if p >= 0.6:
                puanlar.append((p, i, j))
    sonuc, kullanilan = {}, set()
    for p, i, j in sorted(puanlar, key=lambda x: -x[0]):
        if i not in sonuc and j not in kullanilan:
            sonuc[i] = j; kullanilan.add(j)
    return sonuc


class _Isaretci(HTMLParser):
    """voltup.com.tr ana sayfasındaki <div class="map-marker" data-lat data-lng data-mapinfo="Ad , Adres<br />">"""
    def __init__(self):
        super().__init__(); self.liste = []

    def handle_starttag(self, tag, attrs):
        at = dict(attrs)
        if "map-marker" in (at.get("class") or "").split():
            try:
                a, o = float(at.get("data-lat")), float(at.get("data-lng"))
            except (TypeError, ValueError):
                return
            bilgi = html.unescape(re.sub(r"<[^>]+>", " ", at.get("data-mapinfo") or ""))
            ad, _, adres = bilgi.partition(" , ")
            self.liste.append({"a": a, "o": o, "n": ad.strip(), "ad": re.sub(r"\s+", " ", adres).strip()})


def voltup():
    if not VOLTUP_FIYAT.exists():
        raise RuntimeError(f"{VOLTUP_FIYAT} yok (önce node tools/voltup_fiyat.mjs)")
    fj = json.loads(VOLTUP_FIYAT.read_text(encoding="utf-8"))
    liste = fj.get("istasyonlar") or []
    yas = (datetime.date.today() - datetime.date.fromisoformat(fj.get("cekildi") or "2000-01-01")).days
    fiyat_yaz = yas <= VOLTUP_ESKI_GUN
    if yas > 1:
        print(f"voltup: fiyat listesi {yas} gün önce okunmuş" + ("" if fiyat_yaz else "; istasyon fiyatı yazılmıyor"), file=sys.stderr)
    # EPDK kayıtları: kesin koordinat ve soketler (aynı istasyonun birden çok ünitesi tek kayıtta toplanır)
    epdk = []
    if EPDK_API.exists():
        for x in json.loads(EPDK_API.read_text(encoding="utf-8")).get("istasyonlar", []):
            if re.search(r"\bvolt ?up\b", " ".join(_tok(" ".join([x.get("marka", ""), x.get("isletmeci", "")])))) and ok_coord(x.get("a"), x.get("o")):
                epdk.append(x)
    # Sitedeki harita işaretçileri: EPDK'da karşılığı bulunamayan (yeni) istasyonların konumu için
    try:
        p = _Isaretci(); p.feed(get("https://voltup.com.tr/")); isaret = [m for m in p.liste if ok_coord(m["a"], m["o"])]
    except Exception as e:  # noqa: BLE001
        print("voltup: ana sayfadaki harita okunamadı:", e, file=sys.stderr); isaret = []
    ad = lambda x: x.get("n") or x.get("ad") or ""
    e_es = _eslestir(liste, epdk, lambda x: x.get("n") if "n" in x else x.get("ad"), lambda x: _ilce(x.get("adres") if "adres" in x else x.get("ad")))
    kalan = [i for i in range(len(liste)) if i not in e_es]
    m_es = _eslestir([liste[i] for i in kalan], isaret, ad, lambda x: _ilce(x.get("ad")) if " / " in (x.get("ad") or "") else "")
    out, bulunamayan = [], []
    for i, s in enumerate(liste):
        r = {"b": "VoltUp", "n": s["n"], "ad": s.get("ad", "")}
        if i in e_es:
            x = epdk[e_es[i]]
            r.update({"i": "voltup" + re.sub(r"\D", "", x["no"]), "a": round(x["a"], 6), "o": round(x["o"], 6)})
            for tur, kw, n in x.get("s") or []:
                tip = "dc" if tur.startswith("DC") else "ac"
                r[tip] = r.get(tip, 0) + n; r["c"] = r.get("c", 0) + n
                if kw and kw > r.get("k", 0):
                    r["k"] = kw
                t = SOKET_AD.get(tur) or tur.split("_", 1)[-1].title()
                if t not in r.setdefault("t", []):
                    r["t"].append(t)
        elif kalan.index(i) in m_es:
            m = isaret[m_es[kalan.index(i)]]
            r.update({"i": "voltup-" + "-".join(sorted(_kokler(s["n"]))), "a": round(m["a"], 6), "o": round(m["o"], 6)})
        else:
            bulunamayan.append(s["n"]); continue
        if not r.get("ac") and not r.get("dc"):  # soket bilgisi yoksa fiyatı yazılan akım türleri
            r.update({"ac": int(s.get("ac") is not None), "dc": int(s.get("dc") is not None)})
            r["t"] = (["Type 2"] if r["ac"] else []) + (["CCS"] if r["dc"] else [])
        pr = {k: s[k] for k in ("ac", "dc") if isinstance(s.get(k), (int, float))}
        if pr and fiyat_yaz:
            r["pr"] = pr
        out.append(clean(r))
    eslesen_e = {epdk[j]["no"] for j in e_es.values()}
    print(f"voltup: fiyat listesinde {len(liste)} istasyon; konumu EPDK'dan {len(e_es)}, sitedeki haritadan {len(m_es)}, bulunamayan {len(bulunamayan)}"
          + (f" ({'; '.join(bulunamayan)})" if bulunamayan else ""))
    disarda = [x["ad"] for x in epdk if x["no"] not in eslesen_e]
    if disarda:
        print(f"voltup: fiyat listesinde (aktif lokasyonlarda) olmayan EPDK kayıtları gösterilmiyor: {'; '.join(disarda)}")
    return out


# RST Charge Point: rstchargepoint.com ana sayfasındaki Leaflet haritasının "hamVeriler" dizisi
# ({ isim, lat, lng, il, durum?, kw? }; koordinatlar ondalık ya da '38°02\'44.8"N' biçiminde). Fiyat tek tarife (tarifeler.json).
RST_URL = "https://rstchargepoint.com/"
RST_UZAK_KM = 1.0  # listedeki konum eşleşen EPDK kaydından bundan uzaksa EPDK konumu kullanılır (listede kopyalanmış/yanlış koordinatlar görüldü)
_RST_GENEL = {"petro", "akary", "lukoi", "opet", "shell", "bp", "total", "po", "class", "teco", "aytem", "sunpe", "kadoi", "turko",
              "resto", "rest", "otel", "hotel", "park", "otopa", "dinle", "tesis", "mahal", "merke", "sanay", "kucuk", "mm", "ss", "ens",
              "ofisi", "fox", "rst", "tek"}
_RST_BUYUK = {"BP", "PO", "TECO", "MM", "SS"}


def _rst_koord(v):
    """Sayfadaki parseCoord() ile aynı: ondalık sayı ya da 38°02'44.8"N biçimi."""
    v = str(v).strip()
    if "°" not in v and "'" not in v:
        return float(v)
    m = re.search(r"(\d+)°(\d+)'([\d.]+)\"([NSEW])", v)
    if not m:
        return 0.0
    x = float(m[1]) + float(m[2]) / 60 + float(m[3]) / 3600
    return -x if m[4] in "SW" else x


def _rst_dizi(page):
    """var hamVeriler = [ {...}, ... ]; → [{isim, lat, lng, il, durum, kw}] (yorum satırları atlanır)."""
    m = re.search(r"var\s+hamVeriler\s*=\s*\[(.*?)\];", page, re.S)
    if not m:
        raise RuntimeError("hamVeriler dizisi bulunamadı")
    govde = re.sub(r"^\s*//.*$", "", m.group(1), flags=re.M)
    out = []
    for obj in re.findall(r"\{([^{}]*)\}", govde):
        d = {}
        for k, v in re.findall(r"(\w+)\s*:\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|-?[\d.]+)", obj):
            d[k] = re.sub(r"\\(.)", r"\1", v[1:-1]) if v[0] in "\"'" else v
        if d.get("isim") and d.get("lat") and d.get("lng"):
            out.append(d)
    return out


def _km(a, b, c, d):
    t = math.radians
    h = math.sin(t(c - a) / 2) ** 2 + math.cos(t(a)) * math.cos(t(c)) * math.sin(t(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _tr_baslik(w):
    """Türkçe baş harf: "ŞEHİTLİK" → "Şehitlik", "TÜRKOİL-ŞAHMERAN" → "Türkoil-Şahmeran"."""
    if w in _RST_BUYUK:
        return w
    def bir(x):
        x = x.replace("I", "ı").replace("İ", "i").lower()
        return (x[:1].replace("i", "İ").replace("ı", "I").upper() + x[1:]) if x else x
    return "-".join(bir(x) for x in w.split("-"))


def _rst_ad(isim, il, ilce):
    """"ESKİŞEHİR NASRETTİN HOCA" + Sivrihisar → "Nasrettin Hoca, Sivrihisar"; ilçe Merkez ise il adı eklenir."""
    w = [x.strip("-") or x for x in isim.split()]
    f = lambda x: " ".join(_tok(x))
    if len(w) > 1 and (f(w[0]) == f(il) or f(il).startswith(f(w[0]))):
        w = w[1:]
    w = [x for x in w if f(x) != "merkez" and x != "-"] or w
    w = [ilce if ilce and f(x) == f(ilce) else _tr_baslik(x) for x in w]
    ad = " ".join(w)
    yer = ilce if ilce and f(ilce) != "merkez" else _tr_baslik(il)
    return ad if not yer or f(yer) in f(ad).split() else f"{ad}, {yer}"


def rst():
    liste = _rst_dizi(get(RST_URL))
    epdk = []
    if EPDK_API.exists():
        for x in json.loads(EPDK_API.read_text(encoding="utf-8")).get("istasyonlar", []):
            if re.search(r"\brst\b", " ".join(_tok(" ".join([x.get("marka", ""), x.get("isletmeci", "")])))) and ok_coord(x.get("a"), x.get("o")):
                epdk.append(x)
    il_ilce = lambda adres: (lambda m: (m[2].strip(), m[1]) if m else ("", ""))(re.search(r"(\S+)\s*/\s*([^/]+)$", adres or ""))
    kok = lambda s: {w[:5] for w in _tok(s) if len(w) > 1} - _RST_GENEL
    for s in liste:
        s["a"], s["o"] = _rst_koord(s["lat"]), _rst_koord(s["lng"])
    liste = [s for s in liste if ok_coord(s["a"], s["o"])]
    # Birebir eşleştirme: ad/ilçe kökü ortaklığı (aynı il içinde) her ortak kök için 10 puan, 1 km içindeki yakınlık en çok 5 puan.
    # Listede adlar EPDK'dakinden farklı olabildiği için ("UŞAK 7 KITA PETROL BANAZ" = EPDK "GÜLCE PETROL", Banaz) yakınlık tek başına yeter.
    puan = []
    for i, s in enumerate(liste):
        ks, il_s = kok(s["isim"]), " ".join(_tok(s.get("il", "")))
        for j, x in enumerate(epdk):
            il_x, ilce_x = il_ilce(x.get("adres"))
            il_x = " ".join(_tok(il_x))
            ayni_il = bool(il_s and il_x and (il_x.startswith(il_s) or il_s.startswith(il_x)))
            ortak = len(ks & kok(x.get("ad", "") + " " + ilce_x)) if ayni_il else 0
            d = _km(s["a"], s["o"], x["a"], x["o"])
            p = 10 * ortak + (5 * (1 - d / RST_UZAK_KM) if d < RST_UZAK_KM else 0)
            if p > 0:
                puan.append((p, i, j, d))
    es, kullanilan = {}, set()
    for p, i, j, d in sorted(puan, key=lambda x: -x[0]):
        if i not in es and j not in kullanilan:
            es[i] = (j, d); kullanilan.add(j)
    out, uzak, durumlu = [], [], []
    for i, s in enumerate(liste):
        r = {"b": "RST Charge Point"}
        il, ilce = s.get("il", ""), ""
        if i in es:
            x, d = epdk[es[i][0]], es[i][1]
            il_x, ilce = il_ilce(x.get("adres"))
            r["i"] = "rst" + re.sub(r"\D", "", x["no"])
            r["ad"] = re.sub(r"\s+", " ", x.get("adres", "")).strip()
            a, o = (x["a"], x["o"]) if d > RST_UZAK_KM else (s["a"], s["o"])
            if d > RST_UZAK_KM:
                uzak.append(f"{s['isim']} ({d:.1f} km; EPDK {x['no']} {x.get('ad', '')} konumu kullanıldı)")
            for tur, kw, n in x.get("s") or []:
                tip = "dc" if tur.startswith("DC") else "ac"
                r[tip] = r.get(tip, 0) + n; r["c"] = r.get("c", 0) + n
                if kw and kw > r.get("k", 0):
                    r["k"] = kw
                t = SOKET_AD.get(tur) or tur.split("_", 1)[-1].title()
                if t not in r.setdefault("t", []):
                    r["t"].append(t)
        else:
            a, o = s["a"], s["o"]
            r["i"] = "rst-" + "-".join(sorted(_tok(s["isim"])))
            r["ad"] = il
        if not r.get("ac") and not r.get("dc"):  # EPDK'da yoksa listedeki güç (yazılmamışsa sayfanın varsayılanı 120 kW)
            kw = float((re.search(r"[\d.]+", s.get("kw") or "120") or ["120"])[0])
            r["k"] = round(kw)
            r["dc" if kw >= 50 else "ac"] = 1
            r["t"] = ["CCS"] if kw >= 50 else ["Type 2"]
        r.update({"a": round(a, 6), "o": round(o, 6), "n": _rst_ad(s["isim"], il, ilce)})
        durum = (s.get("durum") or "").lower()
        if durum == "arizali":
            r["pasif"] = 1; durumlu.append(f"{r['n']}: arızalı")
        elif durum == "bakimda":
            r["bakim"] = 1; durumlu.append(f"{r['n']}: bakımda")
        out.append(clean(r))
    print(f"rst: listede {len(liste)} istasyon; EPDK ile eşleşen {len(es)}, eşleşmeyen {len(liste) - len(es)}"
          + (f" ({'; '.join(liste[i]['isim'] for i in range(len(liste)) if i not in es)})" if len(es) < len(liste) else ""))
    if uzak:
        print(f"rst: listedeki konumu EPDK kaydından {RST_UZAK_KM:g} km'den uzak olanlar: {'; '.join(uzak)}")
    print("rst: listede arızalı/bakımda işaretli: " + ("; ".join(durumlu) if durumlu else "yok"))
    disarda = [f"{x['no']} {x.get('ad', '')}" for j, x in enumerate(epdk) if j not in kullanilan]
    if disarda:
        print(f"rst: resmi listede olmayan EPDK kayıtları gösterilmiyor ({len(disarda)}): {'; '.join(disarda)}")
    return out


# BIG Station (eski adı Windmark; işletmeci BSX Enerji A.Ş.): Big Station'ın kendi sistemini okuyan, giriş gerektirmeyen üçüncü taraf
# salt okunur servis. YALNIZCA GET /api/stations kullanılır (giriş, şarj, izleme vb. hiçbir başka adres çağrılmaz). Yanıttaki kayıtlar
# okunur okunmaz BIG_ALAN alanlarına indirgenir: cihaz kimliği, anlık oturum/ölçüm ve kullanıcı (ad, plaka) bilgileri diske de loga da
# yazılmaz. Yalnızca halka açık (usageType "public") cihazlar; konut sitesi / şirket içi / test cihazları adlarından ayıklanır.
# Aynı yerdeki cihazlar (aynı temel ad ya da ortak ayırt edici sözcük, BIG_GRUP_M içinde) tek istasyonda toplanır.
BIG_URL = "https://bsx-reverse.ee-w.workers.dev/api/stations?offset={}&limit=100"
BIG_SAYFA = "https://bsx-reverse.ee-w.workers.dev/app"
BIG_ALAN = ("id", "name", "code", "city", "latitude", "longitude", "deviceType", "isDc", "usageType", "powerKw", "pricePerKwh")
BIG_EN_AZ = 100      # bundan az halka açık cihaz gelirse yanıt eksik sayılır, önceki dosya korunur
BIG_GRUP_M = 60      # ortak ayırt edici sözcüklü cihazlar bu uzaklıkta tek istasyon
BIG_AYNI_AD_M = 150  # aynı adlı cihazlar bu uzaklıkta tek istasyon
BIG_AYNI_YER_M = 25  # adı ne olursa olsun bu kadar yakın cihazlar aynı yerdedir (ör. "SDÜ Batı" adlı DC ünitesi Doğu otoparkında)
BIG_EPDK_M = 300     # EPDK windmark kaydının karşılığı sayılma uzaklığı (istasyon_birlestir.py ile aynı)
# Halka açık işaretli olsa da haritada gösterilmeyenler (ad ya da şehir alanında): konut sitesi/rezidans/villa, şirket ofisi, test,
# kurulmamış ya da stoktaki cihaz. "Kurt Safir": aynı adlı konut sitesi ("Kurt Safir Avsallar Sitesi").
BIG_HARIC = [(r"\bsitesi\b|\bkonaklar|\bkonutlar|\bevleri\b|\brezidan|\bresiden|\bmy world\b|\bvilla\b|\bapartman|\bkurt safir\b", "konut/site"),
             (r"\bpersonel\b|\bofis\b", "şirket içi/ofis"),
             (r"\btest|\btesttt\b", "test cihazı"),
             (r"\bkurulu degil\b|\bstokta\b", "kurulu değil/stokta")]
_BIG_AD = {"sdu": "SDÜ", "maku": "MAKÜ", "aosb": "AOSB", "incekum": "İncekum", "bati": "Batı", "dogu": "Doğu", "the": "The"}
_BIG_GENEL = {"hotel", "otel", "resort", "beach", "palace", "club", "hotels", "otopark", "the", "isparta", "denizli", "antalya", "burdur", "sdu"}


def _big_cek():
    """Sayfa sayfa (100'er, aralarında 1 sn) çeker; her kaydı hemen BIG_ALAN alanlarına indirger; kimliğe göre tekilleştirir
    (servisin sayfalaması sabit sıralı değil, aynı cihaz iki sayfada gelebiliyor: uygulamanın kendisi de böyle tekilleştiriyor)."""
    import time
    tum, gorulen, tekrar = [], set(), 0
    for sayfa in range(20):
        if sayfa:
            time.sleep(1)
        liste = json.loads(get(BIG_URL.format(sayfa * 100))).get("stations")
        if not isinstance(liste, list):
            raise RuntimeError("yanıtta 'stations' listesi yok")
        for s in liste:
            s = {k: s.get(k) for k in BIG_ALAN} if isinstance(s, dict) else {}
            if s.get("id") is None:
                continue
            if str(s["id"]) in gorulen:
                tekrar += 1; continue
            gorulen.add(str(s["id"])); tum.append(s)
        if len(liste) < 100:
            break
    return tum, tekrar


def _big_ad(ad):
    """Cihaz adı → okunur istasyon adı: "XŞARJ-000027A (Alexius Beach Hotel)" → "Alexius Beach Hotel", "ISPARTA SDU BATI 2 TABANCALI - 1"
    → "Isparta SDÜ Batı", "Makü - 10 (Burdur)" → "MAKÜ", "Dc Denizli Eren Soket-1" → "Denizli Eren"."""
    s = re.sub(r"\s+", " ", str(ad or "")).strip()
    s = re.sub(r"(?i)\s*tak\s+[cç]al[ıi][sş]t[ıi]r\s+[cç]evr[ıi]l?d[ıi]\s*$", "", s)  # iç not: "tak çalıştır çevrildi"
    s = re.sub(r"(?i)^asel\s*-\s*", "", s)  # kurulumu yapan firmanın öneki
    m = re.match(r"(?i)^(?:x\s?[sş]arj|bsx)[-\s]*[0-9a-f]*\s*\((.+?)\s*\)", s)
    if m:
        s = m.group(1)
    s = re.sub(r"\s*\(\s*(?:\d+|\d+\.\s*tabanca|" + "|".join(re.escape(x) for x in IL_KISA) + r")\s*\)", "", s, flags=re.I)
    s = re.sub(r"(?i)^dc\s+", "", s)
    s = re.sub(r"(?i)\s*\b\d\s*tabancal[ıi]\b", "", s)
    s = re.sub(r"(?i)[\s\-#]*(?:soket|ac|dc)?[\s\-#]*\d{1,2}$", "", s).strip(" -#")
    s = re.sub(r"(?i)\s+soket$", "", s)
    def kelime(w):
        f = " ".join(_tok(w))
        if f in _BIG_AD:
            return _BIG_AD[f]
        # tümü büyük harf yazılmış adlar: ilk harf korunur, gerisi küçültülür ("MERIDIA" → "Meridia"; I → ı yapılmaz, adlar çoğunlukla yabancı)
        return "-".join(x[:1] + x[1:].replace("İ", "i").replace("I", "i").lower() for x in w.split("-")) if w.isupper() and len(w) > 1 else w
    return " ".join(kelime(w) for w in s.split()) or str(ad)


IL_KISA = ("Adana Antalya Burdur Denizli Isparta Muğla İstanbul Ankara Konya Hatay Çanakkale Afyonkarahisar Gaziantep Van Tekirdağ "
           "İzmir Kocaeli").split()


def _big_duz(s):
    """Sıralı, sade metin (Türkçe harfler sadeleşir): "Kurt Safir Avsallar Sitesi" → "kurt safir avsallar sitesi"."""
    import konum_denetim as kd
    return " ".join(re.sub(r"[^a-z0-9]+", " ", kd.fold(s)).split())


def _big_kok(ad):
    return {w for w in _big_duz(ad).split() if len(w) >= 3 and not w.isdigit()}


def bigstation():
    import konum_denetim as kd
    cihaz, tekrar = _big_cek()
    acik = [s for s in cihaz if s.get("usageType") == "public"]
    print(f"bigstation: {len(cihaz)} cihaz (sayfalar arası tekrar {tekrar}), halka açık {len(acik)}, özel {len(cihaz) - len(acik)}")
    if len(acik) < BIG_EN_AZ:
        raise RuntimeError(f"yalnızca {len(acik)} halka açık cihaz (beklenen ≥{BIG_EN_AZ})")
    # EPDK: il/ilçe yazımı ve konum tutarlılığı için başvuru noktaları; windmark kayıtları karşılaştırma için
    epdk, windmark, ilce_ad = [], [], {}
    if EPDK_API.exists():
        for x in json.loads(EPDK_API.read_text(encoding="utf-8")).get("istasyonlar", []):
            if not ok_coord(x.get("a"), x.get("o")):
                continue
            il, ilce = kd.il_ilce_epdk(x.get("adres"))
            if il:
                epdk.append((x["a"], x["o"], il, ilce))
                if ilce:
                    w = kd.ADA.sub("", x["adres"]).rsplit("/", 1)[0].split()
                    ilce_ad.setdefault((il, ilce), w[-1] if w[-1][:1].isupper() else _tr_baslik(w[-1]))
            if re.search(r"windmark|\bbsx\b", " ".join(_tok(x.get("marka", "") + " " + x.get("isletmeci", "")))):
                windmark.append(x)
    hucre = {}
    for p in epdk:
        hucre.setdefault((int(p[0] * 5), int(p[1] * 5)), []).append(p)

    def cevre(a, o, km_, n=7):
        """Konumun çevresindeki en yakın n EPDK noktası (km_ içinde) → [(uzaklık, il, ilçe)]."""
        cx, cy = int(a * 5), int(o * 5); r = int(km_ / 20) + 1
        ys = [(_km(a, o, p[0], p[1]), p[2], p[3]) for dx in range(-r, r + 1) for dy in range(-r, r + 1) for p in hucre.get((cx + dx, cy + dy), [])]
        return sorted(y for y in ys if y[0] <= km_)[:n]

    def il_ilce_metin(t):
        """"Antalya/Alanya", "ANTALYA - MANAVGAT", "ANTALYA KEMER", "İStanbul/Kartal" → (il, ilçe anahtarı | None)."""
        if not isinstance(t, str):
            return None, None
        parca = [p for p in re.split(r"[/,\-]+|\s+", t) if p.strip()]
        il = next((kd.ILLER[kd.harfler(p)] for p in parca if kd.harfler(p) in kd.ILLER), None)
        if not il:
            return None, None
        ilce = next((kd.harfler(p) for p in parca if (il, kd.harfler(p)) in ilce_ad), None)
        return il, ilce

    haric, konumsuz, disari = [], 0, []
    aday = []
    for s in acik:
        metin = _big_duz(f"{s.get('name') or ''} {s.get('city') if isinstance(s.get('city'), str) else ''}")
        neden = next((n for rx, n in BIG_HARIC if re.search(rx, metin)), None)
        a, o = s.get("latitude"), s.get("longitude")
        try:
            a, o = float(a), float(o)
        except (TypeError, ValueError):
            a = o = 0.0
        kw = s.get("powerKw") if isinstance(s.get("powerKw"), (int, float)) else 0
        fiyat = s.get("pricePerKwh") if isinstance(s.get("pricePerKwh"), (int, float)) and 1 <= s["pricePerKwh"] <= 100 else None
        if neden:
            haric.append((neden, s.get("name"), bool(a or o))); continue
        if not kw and fiyat is None:
            haric.append(("güç ve fiyat yok", s.get("name"), bool(a or o))); continue
        if not (a or o) or abs(a - o) < 1e-9:
            konumsuz += 1; continue
        if not (kd.in_turkey(a, o) or kd.sinira_km(a, o) <= kd.KIYI_KM):
            disari.append(f"{s.get('name')} ({a:.5f}, {o:.5f})"); continue
        dc = s.get("deviceType") == "dc" or s.get("isDc") is True
        aday.append({"id": str(s["id"]), "ham": s.get("name") or "", "n": _big_ad(s.get("name")), "a": a, "o": o, "dc": dc, "kw": kw,
                     "fiyat": fiyat, "il_ilce": il_ilce_metin(s.get("city"))})
    def konum_ilce(a, o, il):
        """Konumun 8 km çevresindeki en yakın 5 EPDK kaydından en az 4'ünün ilçesi (yoksa None)."""
        say = {}
        for d, il2, ic in cevre(a, o, 8, 5):
            if il2 == il and ic:
                say[ic] = say.get(ic, 0) + 1
        return max(say, key=say.get) if say and max(say.values()) >= 4 else None

    # Gruplama (birleşim-bul): BIG_AYNI_YER_M içinde her cihaz; aynı ad BIG_AYNI_AD_M; ortak ayırt edici sözcük BIG_GRUP_M içinde.
    # Ayrıca şehir alanındaki ilçesi konumuyla çelişen cihaz, aynı adlı ve konumu o ilçeye uyan cihaz 20 km içindeyse onun yerine
    # taşınır (ör. "Limak Deluxe Hotel" A ünitesi 9 km ötede Muratpaşa'da görünüyor, B ünitesi otelin bulunduğu Aksu'da).
    for x in aday:
        il, ilce = x["il_ilce"]
        x["uyar"] = None if not (il and ilce) else (konum_ilce(x["a"], x["o"], il) in (ilce, None))
    tasinan = []
    ust = list(range(len(aday)))
    def kok(i):
        while ust[i] != i:
            ust[i] = ust[ust[i]]; i = ust[i]
        return i
    for i, x in enumerate(aday):
        for j in range(i):
            y = aday[j]
            m = _km(x["a"], x["o"], y["a"], y["o"]) * 1000
            if (m <= BIG_AYNI_YER_M or (m <= BIG_AYNI_AD_M and _big_duz(x["n"]) == _big_duz(y["n"]))
                    or (m <= BIG_GRUP_M and (_big_kok(x["n"]) & _big_kok(y["n"])) - _BIG_GENEL)):
                ust[kok(i)] = kok(j)
            elif ({x["uyar"], y["uyar"]} == {True, False} and x["il_ilce"] == y["il_ilce"] and _big_duz(x["n"]) == _big_duz(y["n"])
                  and m <= 20000):
                yanlis = x if x["uyar"] is False else y
                dogru = y if yanlis is x else x
                yanlis["a"], yanlis["o"] = dogru["a"], dogru["o"]
                tasinan.append(f"{yanlis['n']} (cihaz {yanlis['id']}, {m / 1000:.1f} km)")
                ust[kok(i)] = kok(j)
    gruplar = {}
    for i, x in enumerate(aday):
        gruplar.setdefault(kok(i), []).append(x)
    out, fiyat_farkli, il_duzelen = [], [], []
    for g in gruplar.values():
        adlar = [x["n"] for x in g]
        ad = sorted(set(adlar), key=lambda n: (-adlar.count(n), len(n)))[0]
        a, o = sum(x["a"] for x in g) / len(g), sum(x["o"] for x in g) / len(g)
        nac, ndc = sum(not x["dc"] for x in g), sum(x["dc"] for x in g)
        pr = {}
        for tur, uy in (("ac", [x for x in g if not x["dc"]]), ("dc", [x for x in g if x["dc"]])):
            f = sorted({x["fiyat"] for x in uy if x["fiyat"] is not None})
            if f:
                pr[tur] = f[-1]
                if len(f) > 1:
                    fiyat_farkli.append(f"{ad}: {tur.upper()} {'/'.join(f'{v:g}' for v in f)}")
        # il/ilçe: cihazların şehir metni; konumun çevresindeki EPDK kayıtlarının iliyle çelişiyorsa ya da yoksa konumdan
        cv = cevre(a, o, 30)
        il_say = {}
        for d, il, _ in cv[:5]:
            il_say[il] = il_say.get(il, 0) + 1
        konum_il = max(il_say, key=il_say.get) if il_say and max(il_say.values()) >= 3 else None
        metin = [x["il_ilce"] for x in g if x["il_ilce"][0]]
        il = metin[0][0] if metin else None
        if konum_il and il != konum_il and (il is None or not any(y[1] == il for y in cv[:5] if y[0] < 15)):
            if il:
                il_duzelen.append(f"{ad}: şehir alanı {il}, konum {konum_il} (konuma göre yazıldı)")
            il = konum_il
        ki = konum_ilce(a, o, il) if il else None
        ilceler = [x[1] for x in metin if x[0] == il and x[1]]
        ilce = ki or (ilceler[0] if ilceler else None)  # çevresindeki EPDK kayıtları ilçede birleşiyorsa o, yoksa şehir alanı
        if ki and ilceler and ki not in ilceler:
            il_duzelen.append(f"{ad}: şehir alanında ilçe {ilce_ad.get((il, ilceler[0]))}, konum {ilce_ad.get((il, ki))} (konuma göre yazıldı)")
        yer = ", ".join(v for v in (ilce_ad.get((il, ilce)) if ilce and ilce != "merkez" else None, il) if v)
        kws = [x["kw"] for x in g if x["kw"]]
        r = {"i": "bigstation" + min((x["id"] for x in g), key=int), "a": round(a, 6), "o": round(o, 6), "n": ad, "b": "BIG Station",
             "ac": nac, "dc": ndc, "c": len(g), "k": max(kws) if kws else 0, "t": (["Type 2"] if nac else []) + (["CCS"] if ndc else []),
             "ad": yer, "pr": pr,
             # cih: istasyondaki cihaz kimlikleri; site detay açılınca /api/durum/bigstation?c=… ile anlık boş/dolu durumunu sorar
             "cih": sorted({x["id"] for x in g}, key=int)}
        if any(f"{ad}: " in x for x in fiyat_farkli):
            r["prn"] = "fiyat ünitelere göre değişiyor, en yükseği gösteriliyor"
        out.append(clean(r))
    print(f"bigstation: dışarıda bırakılan {len(haric)} cihaz (" + "; ".join(f"{n}: {a}{'' if k else ' [konumsuz]'}" for n, a, k in sorted(haric, key=str)) + ")")
    print(f"bigstation: konumu 0/0 ya da bozuk {konumsuz} cihaz atlandı; Türkiye dışı {len(disari)}" + (f" ({'; '.join(disari)})" if disari else ""))
    print(f"bigstation: {len(aday)} cihaz → {len(out)} istasyon")
    if fiyat_farkli:
        print("bigstation: aynı istasyonda farklı fiyat (en yükseği yazıldı): " + "; ".join(fiyat_farkli))
    if tasinan:
        print("bigstation: konumu aynı adlı ünitenin konumuna taşınan (ilçesi konumuyla çelişiyordu): " + "; ".join(tasinan))
    if il_duzelen:
        print("bigstation: il/ilçe uyuşmazlığı: " + "; ".join(il_duzelen))
    for x in sorted(windmark, key=lambda x: x["no"]):
        en = min(out, key=lambda r: _km(x["a"], x["o"], r["a"], r["o"]), default=None)
        d = _km(x["a"], x["o"], en["a"], en["o"]) * 1000 if en else 1e9
        print(f"bigstation: EPDK {x['no']} {x.get('ad', '')} ({kd.il_ilce_epdk(x.get('adres'))[0]}) → "
              + (f"{en['n']} {d:.0f} m" if d <= BIG_EPDK_M else f"karşılığı yok (en yakın {en['n'] if en else '-'} {d / 1000:.1f} km)"))
    return out


# CV Charging (Charging Vehicles; işletmeci CW Enerji): istasyon adresleri sayfasındaki haritanın kullandığı iki açık adres.
# Liste (konum, ad, adres, il/ilçe) tek istekle; soketler (AC/DC, kW) istasyon başına bir istekle (aralarında CV_BEKLE sn).
# Sayfada ve istasyon detay sayfalarında istasyon bazlı fiyat yok: tarife tek (arac-sarj-tarifeleri, site/tarifeler.json).
# Anlık durum alanları (müsait/kullanımda, soket durumu) haritada gösterilmediği için yazılmaz.
CV_SAYFA = "https://cv-charging.com/tr/cv-arac-sarj-istasyonlari"
CV_LISTE = "https://cv-charging.com/views/api/get_istasyon_api.php"
CV_SOKET = "https://cv-charging.com/views/api/get_istasyon_soket_api.php?location_id={}"
CV_BEKLE = 0.3
CV_BUYUK = {"BMW", "AVM", "ODC", "AOSB", "CMC", "CW", "EGS", "MCG", "MYV", "PH", "VIB"}


CV_YABANCI = {"CAPITAL"}


def _cv_ad(t):
    """"ABANT ADEN BOUTIQUE HOTEL & SPA" → "Abant Aden Boutique Hotel & Spa"; kısaltmalar (BMW, AVM) korunur. Türkçe harfi olmayan,
    I içeren sözcük ünlü uyumuna uymuyorsa (E ile I bir arada) ya da yabancı harf dizisi içeriyorsa yabancı sayılır, I → i
    ("SEMERKANDLINE" → "Semerkandline", "POINT" → "Point"); uyanlar Türkçe ("GIDA" → "Gıda", "AKARYAKIT" → "Akaryakıt")."""
    def kelime(w):
        if w in CV_BUYUK or not w[:1].isalpha():
            return w
        if ("I" in w and not re.search("[İŞĞÜÖÇ]", w)
                and (w in CV_YABANCI or ("E" in w) or re.search(r"[WQX]|OI|IO|Y$", w))):
            return "-".join(x[:1] + x[1:].lower() for x in w.split("-"))
        return _tr_baslik(w)
    return " ".join(kelime(w) for w in str(t or "").split())


def _cv_adres(adres, il, ilce):
    """Adres satırlarını tek satıra indirir, sondaki boş "/" ve "Turkey" parçalarını atar; il adresin sonunda yoksa adreste geçmeyen ilçe ve il eklenir."""
    import konum_denetim as kd
    s = re.sub(r"\s+", " ", " / ".join(p.strip() for p in str(adres or "").splitlines() if p.strip()))
    s = re.sub(r"^[\s/:]+|[\s/]+$", "", s)
    s = re.sub(r"(?i)\s+turkey$", "", s).strip(" /")
    m = re.search(r"([^\s/]+)\s+([^\s/]+)$", s)  # "Muratpaşa/Antalya Antalya", "AYDIN Aydın": sondaki yinelenen il atılır
    if m and kd.fold(m[1]) == kd.fold(m[2]):
        s = s[:m.start(2)].rstrip()
    if kd.il_serbest(s) != il:
        var = set(re.findall(r"[a-z]+", kd.fold(s)))
        ek = [x for x in (ilce if ilce and kd.harfler(ilce) != "merkez" else None, il) if x and kd.fold(x) not in var]
        s = ", ".join([s] + ek) if s else ", ".join(x for x in (ilce, il) if x)
    return s


def cv():
    import time
    import konum_denetim as kd
    liste = json.loads(get(CV_LISTE))
    if not liste.get("ok") or not isinstance(liste.get("istasyonlar"), list):
        raise RuntimeError("yanıtta 'istasyonlar' listesi yok")
    out, soketsiz, disari = [], [], []
    for n, s in enumerate(liste["istasyonlar"]):
        try:
            a, o = float(s.get("latitude")), float(s.get("longitude"))
        except (TypeError, ValueError):
            a = o = 0.0
        if not (kd.in_turkey(a, o) or kd.sinira_km(a, o) <= kd.KIYI_KM):
            disari.append(f"{s.get('title')} ({a}, {o})"); continue
        if n:
            time.sleep(CV_BEKLE)
        try:
            sk = json.loads(get(CV_SOKET.format(int(s["api_location_id"]))))
        except Exception as e:  # noqa: BLE001  soketleri okunamayan istasyon yine gösterilir (soket sayısı listeden)
            sk = {}; soketsiz.append(f"{s.get('title')}: {e}")
        r = {"i": f"cv{int(s['i_id'])}", "a": round(a, 6), "o": round(o, 6), "n": _cv_ad(s.get("title")), "b": "CV Charging", "t": []}
        il = kd.ILLER.get(kd.harfler(s.get("il_name") or ""))
        r["ad"] = _cv_adres(s.get("adres"), il, (s.get("ilce_name") or "").strip())
        for ist in sk.get("istasyonlar") or []:
            for k in ist.get("soketler") or []:
                dc = str(k.get("soket_tipi") or "").upper().startswith("DC")
                tip = "dc" if dc else "ac"
                r[tip] = r.get(tip, 0) + 1; r["c"] = r.get("c", 0) + 1
                kw = k.get("power_kw") if isinstance(k.get("power_kw"), (int, float)) else 0
                r["k"] = max(r.get("k", 0), round(kw))
                t = "CCS" if dc else "Type 2"
                if t not in r["t"]:
                    r["t"].append(t)
        if not r.get("c"):
            r["c"] = s.get("toplam_soket") if isinstance(s.get("toplam_soket"), int) else 0
        out.append(clean(r))
    print(f"cv: listede {len(liste['istasyonlar'])} istasyon → {len(out)}; Türkiye dışı/konumsuz {len(disari)}"
          + (f" ({'; '.join(disari)})" if disari else ""))
    if soketsiz:
        print(f"cv: soketleri okunamayan {len(soketsiz)}: " + "; ".join(soketsiz))
    if EPDK_API.exists():  # karşılaştırma: resmi listede 300 m içinde karşılığı olmayan EPDK kayıtları
        yok = [f"{x['no']} {x.get('ad', '')}" for x in json.loads(EPDK_API.read_text(encoding="utf-8")).get("istasyonlar", [])
               if re.search(r"charging vehicles|\bcw enerji", kd.fold(x.get("marka", "") + " " + x.get("isletmeci", "")))
               and ok_coord(x.get("a"), x.get("o")) and not any(_km(x["a"], x["o"], r["a"], r["o"]) <= 0.3 for r in out)]
        print(f"cv: resmi listede 300 m içinde karşılığı olmayan EPDK kayıtları gösterilmiyor ({len(yok)})" + (f": {'; '.join(yok)}" if yok else ""))
    return out


SOURCES = {"trugo": (trugo, "https://trugo.com.tr/individual/network", 500),
           "zes": (zes, "https://zes.net/tr/sarj-istasyonlari", 500),
           "ovolt": (ovolt, "https://ovolt.com.tr/istasyon-haritasi", 50),
           "wat": (wat, "https://www.watmobilite.com/istasyon-haritasi", 100),
           "voltup": (voltup, "https://voltup.com.tr/#istasyonlar", 20),
           "rst": (rst, "https://rstchargepoint.com/#fiyatlar", 30),
           "bigstation": (bigstation, BIG_SAYFA, 15),
           "cv": (cv, CV_SAYFA, 50)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    secilen = [a for a in sys.argv[1:] if a in SOURCES] or list(SOURCES)
    if len(secilen) < len(sys.argv[1:]):
        sys.exit("bilinmeyen ağ: " + ", ".join(a for a in sys.argv[1:] if a not in SOURCES) + " (seçenekler: " + ", ".join(SOURCES) + ")")
    failed = 0
    for key in secilen:
        fn, page, minimum = SOURCES[key]
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
    if failed == len(secilen):
        sys.exit("Hiçbir ağdan veri alınamadı")


if __name__ == "__main__":
    main()
