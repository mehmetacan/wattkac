#!/usr/bin/env python3
"""İstasyon koordinatlarını birleştirmeden önce denetler; hatalıları düzeltir ya da haritadan çıkarır.

tools/istasyon_birlestir.py tarafından çağrılır. Kendi başına çalıştırılırsa (python3 tools/konum_denetim.py) yalnızca
denetimi yapar, özetini ve raporu yazar; site dosyasına dokunmaz.

Neden gerekli: EPDK koordinatları işletmecilerin girdiği haliyle yayımlanır. İki tür hata görüldü:
  - enlem/boylam yer değiştirmiş (ŞRJ/23878 Andera Park AVM Siirt → Karadeniz'in ortası)
  - tek basamak yanlış (ŞRJ/8240 IYAŞPARK AVM Isparta 37,18 → doğrusu 37,78)
OSM, Open Charge Map ve ağların listelerinde de aynı türden hatalar olabilir.

Kurallar (her kaynaktaki her kayıt için; eşikler aşağıdaki sabitlerde):
  1. Türkiye sınırı: nokta TR_POLY içinde olmalı. Kaba çokgenin deniz kıyısı kenarlarına en fazla KIYI_KM uzaklıktaki
     nokta (Bodrum otelleri, Gazipaşa Marina) iline ve ilçesine uyuyorsa kabul edilir; kara sınırında tampon yoktur.
     Enlem = boylam (alan kopyalanmış) ya da 0/0 konum hatalıdır.
  2. İlçe tutarlılığı (EPDK; adres "… İlçe / İL"): ilçedeki EPDK kayıtlarından yinelemeli medyanla (aykırılar
     ayıklanarak) ilçe merkezi bulunur. İlçe güvenilirse (en az 3 farklı yer, %60'ı birbirine uyuyor) eşik
     max(2 × çekirdeğin p95 yarıçapı, ILCE_TABAN_KM).
  3. İl tutarlılığı (adreste il varsa): kaydın, ilinin "doğrulanmış noktalarına" (ilçesine uyan EPDK kayıtları, güvenilir
     ilçe merkezleri, il adı doğrulanmış adres aramaları) en yakın uzaklığı d_il. d_il ≤ eşik (max(IL_TABAN_KM,
     3 × ildeki komşu uzaklığının p95'i), en çok IL_TAVAN_KM) ise uyar. Eşik aşılıp başka ilin noktaları IL_ORAN kat
     daha yakınsa: d_il ≤ IL_UZAK_KM "il_uyumsuz" (şüpheli), daha fazlası ya da IL_ARAMA_KM içinde ilinden hiç nokta
     yoksa "il_uzak" (kesin hata). Başka il de yakın değilse (seyrek bölge) kayıt uyar sayılır.
     (İl merkezine uzaklık + p95 yarıçap kuralı denendi: kayıtlar il merkezinde yoğunlaştığı için ilçelerdeki
     binlerce doğru kaydı işaretliyordu; en yakın doğrulanmış nokta ölçütü il sınırlarını çok daha iyi izliyor.)
EPDK kaydı için onarım sırası:
  a. Yer değiştirme: (boylam, enlem) Türkiye'de ve ilçesine (ilçe güvenilir değilse iline) uyuyorsa takas edilir.
  b. Basamak hatası: enlem ya da boylamın tam kısmı ±1 ya da ilk iki ondalığından biri değiştirilerek bulunan aday
     ilçesine uyuyor VE aynı istasyonun/tesisin başka bir kaydı (OSM, OCM, resmi liste, başka EPDK kaydı, tesis
     eşleşmesi) adaya BASAMAK_M içindeyse kabul edilir. Bağımsız doğrulama yoksa koordinat uydurulmaz.
  c. Addaki yer adı (güvenilir bir ilçenin adı) şimdiki konumun yakınındaysa koordinat doğru, adres yanlış sayılır: bırakılır.
  d. Başka kaynaktan onarım: aynı istasyon (marka anahtarı aynı + ad benzer, ya da ayırt edici tesis adı aynı) adresteki
     ilçede/ilde başka kaynakta varsa onun konumu alınır; q o kaynağınki olur. Öncelik: resmi ağ listesi (r) > OSM (o) /
     OCM (c) > başka EPDK kaydı (e) > tesis eşleşmesi (p).
  e. Şimdiki konumu bağımsız bir kaynak (aynı istasyon 300 m içinde, birebir kopya değil) doğruluyorsa bırakılır
     (ör. ŞRJ/4015: adres "Urla / İZMİR", OSM'deki istasyon Ula/Muğla'da, koordinat da orada).
  f. Aynı adresin adres araması (konum_onbellek.json, q a/m) ilçesine uyuyorsa o konum.
  g. "il_uyumsuz" (orta uzaklık) kayıt bu noktada olduğu gibi bırakılır ve raporda "birakildi" olarak listelenir.
     "il_uzak" / Türkiye dışı kayıt ilçe merkezine (q "i", sitede "Konum yaklaşık") konur; ilçe güvenilir değilse
     haritadan çıkarılır (yanlış yerde göstermektense hiç göstermemek).
  İlçe uyuşmazlığı (il doğru, ilçeye uzak) tek başına konumu değiştirmez (çoğu zaman adresteki ilçe yanlıştır);
  yalnızca b ya da sıkı eşleşmeli d (OSM/OCM/resmi liste) doğrularsa düzeltilir.
OSM / OCM / resmi liste kayıtları: adreslerindeki il çoğu zaman güvenilmez (Trugo'da "İstanbul Yönü" gibi yön adları,
WAT'ta yanlış il), bu yüzden il uyuşmazlığında yalnızca kesin kanıtla işlem yapılır: çok uzaksa takas, ya da aynı
istasyonun adresteki ildeki EPDK kaydı. Türkiye dışındaki nokta takasla düzelmiyorsa: komşu ülkedeki gerçek istasyonlar
(Bulgaristan, Yunanistan, KKTC) "yurt dışı" sayılıp sessizce, diğerleri "cikarildi" olarak çıkarılır.

Rapor: data/epdk/konum_duzeltmeleri.json (düzeltilen ve çıkarılan her kayıt; kural adları KURAL sözlüğünde).
"""
import datetime, json, math, pathlib, re, statistics, sys

