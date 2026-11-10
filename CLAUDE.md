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
- **Fiyatlar:** `site/tarifeler.json` içindeki her ağın `kaynak` sayfası açılır.
  - Fiyat okunabildiyse `ac`/`dc` (min–max, TL/kWh, KDV dahil) ve `kontrol` tarihi güncellenir; sayfa geçerlilik tarihi veriyorsa `gecerlilik` yazılır.
  - Sayfa açılamadıysa fiyata ve `kontrol` tarihine dokunulmaz; tahminle fiyat yazılmaz. Fiyat yalnızca ağın kendi sayfasından alınır.
  - En az bir fiyat değiştiyse dosyanın üstündeki `guncelleme` bugüne çekilir.
- **Tarih alanları:** `data/kampanyalar.json` → `son_kontrol` her taramada bugün yapılır (site "Bugün kontrol edildi" yazar). `guncelleme` yalnızca kampanya verisi gerçekten değiştiğinde değişir.
- **Denetim:** Commit'ten önce `python3 tools/veri_kontrol.py` çalıştırılır; hata varsa düzeltilmeden push edilmez. Aynı denetim GitHub Actions'ta her gün 09:10'da çalışır ve tarama 2 günden fazla aksarsa kırmızı olur.
- `docs/kampanyalar/` elle kopyalanmaz; `pages-kopya.yml` iş akışı main'e her push'ta kendisi eşitler.

## Açıklama metni
- Her gönderi ve Reels açıklamasında hashtag'lerden önce şu satır bulunur: "ℹ️ Reklam veya işbirliği değildir. Kampanyaları bağımsız olarak, kurumların resmi kaynaklarından derliyoruz."

## Güvenlik
- `onaylar/` klasörüne yazılmaz.
- Paylaşım yapılmaz ve `YAYIN_AKTIF` değiştirilmez. Onay ve paylaşım yalnızca kullanıcının panelinden olur.
- Anahtar veya token sohbete yazılmaz, istenmez.
- Kişisel bilgi içeren ekran görüntüleri (ad, telefon, plaka, adres, kart) kullanılmaz.
