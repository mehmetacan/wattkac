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

## Güvenlik
- `onaylar/` klasörüne yazılmaz.
- Paylaşım yapılmaz ve `YAYIN_AKTIF` değiştirilmez. Onay ve paylaşım yalnızca kullanıcının panelinden olur.
- Anahtar veya token sohbete yazılmaz, istenmez.
- Kişisel bilgi içeren ekran görüntüleri (ad, telefon, plaka, adres, kart) kullanılmaz.
