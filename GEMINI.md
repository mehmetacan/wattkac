# WattKaç: Gemini çalışma talimatı (Instagram kampanya gönderileri)

Bu depo @wattkac Instagram sayfasının kampanya verisini, gönderi görsellerini ve paylaşım kuyruğunu tutar.
Görevin: kampanyaları resmi kaynaklardan güncellemek, gönderi görsellerini ve açıklamalarını **mevcut betiklerle** üretmek ve onay kuyruğuna koymak.
**Paylaşım yapmazsın.** Kullanıcı her gönderiyi web panelinde tek tek onaylar; onaylananları GitHub Actions Instagram'a yükler.

İçerik ve veri kurallarının tamamı `CLAUDE.md` dosyasındadır ve sen de birebir uyarsın:
@./CLAUDE.md

## 1. Düzen (değiştirme, sadece kullan)

```
data/kampanyalar.json   ← tek veri kaynağı (bankalar, istasyonlar, uygulamalar)
        │  python3 scripts/render.py      → media/<etiket>/<post_id>/*.jpg + manifest.json
        │  python3 scripts/build_queue.py → queue/<etiket>.json  (durum: "bekliyor")
        ▼
git push (main)  →  Onay paneli: https://mehmetacan.github.io/wattkac/  (kullanıcı onaylar → onaylar/*.json)
                 →  .github/workflows/yayinla.yml onaylananı zamanı gelince Instagram'a yükler
```

- Görseli **elle tasarlama, yapay zekâ görseli üretme.** Görseller `scripts/render.py` içindeki HTML şablonlarından Chrome ile çekilir; tema, logo ve yazı tipleri orada sabittir.
- Açıklama metnini `scripts/build_queue.py` üretir. Gerekirse kuyruk dosyasındaki `aciklama` alanını düzeltebilirsin, ama yapıyı bozma.
- Yeni bir gönderi türü gerekiyorsa önce kullanıcıya sor; şablonları ve betikleri izinsiz değiştirme.

## 2. Adım adım iş akışı

1. `git pull` ile güncel hâli al.
2. **Kampanyaları kontrol et.** `CLAUDE.md` › "Kaynak" ve "Günlük kontrol" kurallarıyla `data/kampanyalar.json` dosyasını güncelle.
   - Yalnız resmi kaynak (kurumun kendi sitesi, uygulaması, resmi hesabı).
   - Yeni kampanyaya `"eklendi": "YYYY-AA-GG"` yaz.
   - Bitenleri çıkar.
3. `python3 tools/veri_kontrol.py`: hata varsa düzeltmeden devam etme.
4. **Görselleri üret** (yalnız yeni veya değişen gönderiler):
   ```bash
   python3 scripts/render.py --etiket 2026-11-21 --sadece banka_garanti,istasyon_ovolt
   ```
   - Post kimlikleri `banka_<id>`, `istasyon_<id>`, `uygulama_<id>`, `ozet_bankalar`, `ozet_istasyonlar` biçimindedir.
   - `--etiket` o günün tarihi olur (aynı gün ikinci iş için `2026-11-21-b` gibi).
5. **Kuyruğu kur:**
   ```bash
   python3 scripts/build_queue.py --etiket 2026-11-21 --baslangic 2026-11-22 --sadece banka_garanti,istasyon_ovolt
   ```
   Betik dolu saatleri atlar. Günde en fazla **1 karusel + hikayesi** hedefle; Instagram yoğun paylaşımda erişimi düşürüyor.
6. **Kontrol et:**
   - Üretilen her JPEG'i aç; taşan yazı, yanlış tarih ya da yanlış oran olmasın.
   - Kuyruktaki her öğenin `kaynaklar` listesinde en az bir `"tur": "resmi"` bağlantı olsun.
   - Açıklamada hashtag'lerden önce "reklam değildir" satırı bulunsun.
7. **Gönder:**
   ```bash
   git add data/ media/2026-11-21/ queue/2026-11-21.json
   git commit -m "Kampanya gönderileri 2026-11-21: <kısa özet>"
   git push origin main
   ```
8. Kullanıcıya kısa rapor ver: ne eklendi/çıktı, hangi gönderiler panele düştü, hangi kaynağı doğrulayamadın (`"kontrol": true`).

## 3. Asla yapma

- `onaylar/` klasörüne yazma ve onay verme. Onay yalnız kullanıcının panelinden gelir.
- Instagram'a paylaşım yapma, `scripts/publish.py` çalıştırma, `YAYIN_AKTIF` değişkenini değiştirme.
- `paylasildi` durumundaki kuyruk öğelerini silme ya da değiştirme.
- Anahtar ve token isteme, yazdırma, depoya koyma (`IG_ACCESS_TOKEN` vb. yalnız GitHub Secrets'tadır).
- Derleme sitelerini (sarjkampanya, sarjharitasi, hangikredi…) kaynak gösterme.
- Kişisel bilgi içeren ekran görüntüsü kullanma.
- `--force` ile push etme. Çakışma olursa `git pull --rebase` yap; tekrar çakışırsa dur ve kullanıcıya sor.

## 4. Marka ve tema (Instagram görselleri)

Bu tema `scripts/render.py` › `base_css()` içindedir. Sitenin açık gri teması (`TASARIM.md`) ayrıdır; Instagram'da kullanılmaz.

| Öğe | Değer |
|---|---|
| Zemin | Koyu lacivert `#0A1020`, sağ üstte sarı, sol altta yeşil hafif ışık halesi |
| Ana metin | `#F4F6FB` |
| Vurgu (indirim oranı, şimşek, "Kaç") | Sarı `#FFD400` |
| İkincil vurgu (alt başlık, "tümü" etiketi) | Yeşil `#22E3A0` |
| Soluk metin | `#9FB0D0`, `#8394B8` |
| Kart | `rgba(255,255,255,.045)` zemin, `#202C4A` çerçeve, 24px köşe |
| Yazı tipi | Inter (900 başlık/oran, 600–800 gövde) |
| Logo | Sarı şimşek + "Watt" (beyaz) "**Kaç**" (sarı); dosya: `site/logo.png` (yuvarlak profil logosu) |
| Boyutlar | Post 1080×1350 (4:5), hikaye 1080×1920 |

Anlam dili: **sarı** = kampanya/oran, **yeşil** = şarj ağının kendi indirimi / doğrulandı, **kırmızı** = son günler.
Kapakta logo yok, kurum adı büyük yazılır (profilde ızgarada okunsun diye). Banka logosu kullanılmaz, yalnız ad.

## 5. Açıklama metni kuralları

- İlk satırda kurum adı + en güçlü fayda: `⚡ Garanti BBVA: Ovolt'ta 75 TL bonus!`
- Madde madde: oran/tutar, nerede geçerli, katılım yöntemi, son gün.
- Hashtag'lerden hemen önce bu satır yer alır: `ℹ️ Reklam veya işbirliği değildir. Kampanyaları bağımsız olarak, kurumların resmi kaynaklarından derliyoruz.`
- Bu satır yalnız normal gönderide kullanılır. Kullanıcı bir gönderiyi **ücretli reklama** çevirecekse bu satırı çıkar.
- Hesap ya da örnek verirken her satırı tek kartla hesapla, kaynağı olmayan fiyat yazma.

## 6. Kurulum (bir kez)

- Python 3.11+, `pip install pillow`, Google Chrome veya Chromium (`render.py` başsız Chrome ile ekran görüntüsü alır).
- Depoya yazma: kullanıcının kendi GitHub kimliğiyle (`gh auth login`), ya da yalnız bu depoya **Contents: Read and write** izni olan ince ayarlı bir PAT ile.
