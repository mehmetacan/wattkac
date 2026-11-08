# WattKaç kampanya sitesi (Cloudflare Pages)

Cloudflare Pages ayarları:
- Framework preset: None
- Build command: `cp data/kampanyalar.json site/kampanyalar.json`
- Build output directory: `site`

`data/kampanyalar.json` her güncellendiğinde (günlük tarama main'e push ettiğinde) site kendiliğinden yeniden yayınlanır.
Filtreler adres çubuğunda saklanır; ör. `/#ag=Trugo` veya `/#banka=garanti` linkleri paylaşılabilir.

## Şu anki yayın: GitHub Pages
Türkiye'de pages.dev/workers.dev erişim sorunları nedeniyle site şimdilik
https://mehmetacan.github.io/wattkac/kampanyalar/ adresinde yayınlanır.
`site/` veya `data/kampanyalar.json` değişince şu kopyalama yapılmalı (günlük görev bunu yapar):
    cp site/index.html site/logo.png docs/kampanyalar/ && cp data/kampanyalar.json docs/kampanyalar/

## Şarj fiyatları (tarifeler.json)
`site/tarifeler.json` ağların resmi sayfalarındaki liste fiyatlarını tutar (TL/kWh, konuma göre min-max aralığı).
Doğrulanamayan ağlar `null` kalır. Kopyalama komutuna `site/tarifeler.json` da eklenmeli:
    cp site/index.html site/logo.png site/tarifeler.json docs/kampanyalar/ && cp data/kampanyalar.json docs/kampanyalar/

## İstasyon verisi (istasyonlar.json)
`tools/istasyon_cek.py` Türkiye'deki tüm şarj istasyonlarını OpenStreetMap'ten çeker ve `site/istasyonlar.json` dosyasına yazar.
`.github/workflows/istasyonlar.yml` bunu her gün 05:17'de çalıştırıp değişiklik varsa commit eder. Haritadaki arama önce bu dosyayı kullanır; dosya yoksa canlı Overpass'a düşer.

## Uygulama olarak (PWA)
`manifest.webmanifest`, `icons/` ve `sw.js` sitenin telefona "ana ekrana ekle" ile uygulama gibi kurulmasını sağlar.
`sw.js` sayfayı ve veri dosyalarını önbelleğe alır (bağlantı yoksa son görülen veri açılır). `sw.js` içinde
kabuk dosyaları değişirse `SURUM` değerini artır.
GitHub Pages kopyası için: `cp -r site/index.html site/manifest.webmanifest site/sw.js site/icons docs/kampanyalar/`
