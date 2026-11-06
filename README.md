# WattKaç Instagram otomasyonu

Elektrikli araç şarj ağları ve banka kartı kampanyalarını toplayıp Instagram'da
karusel post ve hikaye olarak paylaşan yarı otomatik sistem.

## Nasıl çalışır

1. **Kampanya taraması (Claude, her sabah):** Kampanyalar taranır, `data/kampanyalar.json`
   güncellenir, `scripts/render.py` görselleri üretir, `scripts/build_queue.py` yeni postları
   `queue/*.json` dosyasına **onay bekliyor** olarak ekler.
2. **Onay (siz):** **Onay paneli** (https://mehmetacan.github.io/wattkac/) her postu ayrı kart olarak
   gösterir: görseller, açıklama, kaynaklar. Her birini tek tek **Onayla** / **Reddet**;
   açıklamayı, saati ve hikaye tercihini değiştirebilirsiniz. Onay `onaylar/<grup>.json` olarak kaydedilir.
3. **Paylaşım (GitHub Actions, 15 dakikada bir):** `yayinla.yml` yalnızca **onaylanmış** ve zamanı
   gelen post ve hikayeleri Instagram API ile paylaşır, durumu `paylasildi` yapar.

Takvim: günde 3 post (09:30, 13:00, 19:30) ve her postun 1 saat sonrasında o kurumun
hikayesi. Bitiş tarihi geçmiş kampanya kuyruğa alınmaz, 24 saatten fazla geciken paylaşım atlanır.

## Bir kerelik kurulum

### 1. Instagram hesabını profesyonel yap
Instagram › Ayarlar › Hesap türü ve araçlar › **Profesyonel hesaba geç** (İşletme veya İçerik Üreticisi).

### 2. Meta uygulaması ve token
1. <https://developers.facebook.com/apps> › **Uygulama oluştur**.
2. Kullanım amacı olarak **Instagram API** (Instagram'da içerik yönetimi) seçin, tür: İşletme.
3. Uygulama panelinde **Instagram › API setup with Instagram login** bölümüne girin.
4. **Generate access tokens** altında **Add account** ile `wattkac` hesabıyla giriş yapın ve
   `instagram_business_basic` ile `instagram_business_content_publish` izinlerini onaylayın.
   - Hesap eklenemezse: **Uygulama rolleri › Roller › Instagram test kullanıcıları**'na
     `wattkac` ekleyin, daveti Instagram'da *Ayarlar › Uygulamalar ve web siteleri* altından kabul edin.
5. Ekranda görünen **Instagram kullanıcı ID**'sini ve **access token**'ı kopyalayın.
   Token'ı kimseyle (Claude dahil) sohbette paylaşmayın, doğrudan 3. adımdaki secret'a yapıştırın.

### 3. GitHub ayarları (Settings › Secrets and variables › Actions)
| Tür | Ad | Değer |
|---|---|---|
| Secret | `IG_USER_ID` | Instagram kullanıcı ID |
| Secret | `IG_ACCESS_TOKEN` | Access token |
| Secret | `GH_PAT` | Fine-grained token: yalnızca bu depo, *Secrets: Read and write* |
| Variable | `YAYIN_AKTIF` | `true` (paylaşımı durdurmak için `false` yapın) |

### 4. Deneme
Actions › **Instagram'a yayınla** › *Run workflow* (deneme modu açık) — hiçbir şey paylaşmadan
neyin paylaşılacağını listeler. Sorun yoksa `YAYIN_AKTIF=true` ile gerçek paylaşım başlar.

## Sınırlar
- Instagram API: 24 saatte en fazla 50 API paylaşımı güvenli kabul edilir (karusel = 1 paylaşım),
  karuselde en fazla 10 kare, yalnızca JPEG. Sistem her çalışmada en fazla 3 paylaşım yapar
  ve kalan kotayı kontrol eder.
- API ile hikayeye link çıkartması eklenemez; profil sabitleme de elle yapılır
  (özet postlarını profilde sabitleyin).

## Elle komutlar
```bash
python scripts/render.py --etiket 2026-11                          # görselleri üret
python scripts/build_queue.py --etiket 2026-11 --baslangic 2026-11-07  # takvimi kur
DRY_RUN=1 GITHUB_REPOSITORY=kullanici/wattkac python scripts/publish.py  # deneme
```