RAPOR = pathlib.Path("data/epdk/konum_duzeltmeleri.json")
KIYI_KM = 7.0         # kaba sınır çokgeninin dışında kalabilen kıyı noktaları (Gazipaşa Marina 5,2 km, Bodrum otelleri ≤ 4 km)
DESTEK_KM = 15.0      # sınır dışı kıyı noktasının / ili bilinmeyen kaydın yakınında bulunması gereken doğrulanmış nokta
IL_TABAN_KM = 40.0    # il eşiği: ilin doğrulanmış noktalarından en yakınına uzaklık en az bu kadar olunca şüpheli
IL_TAVAN_KM = 60.0    # seyrek illerde eşik (3 × komşu uzaklığı p95) bunu aşmaz
IL_UZAK_KM = 80.0     # bunun ötesi (ya da IL_ARAMA_KM içinde ilinden hiç nokta yoksa) kesin hata: doğrulama yoksa ilçe merkezi/çıkarma
IL_ARAMA_KM = 120.0
IL_ORAN = 1.5         # şüpheli sayılmak için başka ilin noktaları bu kat daha yakın olmalı (il sınırındaki kayıtlar için)
ILCE_TABAN_KM = 25.0  # ilçe eşiği en az bu kadar (büyük ilçeler)
BASAMAK_M = 300       # basamak düzeltmesinin aynı istasyonun başka kayıttaki konumuna en fazla uzaklığı

KURAL = {
    "yer_degistirme": "enlem/boylam yer değiştirmiş; takas edildi",
    "basamak": "tek basamak hatası; başka kaynakla doğrulanan düzeltme",
    "kaynak": "aynı istasyonun başka kaynaktaki konumu alındı",
    "adres": "aynı adresin adres araması (yaklaşık)",
    "ilce_merkezi": "ilçe merkezine yerleştirildi (yaklaşık)",
    "cikarildi": "makul konum bulunamadı; haritadan çıkarıldı",
    "birakildi": "ilinin dışında görünüyor ama doğrulayan kaynak yok; olduğu gibi bırakıldı (elle bakılmalı)",
}

IL_ADLARI = ("Adana Adıyaman Afyonkarahisar Ağrı Aksaray Amasya Ankara Antalya Ardahan Artvin Aydın Balıkesir Bartın Batman "
             "Bayburt Bilecik Bingöl Bitlis Bolu Burdur Bursa Çanakkale Çankırı Çorum Denizli Diyarbakır Düzce Edirne Elazığ "
             "Erzincan Erzurum Eskişehir Gaziantep Giresun Gümüşhane Hakkari Hatay Iğdır Isparta İstanbul İzmir Kahramanmaraş "
             "Karabük Karaman Kars Kastamonu Kayseri Kırıkkale Kırklareli Kırşehir Kilis Kocaeli Konya Kütahya Malatya Manisa "
             "Mardin Mersin Muğla Muş Nevşehir Niğde Ordu Osmaniye Rize Sakarya Samsun Siirt Sinop Sivas Şanlıurfa Şırnak "
             "Tekirdağ Tokat Trabzon Tunceli Uşak Van Yalova Yozgat Zonguldak").split()
TR = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç", "Â": "a", "â": "a", "Î": "i", "î": "i", "Û": "u", "û": "u"})


def fold(s):
    s = (s or "").translate(TR).lower()
    for a, b in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c"), ("i̇", "i")):
        s = s.replace(a, b)
    return s


def harfler(s):
    return re.sub(r"[^a-z]", "", fold(s))


ILLER = {harfler(n): n for n in IL_ADLARI}
ILLER.update({"kmaras": "Kahramanmaraş", "maras": "Kahramanmaraş", "afyon": "Afyonkarahisar", "icel": "Mersin",
              "urfa": "Şanlıurfa", "antep": "Gaziantep", "duzce": "Düzce"})
ADA = re.compile(r"\(\s*Ada:.*?\)")
ILCE_DEGIL = {"mahallesi", "mah", "caddesi", "cad", "sokagi", "sokak", "sk", "bulvari", "koyu", "no", "kat", "blok", "beldesi", ""}

