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
`tools/istasyon_cek.py` Türkiye'deki tüm şarj istasyonlarını OpenStreetMap'ten çeker ve `site/istasyonlar.json` dosyasına yazar.
`.github/workflows/istasyonlar.yml` bunu her gün 05:17'de çalıştırıp değişiklik varsa commit eder. Haritadaki arama önce bu dosyayı kullanır; dosya yoksa canlı Overpass'a düşer.

## Uygulama olarak (PWA)
`manifest.webmanifest`, `icons/` ve `sw.js` sitenin telefona "ana ekrana ekle" ile uygulama gibi kurulmasını sağlar.
`sw.js` sayfayı ve veri dosyalarını önbelleğe alır (bağlantı yoksa son görülen veri açılır). `sw.js` içinde
kabuk dosyaları değişirse `SURUM` değerini artır.
