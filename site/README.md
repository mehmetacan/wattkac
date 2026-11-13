# WattKaç kampanya sitesi (Cloudflare Pages)

Cloudflare Pages ayarları:
- Framework preset: None
- Build command: `cp data/kampanyalar.json site/kampanyalar.json`
- Build output directory: `site`

`data/kampanyalar.json` her güncellendiğinde (günlük tarama main'e push ettiğinde) site kendiliğinden yeniden yayınlanır.
Filtreler adres çubuğunda saklanır; ör. `/#ag=Trugo` veya `/#banka=garanti` linkleri paylaşılabilir.

## Yedek kopya: GitHub Pages
https://mehmetacan.github.io/wattkac/kampanyalar/ adresindeki kopya (`docs/kampanyalar/`) elle güncellenmez.
`site/` veya `data/kampanyalar.json` main'e her push edildiğinde `.github/workflows/pages-kopya.yml` kopyayı
kendisi eşitler (`tools/pages_kopya.sh`).

## Şarj fiyatları (tarifeler.json)
`site/tarifeler.json` ağların resmi sayfalarındaki liste fiyatlarını tutar (TL/kWh, konuma göre min-max aralığı).
Doğrulanamayan ağlar `null` kalır. Günlük tarama her ağın `kaynak` sayfasını açıp fiyatı ve `kontrol` tarihini günceller
(kurallar: depo kökündeki `CLAUDE.md` → "Günlük kontrol").

## Veri denetimi
`python3 tools/veri_kontrol.py` kampanya ve fiyat verisini denetler (bozuk alan, derleme sitesi bağlantısı, süresi dolmuş
kampanya, 7 günden eski fiyat kontrolü, aksayan günlük tarama). `.github/workflows/veri-kontrol.yml` bunu veri değişince
ve her gün 09:10'da çalıştırır.

## İstasyon verisi (istasyonlar.json)
`.github/workflows/istasyonlar.yml` her gün 05:17'de şu kaynakları çekip `tools/istasyon_birlestir.py` ile `site/istasyonlar.json` üretir:
- **EPDK açık servisi** (`tools/epdk_cek.py` → `data/epdk/epdk_api.json`): lisanslı tüm halka açık istasyonlar; kesin koordinat,
  soket türü ve gücü. Günde tek istek atılır (servisin kotası dar). Fiyat ve anlık durum içermez.
- **Ağların resmi haritaları** (`tools/ag_istasyonlari.py`): ZES, Trugo, Ovolt, WAT, VoltUp, RST Charge Point, BIG Station, CV Charging, Acropol Şarj. Bu ağlarda resmi liste kullanılır; eksik güç/soket
  bilgisi EPDK kaydından tamamlanır.
- **VoltUp** (`tools/voltup_fiyat.mjs` → `data/aglar/voltup_fiyat.json`, ardından `ag_istasyonlari.py voltup` → `data/aglar/voltup.json`):
  voltup.com.tr'deki istasyon bazlı fiyat listesi (aktif lokasyonlar, AC/DC fiyatı). Liste bir Blazor sayfası olduğundan Node + Playwright
  ile günde bir kez açılır; okunamazsa önceki dosya kullanılır. Konum ve soketler aynı adlı EPDK kaydından (bulunamazsa sitedeki harita
  işaretçisinden) alınır; fiyat her istasyonun `pr` alanına yazılır. Yalnızca VoltUp'ı yenilemek için:
  `node tools/voltup_fiyat.mjs && python3 tools/ag_istasyonlari.py voltup && python3 tools/istasyon_birlestir.py site/istasyonlar.json`.
- **RST Charge Point** (`ag_istasyonlari.py rst` → `data/aglar/rst.json`): rstchargepoint.com ana sayfasındaki haritanın istasyon
  dizisi (ondalık ya da derece-dakika-saniye koordinat). Soketler konum/ad/ilçe eşleşmesiyle EPDK kaydından alınır; listedeki konum
  eşleşen EPDK kaydından 1 km'den uzaksa EPDK konumu kullanılır (listede kopyalanmış koordinatlar görüldü). Listedeki `durum`
  (arizali → `pasif`, bakimda → `bakim`) ağın elle güncellediği alandır, canlı durum değildir. Resmi listede olmayan EPDK kayıtları
  gösterilmez. Fiyat tüm istasyonlarda tek tarife (`tarifeler.json`).
- **BIG Station** (eski adı Windmark, işletmeci BSX Enerji; `ag_istasyonlari.py bigstation` → `data/aglar/bigstation.json`): veri, Big Station'ın
  kendi sistemi üzerine kurulmuş üçüncü taraf salt okunur bir servisten (`bsx-reverse.ee-w.workers.dev`, yalnızca `GET /api/stations`,
  giriş yok) günde bir kez alınır. Yalnızca halka açık istasyonlar ve kişisel olmayan alanlar (ad, şehir, konum, AC/DC, güç, fiyat)
  tutulur; konut sitesi / ofis / test cihazları ve konumu girilmemiş (0/0) cihazlar atlanır, aynı yerdeki cihazlar tek istasyonda
  toplanır, fiyat her istasyonun `pr` alanına yazılır. Listede karşılığı (300 m içinde) olmayan EPDK "windmark" kayıtları EPDK'dan gösterilir.
  Her istasyonun cihaz kimlikleri `cih` alanında tutulur (ör. `["95","96"]`). **Anlık durum:** biri BIG Station detayını açınca site
  `GET /api/durum/bigstation?c=95,96` ister (yoklama yok, detay başına bir istek). Worker aynı servisin listesini okur, her cihazı hemen
  `bos` / `sarj` / `bilinmiyor` durumuna indirger (diğer alanlar saklanmaz) ve Cloudflare Cache API'de 60 sn tutar; böylece kullanıcı
  sayısından bağımsız olarak konum başına dakikada en çok bir yenileme (≈4 istek) yapılır. Bağlı olmayan (offline) cihazın durumu bilinmiyor sayılır.
- **Acropol Şarj** (işletmeci Greenleaf Yenilenebilir Enerji; `ag_istasyonlari.py acropol` → `data/aglar/acropol.json`): ağın kendi
  haritasının (acropolsarj.com/evsarjharitasi.aspx) kullandığı, giriş gerektirmeyen tek liste (`getAllAndFilteredStations`; tüm
  istasyonlar, üniteler ve soketler tek istekte). Ad, konum, adres, soket türü/gücü ve soket kimlikleri (`cih`) tutulur; konut sitesi,
  yayında olmayan ve test istasyonları atlanır, ev tipi priz (scooter çıkışı) soket sayılmaz. Resmi listede olmayan EPDK "ACROPOL"
  kayıtları gösterilmez. Fiyat tek tarife (`tarifeler.json`, acropolsarj.com ana sayfasındaki tablo). **Anlık durum:** detay açılınca
  `GET /api/durum/acropol?c=59,60`; worker aynı listeyi tek istekle okur, her soketi hemen `bos` (Available) / `sarj` (Preparing,
  Charging, SuspendedEV/EVSE, Finishing) / `bilinmiyor` (Closed, Faulted vb.) durumuna indirger ve 60 sn önbellekte tutar.
- **OpenStreetMap ve Open Charge Map**: yalnızca EPDK'da karşılığı olmayan istasyonlar eklenir; EPDK kayıtlarına saat/web bilgisi katar.

EPDK servisinden hiç veri alınamadıysa eski yönteme (CSV listesi + adresten konum arama) düşülür.

## Uygulama olarak (PWA)
`manifest.webmanifest`, `icons/` ve `sw.js` sitenin telefona "ana ekrana ekle" ile uygulama gibi kurulmasını sağlar.
`sw.js` sayfayı ve veri dosyalarını önbelleğe alır (bağlantı yoksa son görülen veri açılır). `sw.js` içinde
kabuk dosyaları değişirse `SURUM` değerini artır.