# Türkiye'nin kaba sınırı (boylam, enlem). Ege'deki Yunan adalarını ve Kıbrıs'ı dışarıda bırakacak şekilde çizildi.
TR_POLY = [(26.35, 41.72), (26.6, 41.98), (27.0, 42.1), (28.05, 41.98), (28.15, 41.6), (29.1, 41.27), (31.0, 41.32), (32.5, 41.92),
           (33.5, 42.08), (35.2, 42.12), (36.5, 41.45), (38.0, 41.15), (40.0, 41.12), (41.5, 41.58), (42.8, 41.62), (43.5, 41.15),
           (44.85, 41.2), (44.85, 40.0), (44.6, 39.4), (44.45, 39.0), (44.85, 37.25), (44.3, 37.0), (42.3, 37.12), (42.2, 37.1), (41.2, 37.062), (40.0, 36.81),
           (39.0, 36.68), (38.0, 36.83), (37.4, 36.62), (36.7, 36.6), (36.65, 36.2), (36.4, 35.78), (35.85, 35.78), (35.9, 36.3), (35.5, 36.58),
           (34.6, 36.78), (33.9, 36.25), (32.8, 36.0), (32.0, 36.5), (30.6, 36.2), (30.4, 36.18), (29.66, 36.18), (29.38, 36.21), (29.1, 36.55),
           (28.6, 36.75), (27.9, 36.62), (27.35, 36.66), (27.7, 36.8), (27.6, 36.98), (27.2, 37.0), (27.22, 37.15), (27.18, 37.35),
           (27.2, 37.55), (27.15, 37.75), (26.75, 38.2), (26.25, 38.25), (26.22, 38.5), (26.45, 38.7), (26.75, 38.75), (26.65, 39.2),
           (26.58, 39.36), (26.0, 39.45), (26.1, 39.9), (26.15, 40.05), (26.2, 40.3), (26.3, 40.6), (26.6, 40.62), (26.0, 40.72),
           (26.3, 41.25), (26.55, 41.6)]
TR_ISLANDS = [(25.6, 40.08, 26.02, 40.26), (25.95, 39.78, 26.1, 39.87)]  # Gökçeada, Bozcaada


def in_turkey(lat, lon):
    if any(x0 <= lon <= x1 and y0 <= lat <= y1 for x0, y0, x1, y1 in TR_ISLANDS):
        return True
    inside, n = False, len(TR_POLY)
    for k in range(n):
        x1, y1 = TR_POLY[k]; x2, y2 = TR_POLY[(k + 1) % n]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


# TR_POLY'un deniz kıyısı olan kenarları (k → k+1). Kara sınırları (Bulgaristan, Yunanistan/Meriç, doğu ve güney komşular)
# dışarıda: tampon yalnızca kıyıda uygulanır, Kapıkule/Svilengrad gibi sınır ötesi noktalar Türkiye sayılmaz.
KIYI_KENAR = list(range(3, 13)) + list(range(32, 67))


