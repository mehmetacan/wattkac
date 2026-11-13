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
- **Ağların resmi haritaları** (`tools/ag_istasyonlari.py`): ZES, Trugo, Ovolt, WAT, VoltUp. Bu ağlarda resmi liste kullanılır; eksik güç/soket
  bilgisi EPDK kaydından tamamlanır.
- **VoltUp** (`tools/voltup_fiyat.mjs` → `data/aglar/voltup_fiyat.json`, ardından `ag_istasyonlari.py voltup` → `data/aglar/voltup.json`):
  voltup.com.tr'deki istasyon bazlı fiyat listesi (aktif lokasyonlar, AC/DC fiyatı). Liste bir Blazor sayfası olduğundan Node + Playwright
  ile günde bir kez açılır; okunamazsa önceki dosya kullanılır. Konum ve soketler aynı adlı EPDK kaydından (bulunamazsa sitedeki harita
  işaretçisinden) alınır; fiyat her istasyonun `pr` alanına yazılır. Yalnızca VoltUp'ı yenilemek için:
  `node tools/voltup_fiyat.mjs && python3 tools/ag_istasyonlari.py voltup && python3 tools/istasyon_birlestir.py site/istasyonlar.json`.
- **OpenStreetMap ve Open Charge Map**: yalnızca EPDK'da karşılığı olmayan istasyonlar eklenir; EPDK kayıtlarına saat/web bilgisi katar.

EPDK servisinden hiç veri alınamadıysa eski yönteme (CSV listesi + adresten konum arama) düşülür.

## Uygulama olarak (PWA)
`manifest.webmanifest`, `icons/` ve `sw.js` sitenin telefona "ana ekrana ekle" ile uygulama gibi kurulmasını sağlar.
`sw.js` sayfayı ve veri dosyalarını önbelleğe alır (bağlantı yoksa son görülen veri açılır). `sw.js` içinde
kabuk dosyaları değişirse `SURUM` değerini artır.
