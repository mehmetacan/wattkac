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
  (ASTOR Şarj'ın haritası map-api.echargo.com kullanıyor ama sunucudan yapılan istekleri reddediyor (HTTP 404);
   erişim kısıtını aşmaya çalışmıyoruz, ASTOR istasyonları EPDK + OSM'den gelir.)

Kurallar: günde bir kez, her kaynağa tek istek; anahtar/oturum gerektiren kaynaklar KULLANILMAZ.
Bir ağın çekimi başarısız olursa o ağın önceki dosyası korunur.
Yalnızca bazı ağları çekmek için adlarını verin: python3 tools/ag_istasyonlari.py voltup
Kayıt alanları istasyon_cek.py ile aynıdır (i, a, o, n, b, k, t, ac, dc, c, ad) + pr (soket fiyatları, varsa).
"""
import html, json, math, pathlib, re, sys, urllib.request, datetime
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


SOURCES = {"trugo": (trugo, "https://trugo.com.tr/individual/network", 500),
           "zes": (zes, "https://zes.net/tr/sarj-istasyonlari", 500),
           "ovolt": (ovolt, "https://ovolt.com.tr/istasyon-haritasi", 50),
           "wat": (wat, "https://www.watmobilite.com/istasyon-haritasi", 100),
           "voltup": (voltup, "https://voltup.com.tr/#istasyonlar", 20),
           "rst": (rst, "https://rstchargepoint.com/#fiyatlar", 30)}


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