def sinira_km(lat, lon):
    """Noktanın kaba sınır çokgeninin deniz kıyısı kenarlarına uzaklığı (km, yaklaşık düzlem hesabı)."""
    kx, ky = math.cos(math.radians(lat)) * 111.32, 110.57
    best = 1e9
    for k in KIYI_KENAR:
        (x1, y1), (x2, y2) = TR_POLY[k], TR_POLY[(k + 1) % len(TR_POLY)]
        ax, ay, bx, by = (x1 - lon) * kx, (y1 - lat) * ky, (x2 - lon) * kx, (y2 - lat) * ky
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, -(ax * dx + ay * dy) / ((dx * dx + dy * dy) or 1)))
        best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def km(a, b, c, d):
    t = math.radians
    h = math.sin(t(c - a) / 2) ** 2 + math.cos(t(a)) * math.cos(t(c)) * math.sin(t(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(min(1.0, math.sqrt(h)))


def gecerli(a, o):
    return isinstance(a, (int, float)) and isinstance(o, (int, float)) and -90 <= a <= 90 and -180 <= o <= 180 and (a or o)


# ---------- adres çözümleme ----------

def il_ilce_epdk(adres):
    """EPDK adresi "… İlçe / İL" biçimindedir → (il, ilçe_anahtarı); bulunamayan None."""
    a = ADA.sub("", adres or "").strip()
    if "/" not in a:
        return None, None
    sol, il = a.rsplit("/", 1)
    il = ILLER.get(harfler(il))
    if not il:
        return None, None
    w = sol.split()
    ilce = harfler(w[-1]) if w else ""
    return il, (None if ilce in ILCE_DEGIL or len(ilce) < 3 else ilce)


def il_serbest(adres):
    """OCM / resmi liste adresleri ("…, Nilüfer/Bursa, Bursa", "… KAYNAŞLI / DUZCE", "Van"): yalnızca sondaki üç parçadan
    biri tek başına bir il adıysa il kabul edilir ("Ankara Caddesi" gibi sokak adlarına aldanmamak için)."""
    parcalar = [p for p in re.split(r"[,/]", adres or "") if p.strip()]
    for p in reversed(parcalar[-3:]):
        t = [x for x in re.findall(r"[a-z]+", fold(p)) if x not in ("turkiye", "turkey", "tr")]
        if t and ("".join(t) in ILLER):
            return ILLER["".join(t)]
    return None


# ---------- ad benzerliği ----------

GENEL = set("""avm otel hotel resort petrol akaryakit akaryakıt istasyonu istasyon sarj şarj dc ac kw hizli merkez merkezi ve the of
ltd sti as san tic a b c d e f g h no mah mahallesi cad caddesi sk sokak sokagi bulvari bulv site sitesi tesis tesisi tesisleri
dinlenme otopark otoparki yonu yolu yol plaza center mall arac elektrikli enerji ag agi ticaret sanayi turizm insaat sube
istanbul ankara izmir belediye belediyesi belediyesinin hastane hastanesi universitesi otel oteli restoran restaurant
restorant cafe kafe market marketi sube subesi grup ticaret""".split())


def ad_parcalari(ad, haric=()):
    # marka anahtarıyla başlayan sözcükler de atılır ("ASTORŞARJ", "POWERŞARJ")
    on = tuple(h for h in haric if h and len(h) >= 3)
    return [x for x in re.findall(r"[a-z0-9]+", fold(ad))
            if x not in GENEL and x not in haric and not x.isdigit() and len(x) >= 2 and not (on and x.startswith(on))]


def benzer(a, b, haric=()):
    """0..1 arası ad benzerliği: ayırt edici sözcüklerin örtüşmesi; "IYAŞPARK" ~ "Iyaş Park" gibi bitişik yazımlar da sayılır."""
    ta, tb = ad_parcalari(a, haric), ad_parcalari(b, haric)
    if not ta or not tb:
        return 0.0
    ca, cb = "".join(ta), "".join(tb)
    if ca == cb and len(ca) >= 6:
        return 1.0
    sa, sb = {x for x in ta if len(x) >= 3}, {x for x in tb if len(x) >= 3}
    s = len(sa & sb) / len(sa | sb) if sa and sb else 0.0  # Jaccard: zincir adları ("Köfteci Yusuf …") tek başına yetmez
    kisa, uzun = sorted((ca, cb), key=len)
    if len(kisa) >= 6 and kisa in uzun and len(kisa) >= 0.75 * len(uzun):
        s = max(s, 0.75)
    return s


# ---------- yinelemeli medyan ----------

def merkez(noktalar):
    """Aykırıları ayıklayan yinelemeli medyan → (enlem, boylam, p95_km, çekirdek_sayı, toplam)."""
    a = statistics.median(p[0] for p in noktalar); o = statistics.median(p[1] for p in noktalar)
    tut = noktalar
    for _ in range(6):
        ds = [km(a, o, *p) for p in noktalar]
        sinir = max(4 * statistics.median(ds), 5.0)
        tut = [p for p, d in zip(noktalar, ds) if d <= sinir]
        a2 = statistics.median(p[0] for p in tut); o2 = statistics.median(p[1] for p in tut)
        if (a2, o2) == (a, o):
            break
        a, o = a2, o2
    ds = sorted(km(a, o, *p) for p in tut)
    return a, o, ds[int(0.95 * (len(ds) - 1))], len(tut), len(noktalar)


class Izgara:
    """Basit uzamsal dizin (0,1° hücre)."""
    G = 0.1

    def __init__(self):
        self.h = {}

    def ekle(self, a, o, x):
        self.h.setdefault((int(a // self.G), int(o // self.G)), []).append((a, o, x))

    def yakin(self, a, o, r_km):
        """r_km içindeki (uzaklık, öğe) çiftleri, yakından uzağa."""
        ca, co = int(a // self.G), int(o // self.G)
        na = int(r_km / 11.1) + 1
        no = int(r_km / (11.1 * max(0.3, math.cos(math.radians(a))))) + 1
        out = []
        for i in range(ca - na, ca + na + 1):
            for j in range(co - no, co + no + 1):
                for pa, po, x in self.h.get((i, j), ()):
                    d = km(a, o, pa, po)
                    if d <= r_km:
                        out.append((d, x))
        out.sort(key=lambda t: t[0])
        return out

    def en_yakin(self, a, o, uygun, r_max):
        """uygun(öğe) olan en yakın öğenin uzaklığı ve kendisi; r_max içinde yoksa (inf, None). Yarıçap adım adım büyür."""
        r = 3.0
        while True:
            r = min(r, r_max)
            for d, x in self.yakin(a, o, r):
                if uygun(x):
                    return d, x
            if r >= r_max:
                return float("inf"), None
            r *= 3


# ---------- ana denetim ----------

class Kayit:
    __slots__ = ("kaynak", "kimlik", "a", "o", "ad", "marka", "adres", "il", "ilce", "ref", "q", "bayrak", "ilce_ok")

    def __init__(self, kaynak, kimlik, a, o, ad, marka, adres, il, ilce, ref, q):
        self.kaynak, self.kimlik, self.a, self.o, self.ad, self.marka = kaynak, kimlik, a, o, ad, marka
        self.adres, self.il, self.ilce, self.ref, self.q = adres, il, ilce, ref, q
        self.bayrak, self.ilce_ok = None, None


def denetle(epdk, resmi, osm, ocm, poi, cache, anahtar, yaz=True):
    """epdk: [{"no","ad","marka","adres","a","o"}]; resmi/osm/ocm: birleştiricinin kayıt sözlükleri (i, a, o, …);
    poi: {no: [a, o, tesis, osm]}; cache: {adres: [a, o, kalite]}; anahtar: marka anahtarı işlevi.
    Döner: (epdk_sonuc {no: (a, o, q) | None (çıkar)}, sil {OSM/OCM/resmi kimliği}, geçersiz yardımcı kayıtlar
    {EPDK no | adres}, rapor). resmi/osm/ocm kayıtlarının a/o alanları düzeltmede yerinde güncellenir."""
    K = []
    epdk_adres = {}
    for x in epdk:
        il, ilce = il_ilce_epdk(x["adres"])
        epdk_adres[x["no"]] = x["adres"]
        K.append(Kayit("e", x["no"], x["a"], x["o"], x["ad"], anahtar(x["marka"]), x["adres"], il, ilce, x, "e"))
    for q, liste in (("r", resmi), ("o", osm), ("c", ocm)):
        for s in liste:
            m = anahtar(s.get("b") or s.get("p") or s.get("w") or s.get("n") or "")
            K.append(Kayit(q, s["i"], s.get("a"), s.get("o"), s.get("n") or "", m, s.get("ad") or "", il_serbest(s.get("ad")), None, s, q))
    # yardımcı kaynaklar (yalnızca karşılaştırma ve onarım için): tesis eşleşmesi ve adres araması önbelleği
    yardim = []
    for no, v in (poi or {}).items():
        if v and no in epdk_adres:
            il, ilce = il_ilce_epdk(epdk_adres[no])
            yardim.append(Kayit("p", no, v[0], v[1], v[2] if len(v) > 2 else "", "", epdk_adres[no], il, ilce, None, "p"))
    for adres, v in (cache or {}).items():
        if v:
            il, ilce = il_ilce_epdk(adres)
            yardim.append(Kayit("k", adres, v[0], v[1], "", "", adres, il, ilce, None, v[2]))
    tum = K + yardim

    # 1) Türkiye sınırı
    for r in tum:
        if not gecerli(r.a, r.o):
            r.bayrak = "konum_yok"
        elif abs(r.a - r.o) < 1e-9:
            r.bayrak = "bozuk"  # enlem = boylam (kaynakta alan kopyalanmış)
        elif not in_turkey(r.a, r.o):
            r.bayrak = "kiyi" if sinira_km(r.a, r.o) <= KIYI_KM else "turkiye_disi"

    # 2) İlçe merkezleri (EPDK kayıtlarından; aynı yerdeki üniteler tek nokta sayılır)
    ilce_nokta = {}
    for r in K:
        if r.kaynak == "e" and r.il and r.ilce and r.bayrak in (None, "kiyi"):
            ilce_nokta.setdefault((r.il, r.ilce), set()).add((round(r.a, 3), round(r.o, 3)))
    ILCE = {}
    for k, pts in ilce_nokta.items():
        a, o, p95, n, top = merkez(list(pts))
        ILCE[k] = (a, o, max(2 * p95, ILCE_TABAN_KM), n >= 3 and n >= 0.6 * top, n, top)

    def ilce_uyar(r, a, o):
        """True: ilçe merkezine uyar; False: uymaz; None: ilçe güvenilir değil/bilinmiyor."""
        z = ILCE.get((r.il, r.ilce)) if r.il and r.ilce else None
        if not z or not z[3]:
            return None
        return km(a, o, z[0], z[1]) <= z[2]

    for r in tum:
        if r.kaynak in ("e", "p", "k") and r.bayrak in (None, "kiyi"):
            r.ilce_ok = ilce_uyar(r, r.a, r.o)

    # 3) İl destek noktaları: ilçesine uyan EPDK kayıtları, güvenilir ilçe merkezleri, il adı doğrulanmış adres aramaları
    destek = Izgara()
    il_site = {}
    for r in K:
        if r.kaynak == "e" and r.ilce_ok and r.il:
            s = (round(r.a, 2), round(r.o, 2))
            if s not in il_site.setdefault(r.il, set()):
                il_site[r.il].add(s); destek.ekle(r.a, r.o, (r.il, s))
    for (il, ilce), z in ILCE.items():
        if z[3]:
            destek.ekle(z[0], z[1], (il, ("ilce", ilce)))
    for r in yardim:
        if r.kaynak == "k" and r.il and r.bayrak is None and r.ilce_ok is not False:
            destek.ekle(r.a, r.o, (r.il, ("k", r.kimlik)))

    def d_il(il, a, o, haric=None):
        return destek.en_yakin(a, o, lambda x: x[0] == il and x[1] != haric, IL_ARAMA_KM)[0]

    # il eşiği: ilin kendi destek noktaları arasındaki en yakın komşu uzaklığından (seyrek illerde daha geniş)
    IL_ESIK = {}
    for il in set(ILLER.values()):
        ds = sorted(d for d in (d_il(il, s[0], s[1], haric=s) for s in il_site.get(il, ())) if d < float("inf"))
        p95 = ds[int(0.95 * (len(ds) - 1))] if ds else IL_TAVAN_KM
        IL_ESIK[il] = min(IL_TAVAN_KM, max(IL_TABAN_KM, 3 * p95))

    def il_durum(il, a, o):
        """0: iline uyar; 1: ilinden uzak (IL_ESIK–IL_UZAK_KM) ve başka il belirgin biçimde yakın; 2: çok uzak."""
        di = d_il(il, a, o)
        if di <= IL_ESIK[il]:
            return 0
        if di == float("inf"):
            return 2
        if destek.en_yakin(a, o, lambda x: x[0] != il, di / IL_ORAN)[0] == float("inf"):
            return 0  # seyrek bölge: başka ilin noktaları da daha yakın değil
        return 2 if di > IL_UZAK_KM else 1

    # ad içinde geçen yer adları (ilçe ya da il): koordinatın yakınındaysa koordinat doğrulanmış sayılır (adres yanlış olabilir)
    YER = {}
    for (il, ilce), z in ILCE.items():
        if z[3]:  # yalnızca güvenilir ilçe merkezi (kaydın kendisi tek başına kendi ilçesini "doğrulamasın")
            YER.setdefault(ilce, []).append(z)

    def ad_yeri(r, a, o):
        for t in sorted(set(re.findall(r"[a-z]+", fold(r.ad)))):
            if len(t) < 3 or t in GENEL:
                continue
            if any(km(a, o, z[0], z[1]) <= min(z[2], 40.0) for z in YER.get(t, ())):
                return t
            il = ILLER.get(t)
            if il and d_il(il, a, o) <= 15.0:  # il adı zayıf kanıt (sınır yakınında): yalnızca çok yakınsa
                return t
        return None

    def yerinde(r, a, o):
        """Aday konum kayda uyuyor mu? (Türkiye'de; ilçesine, ilçe bilinmiyorsa iline, o da yoksa doğrulanmış kayıtlara yakın)"""
        if not gecerli(a, o) or abs(a - o) < 1e-9:
            return False
        if not in_turkey(a, o) and not (sinira_km(a, o) <= KIYI_KM and destek.yakin(a, o, DESTEK_KM)):
            return False
        iu = ilce_uyar(r, a, o)
        if iu is not None:
            return iu
        if r.il:
            return il_durum(r.il, a, o) == 0
        return bool(destek.yakin(a, o, DESTEK_KM))

    # 4) İşaretleme
    for r in tum:
        if r.bayrak in ("konum_yok", "bozuk", "turkiye_disi"):
            continue
        if r.bayrak == "kiyi":
            # kıyı noktası (kaba sınırın birkaç km dışında): ilçesine de uymalı (Meis açığındaki "Demre" noktası gibi denizdekiler elenir)
            ok = il_durum(r.il, r.a, r.o) == 0 if r.il else bool(destek.yakin(r.a, r.o, DESTEK_KM))
            r.bayrak = None if ok and r.ilce_ok is not False else "turkiye_disi"
            continue
        if r.ilce_ok:
            continue
        d = il_durum(r.il, r.a, r.o) if r.il else None
        if d == 2:
            r.bayrak = "il_uzak"
        elif d == 1:
            r.bayrak = "il_uyumsuz"
        elif r.ilce_ok is False:
            r.bayrak = "ilce_uyumsuz"
    for r in K:
        # ağların listelerinde komşu ülkelerdeki (Bulgaristan, Yunanistan, KKTC) gerçek istasyonlar da var: hata değil,
        # yalnızca haritada gösterilmez. Takasla Türkiye'ye düşüyorsa aşağıda hata olarak ele alınır.
        if (r.kaynak != "e" and r.bayrak == "turkiye_disi" and 30 <= r.a <= 48 and 18 <= r.o <= 50
                and not in_turkey(r.o, r.a)):
            r.bayrak = "yurt_disi"
    isaret = {}
    for r in K:
        if r.bayrak:
            isaret.setdefault(r.kaynak, {}).setdefault(r.bayrak, 0)
            isaret[r.kaynak][r.bayrak] += 1

    # 5) Onarım adayları: bayraksız kayıtlar. EPDK dışındaki kaynakların adresleri güvenilmez (yön adları, yanlış il),
    # bu yüzden onların "il uyumsuz" kayıtları da aday olabilir; il grubu konumdan (en yakın doğrulanmış nokta) bulunur.
    temiz = Izgara()
    il_kayit = {}
    for r in tum:
        if r.bayrak is None or (r.kaynak in "roc" and r.bayrak in ("il_uyumsuz", "il_uzak")):
            temiz.ekle(r.a, r.o, r)
            il = r.il if r.kaynak in ("e", "p", "k") else None
            if not il:
                il = (destek.en_yakin(r.a, r.o, lambda x: True, 10.0)[1] or (None,))[0]
            if il:
                il_kayit.setdefault(il, []).append(r)

    def ayni_istasyon(r, s, siki=False):
        """Aynı istasyon ya da aynı tesis mi? 3: tesis eşleşmesi bu EPDK no için, 2: marka aynı + ad benzer, 1: tesis adı aynı."""
        if s is r or (s.kaynak == r.kaynak == "e" and s.kimlik == r.kimlik):
            return 0
        if s.kaynak == "p":
            return 3 if s.kimlik == r.kimlik else 0
        haric = {r.marka, s.marka, "merkez"} | ({harfler(r.il)} if r.il else set()) | ({r.ilce} if r.ilce else set())
        b = benzer(r.ad, s.ad, haric)
        if r.marka and s.marka == r.marka and b >= (0.75 if siki else 0.6):
            return 2
        if b >= 1.0:
            return 1
        return 0

    def basamak_adaylari(a, o):
        out = []
        for hangi, v in ((0, a), (1, o)):
            out += [(hangi, v - 1), (hangi, v + 1)]
            s = "%.6f" % v
            nokta = s.index(".")
            for poz in (nokta + 1, nokta + 2):
                out += [(hangi, float(s[:poz] + c + s[poz + 1:])) for c in "0123456789" if c != s[poz]]
        return [((v, o) if h == 0 else (a, v)) for h, v in out]

    def basamak_duzelt(r):
        best = None
        for ca, co in basamak_adaylari(r.a, r.o):
            if not yerinde(r, ca, co):
                continue
            for d, s in temiz.yakin(ca, co, BASAMAK_M / 1000):
                if s.kaynak != "k" and ayni_istasyon(r, s):
                    if best is None or d < best[0]:
                        best = (d, ca, co, s)
                    break
        return best

    def konum_dogrulayan(r):
        """Kaydın şimdiki konumunu bağımsız bir kaynak (OSM/OCM/resmi liste) doğruluyor mu? Aynı istasyon BASAMAK_M içinde,
        ama birebir aynı koordinatta değil (birebir aynısı çoğunlukla EPDK'dan kopyadır, bağımsız sayılmaz)."""
        for d, s in temiz.yakin(r.a, r.o, BASAMAK_M / 1000):
            if s.kaynak in "roc" and d > 0.005 and ayni_istasyon(r, s):
                return s
        return None

    ONCELIK = {"r": 0, "o": 1, "c": 1, "e": 2, "p": 3}

    def kaynak_onar(r, siki=False):
        best = None
        for s in il_kayit.get(r.il, ()):
            if s.kaynak not in ONCELIK or (siki and s.kaynak not in "roc"):
                continue
            tur = ayni_istasyon(r, s, siki)
            if not tur or not yerinde(r, s.a, s.o):
                continue
            puan = (ONCELIK[s.kaynak], -tur)
            if best is None or puan < best[0]:
                best = (puan, s)
        return best[1] if best else None

    epdk_sonuc, sil, kayitlar = {}, set(), []
    say = {k: 0 for k in KURAL}
    korundu = {"ilce_uyumsuz": 0, "il_uyumsuz": 0, "ad_yeri": 0, "diger_kaynak_il": 0}  # ad_yeri: ad ya da bağımsız kaynak doğruladı
    yurt_disi = 0

    def kaydet(r, kural, a=None, o=None, q=None, dayanak=None):
        say[kural] += 1
        if kural == "birakildi":
            kayitlar.append({"id": r.kimlik, "kaynak": r.kaynak, "ad": (r.ad or "")[:60], "il": r.il,
                             "eski": [round(r.a, 6), round(r.o, 6)], "kural": kural, "neden": r.bayrak, **({"dayanak": dayanak} if dayanak else {})})
            return
        eski = [round(r.a, 6), round(r.o, 6)] if gecerli(r.a, r.o) else None
        d = {"id": r.kimlik, "kaynak": r.kaynak, "ad": (r.ad or "")[:60], "il": r.il, "eski": eski,
             "yeni": [round(a, 6), round(o, 6)] if a is not None else None, "kural": kural, "neden": r.bayrak}
        if dayanak:
            d["dayanak"] = dayanak
        if eski and a is not None:
            d["km"] = round(km(r.a, r.o, a, o), 1)
        kayitlar.append(d)
        if r.kaynak == "e":
            epdk_sonuc[r.kimlik] = (a, o, q) if a is not None else None
        elif a is None:
            sil.add(r.kimlik)
        else:
            r.ref["a"], r.ref["o"] = a, o

    def takas_uygun(r):
        return gecerli(r.a, r.o) and in_turkey(r.o, r.a) and yerinde(r, r.o, r.a) and bool(destek.yakin(r.o, r.a, DESTEK_KM))

    for r in K:
        b = r.bayrak
        if b is None:
            continue
        if b == "yurt_disi":
            yurt_disi += 1; sil.add(r.kimlik)
            continue
        if r.kaynak != "e":
            # OSM / OCM / resmi liste
            if b in ("konum_yok", "bozuk"):
                kaydet(r, "cikarildi")
            elif b == "turkiye_disi":
                if takas_uygun(r):
                    kaydet(r, "yer_degistirme", r.o, r.a)
                else:
                    kaydet(r, "cikarildi")
            else:
                # adresteki il bu kaynaklarda güvenilmez: yalnızca bağımsız doğrulamayla düzeltilir
                if b == "il_uzak" and takas_uygun(r):
                    kaydet(r, "yer_degistirme", r.o, r.a)
                    continue
                s = kaynak_onar(r, siki=True)
                if s and s.kaynak == "e":
                    kaydet(r, "kaynak", s.a, s.o, dayanak=s.kimlik)
                else:
                    korundu["diger_kaynak_il"] += 1
            continue
        # EPDK
        if b == "ilce_uyumsuz":
            # il içinde ama ilçesine uzak: çoğu zaman adres yanlış; yalnızca bağımsız doğrulama varsa düzelt
            x = basamak_duzelt(r)
            if x:
                kaydet(r, "basamak", x[1], x[2], "e", x[3].kimlik)
                continue
            s = kaynak_onar(r, siki=True)
            if s:
                kaydet(r, "kaynak", s.a, s.o, s.q, s.kimlik)
                continue
            korundu["ilce_uyumsuz"] += 1
            continue
        if takas_uygun(r):
            kaydet(r, "yer_degistirme", r.o, r.a, "e")
            continue
        x = basamak_duzelt(r) if gecerli(r.a, r.o) else None
        if x:
            kaydet(r, "basamak", x[1], x[2], "e", x[3].kimlik)
            continue
        # adres mi yanlış, koordinat mı? Addaki yer adı (ilçe) şimdiki konumun yakınındaysa koordinat korunur
        yer = ad_yeri(r, r.a, r.o) if b in ("il_uyumsuz", "il_uzak") else None
        if yer:
            korundu["ad_yeri"] += 1
            kaydet(r, "birakildi", dayanak="ad: " + yer)
            continue
        s = kaynak_onar(r)  # adresteki ilçede/ilde aynı istasyon başka kaynakta var
        if s:
            kaydet(r, "kaynak", s.a, s.o, s.q, s.kimlik)
            continue
        s = konum_dogrulayan(r) if b in ("il_uyumsuz", "il_uzak") else None
        if s:  # şimdiki konumu bağımsız bir kaynak doğruluyor: adres yanlış olmalı
            korundu["ad_yeri"] += 1
            kaydet(r, "birakildi", dayanak=s.kimlik)
            continue
        g = cache.get(r.adres) if cache else None
        if g and g[2] in ("a", "m") and yerinde(r, g[0], g[1]):
            kaydet(r, "adres", g[0], g[1], g[2])
            continue
        if b == "il_uyumsuz":
            korundu["il_uyumsuz"] += 1  # ilinden orta uzaklıkta, doğrulayan kaynak yok: koordinat uydurulmaz
            kaydet(r, "birakildi")
            continue
        z = ILCE.get((r.il, r.ilce)) if r.il and r.ilce else None
        if z and z[3]:
            kaydet(r, "ilce_merkezi", round(z[0], 5), round(z[1], 5), "i")
            continue
        kaydet(r, "cikarildi")

    gecersiz_yardim = {r.kimlik for r in yardim if r.bayrak not in (None, "ilce_uyumsuz")}
    ozet = {"denetlenen": {q: sum(1 for r in K if r.kaynak == q) for q in "eroc"},
            "isaretlenen": isaret, "duzeltme": say, "korunan": korundu, "yurt_disi": yurt_disi,
            "gecersiz_yardimci": len(gecersiz_yardim),
            "ilce": {"toplam": len(ILCE), "guvenilir": sum(1 for z in ILCE.values() if z[3])},
            "esikler": {"kiyi_km": KIYI_KM, "il_esik_km": [IL_TABAN_KM, IL_TAVAN_KM], "il_uzak_km": IL_UZAK_KM,
                        "il_oran": IL_ORAN, "ilce_taban_km": ILCE_TABAN_KM, "basamak_m": BASAMAK_M}}
    rapor = {"guncelleme": datetime.date.today().isoformat(), "ozet": ozet, "kurallar": KURAL,
             "kayitlar": sorted(kayitlar, key=lambda d: (d["kural"], str(d["id"])))}
    if yaz:
        RAPOR.parent.mkdir(parents=True, exist_ok=True)
        RAPOR.write_text(json.dumps(rapor, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    return epdk_sonuc, sil, gecersiz_yardim, rapor


def ozet_satiri(rapor):
    s, k = rapor["ozet"]["duzeltme"], rapor["ozet"]["korunan"]
    return ("konum denetimi: yer değiştirme %d, basamak düzeltmesi %d, başka kaynaktan %d, adres araması %d, ilçe merkezi %d, "
            "çıkarılan %d; doğrulanamadığı için olduğu gibi bırakılan %d, yurt dışı %d" % (
                s["yer_degistirme"], s["basamak"], s["kaynak"], s["adres"], s["ilce_merkezi"], s["cikarildi"],
                sum(k.values()), rapor["ozet"]["yurt_disi"]))


def main():
    """Yalnızca denetim: girdileri istasyon_birlestir.py ile aynı biçimde okur, raporu yazar, özeti basar."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import istasyon_birlestir as B
    epdk = [{"no": no, "ad": ad, "marka": m, "adres": adr, "a": k[0], "o": k[1]}
            for no, ad, m, _, adr, acik, k, _ in B.epdk_kayitlari() if k]
    oku = lambda p, alan="istasyonlar": json.loads(p.read_text(encoding="utf-8")).get(alan, []) if p.exists() else []
    # istasyon_birlestir.py gibi yalnızca RESMI ağların istasyon dosyaları (ör. voltup_fiyat.json istasyon listesi değildir)
    ag = lambda p: json.loads(p.read_text(encoding="utf-8")).get("ag")
    resmi = [r for f in sorted(B.AGLAR.glob("*.json")) if ag(f) in B.RESMI for r in oku(f)]
    cache = json.loads(B.CACHE.read_text(encoding="utf-8")) if B.CACHE.exists() else {}
    poi = json.loads(B.POI.read_text(encoding="utf-8")) if B.POI.exists() else {}
    _, _, _, rapor = denetle(epdk, resmi, oku(B.OSM), oku(B.OCM), poi, cache, B.key, yaz="--yazma" not in sys.argv)
    print(ozet_satiri(rapor))
    print(json.dumps(rapor["ozet"], ensure_ascii=False))


if __name__ == "__main__":
    main()
