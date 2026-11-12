# WattKaç içerik kuralları

Bu depo @wattkac Instagram sayfasının kampanya verisini, görsellerini ve paylaşım kuyruğunu tutar. Günlük kampanya taraması da dahil, bu depoda çalışan her oturum aşağıdaki kurallara uyar.

## Kaynak
- Kampanya bilgisi yalnızca kampanya sahibinin kendi sitesi, uygulaması veya resmi sosyal medya hesabından alınır.
- Derleme siteleri (sarjkampanya, sarjharitasi, sarjevi, hangikredi vb.) yalnızca kampanyayı fark etmek için kullanılır, kaynak olarak gösterilmez.
- Resmi sayfa açılamadıysa teklife `"kontrol": true` eklenir. Panel bunu "RESMİ · KONTROL ET" olarak gösterir.

## Post kuralı (7 Kasım 2026)
- **Banka postu:** Kart kampanyası ve geçerli olduğu istasyonlar (`st` listesi) burada yazılır.
- **Şarj ağı postu:** Yalnızca ağın **kendi** indirimi varsa yapılır (`own` boş değilse).
  - Banka kampanyaları istasyon postunda tekrar edilmez. Kendi indirimi olmayan ağ için post üretilmez; `render.py` bunları otomatik atlar.
- **Birleşik fiyat:** Ağın kendi indirimi bir banka kampanyasıyla birleşebiliyorsa, istasyonun `birlesik` alanına banka kartıyla birlikte net fiyat yazılır.
  - Format: `{"baslik", "satirlar": [[kart, sonuç]], "not"}`.
  - Kesin kWh fiyatı resmi değilse "100 TL'lik şarjda net maliyet" örneği kullanılır.
  - Her satır tek bir kartla hesaplanır.
  - "Başka indirimle birleşmez" yazan kart kampanyaları (ör. Paraf Doğal) birleşik hesaba katılmaz.

## Günlük kontrol (kampanya + fiyat)
Günlük tarama her çalıştığında, değişiklik olmasa bile:
- **Kampanyalar:** `data/kampanyalar.json` içindeki her kampanyanın resmi sayfası yeniden açılır.
  - Süresi dolan kampanya veriden çıkarılır.
  - `"kontrol": true` olanlar yeniden denenir; resmi sayfa açılıp doğrulanırsa `kontrol` alanı silinir. Site bu kampanyaları "Doğrulanıyor" etiketiyle gösterir.
  - Yeni eklenen kampanyaya `"eklendi": "YYYY-AA-GG"` yazılır (site 7 gün "Yeni" etiketi gösterir).
  - Kampanya yalnızca belli marka araçlara özelse `"arac": ["Togg"]`, yalnızca belli illerde geçerliyse `"iller": ["Ankara", "İzmir"]` yazılır (il adları sitedeki il listesindeki yazımla). Bu alanlar profil eşleşmesinde ve bildirimlerde kullanılır; herkese / her yerde geçerli kampanyada yazılmaz.
  - Şarj ağının kendi kampanyasına (`own`) `"herkese"` yazılır: o ağda şarj eden herkese kendiliğinden uygulanıyorsa `true`; kod, üyelik, abonelik, sigorta, yeni üye, doğum günü gibi bir koşul varsa `false` (araca özelse `arac` yazılır, `herkese` yazılmaz). Site yalnızca `herkese: true` olanları haritada yeşil rozet ve indirimli fiyat olarak gösterir.
  - Yalnızca belli günlerde geçerli indirimde (ör. "her ayın son günü") `bas` ve `bit` o günün tarihi olur; site başlangıcı gelmemiş indirimi haritada uygulamaz.
  - `eklendi` tarihi bildirimleri tetikler (aboneye yalnızca abonelikten sonra eklenen kampanya bildirilir); bu yüzden yalnızca gerçekten yeni kampanyada yazılır, mevcut kampanyanın metni düzeltilirken değiştirilmez.
- **İzlenen kaynaklar:** `data/kaynaklar.json` okunur. `arastir` listesindeki konular her taramada resmi kaynakta aranır; doğrulanınca veriye işlenir ve listeden çıkarılır. `sosyal` listesindeki resmi hesaplar ve `kesif` listesindeki hesap/siteler son paylaşımları için kontrol edilir (açılamayan hesap raporda yazılır). Sosyal medyada görülen kampanya, kurumun resmi sayfasında doğrulanmadan eklenmez; resmi hesabın kendi duyurusu tek kaynaksa `"kontrol": true` ile eklenir ve bağlantı o gönderiye gider.
- **Fiyatlar:** `site/tarifeler.json` içindeki her ağın `kaynak` sayfası açılır.
  - Fiyat okunabildiyse `ac`/`dc` (min–max, TL/kWh, KDV dahil) ve `kontrol` tarihi güncellenir; sayfa geçerlilik tarihi veriyorsa `gecerlilik` yazılır.
  - Sayfa açılamadıysa fiyata ve `kontrol` tarihine dokunulmaz; tahminle fiyat yazılmaz. Fiyat yalnızca ağın kendi sayfasından alınır.
  - En az bir fiyat değiştiyse dosyanın üstündeki `guncelleme` bugüne çekilir.
  - `ac`/`dc` değeri `null` olan ağlar henüz doğrulanmamıştır: sayfa açılıp fiyat okunursa doldurulur. Yeni ağ eklerken anahtar, ağın sitede görünen adı olur; EPDK kaydındaki farklı yazımlar `adlar` listesine yazılır.
- **Tarih alanları:** `data/kampanyalar.json` → `son_kontrol` her taramada bugün yapılır (site "Bugün kontrol edildi" yazar). `guncelleme` yalnızca kampanya verisi gerçekten değiştiğinde değişir.
- **Denetim:** Commit'ten önce `python3 tools/veri_kontrol.py` çalıştırılır; hata varsa düzeltilmeden push edilmez. Aynı denetim GitHub Actions'ta her gün 09:10'da çalışır ve tarama 2 günden fazla aksarsa kırmızı olur.
- `docs/kampanyalar/` elle kopyalanmaz; `pages-kopya.yml` iş akışı main'e her push'ta kendisi eşitler.

## Açıklama metni
- Her gönderi ve Reels açıklamasında hashtag'lerden önce şu satır bulunur: "ℹ️ Reklam veya işbirliği değildir. Kampanyaları bağımsız olarak, kurumların resmi kaynaklarından derliyoruz."

## Bildirimler
- Site, profiline uyan yeni kampanyada aboneye web push bildirimi gönderir (`worker/index.js` → "Bildirimler"): kampanya başına bir kez, kişi başına günde en fazla bir, yalnızca doğrulanmış ve abonelikten sonra eklenmiş kampanyalar.
- Bildirim gönderimi tümüyle otomatiktir; tarama oturumu bildirim göndermez, yalnızca veriyi doğru doldurur (`eklendi`, `arac`, `iller`, `kontrol`).

## Güvenlik
- `onaylar/` klasörüne yazılmaz.
- Paylaşım yapılmaz ve `YAYIN_AKTIF` değiştirilmez. Onay ve paylaşım yalnızca kullanıcının panelinden olur.
- Anahtar veya token sohbete yazılmaz, istenmez.
- Kişisel bilgi içeren ekran görüntüleri (ad, telefon, plaka, adres, kart) kullanılmaz.
