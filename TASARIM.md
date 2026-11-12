# WattKaç tasarım sistemi (v4 · açık gri tema)

Arayüz, [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) veri setindeki "EV/Charging Ecosystem" ve
"harita merkezli uygulama" önerilerine göre kuruldu. Belirteçler `site/index.html` içindeki `:root` bloğunda tanımlıdır; yeni bileşen
yazarken sabit renk yerine bu belirteçler kullanılır. **Tüm yüzey, çerçeve ve metin renkleri belirteçten okunur**; CSS'te, HTML `style="…"`
içinde ya da JS şablonlarında `#fff`, açık gri gibi sabit renk yazılmaz. Sabit renk yalnızca harita içeriğinde kalır (marka renkli işaretçiler,
`--map-ink` / `--map-halo`, konum noktası), çünkü onlar temadan bağımsız olarak açık harita döşemelerinin üstünde durur.

## Yön
- **Stil:** sade, düz (Minimalism / Flat), modern. Harita ve marka renkli işaretçiler öne çıksın diye arayüz çerçevesi nötrdür.
- **Tek tema:** bütün uygulama (üst çubuk, alt çubuk, alt pencere, kampanya / profil / geri bildirim sayfaları, çekmeceler, harita denetimleri)
  tek açık temadadır: düz beyaz değil, griye çalan serin bir zemin (`--bg`) ve onun üstünde kırık beyaz gri yüzeyler (`--card`).
  **Hiçbir yüzey saf `#FFFFFF` değildir.** Harita denetimleri de aynı yüzey renginden camdır; sayfadan ayrı bir "beyaz kutu" gibi durmaz.
  Harita döşemelerine filtre uygulanmaz.
- **Koyu tema yedeği:** `:root[data-theme="dark"]` bloğu v3'ün koyu lacivert değerlerini eksiksiz tutar. Arayüzde düğmesi yoktur;
  `<html data-theme="dark">` yazmak tüm uygulamayı koyu temaya döndürür. Yeni belirteç eklenirse iki bloğa da yazılır.
- **Az yazı:** istasyon detayı ve listesinde cümle yerine değer gösterilir. İndirimli fiyat "üstü çizili liste fiyatı + yeşil indirimli fiyat"
  olarak yazılır, koşulu (i) bilgi düğmesindeki tek cümlede durur. Kampanya değeri kısa yazılır ("%20", "75 TL"); ayrıntı açılır kısımdadır.
- **Kaçınılacaklar (veri setindeki uyarı):** kötü harita deneyimi ve gizli maliyet. Fiyat ve indirim her zaman açık yazılır.

## Renk
Değerler açık temanındır (varsayılan). Koyu tema karşılıkları `:root[data-theme="dark"]` içindedir.

| Belirteç | Açık değer | Kullanım |
|---|---|---|
| `--bg` | `#E9EDF2` | Sayfa zemini (serin açık gri) |
| `--card` | `#F5F7FA` | Yüzey: kart, bölüm, alt pencere, çekmece, alt çubuk, harita iletisi, bilgi kutusu |
| `--card2` | `#ECEFF4` | İç / yükseltilmiş yüzey: hap etiketler, istasyon çipleri, metin alanları, açık satır |
| `--ctl` | `#EEF1F5` | Denetim zemini: düğme, çip, arama, açılır liste |
| `--pop` | `#F5F7FA` | Öne çıkan yüzen kutu (ana ekrana ekle şeridi, bilgi kutusu); `--sh-pop` gölgesiyle ayrılır |
| `--bar` | `rgba(245,247,250,.92)` | Üst çubuk (bulanıklaştırmalı) |
| `--line` / `--line2` | `#D5DCE6` / `#77869A` | Ayırıcı ve kart çerçevesi / denetim çerçevesi (≥3:1) |
| `--grip` | `#B6C0CE` | Alt pencere tutamacı, adım noktaları |
| `--scrim` | `rgba(15,23,42,.42)` | Çekmece arka örtüsü |
| `--txt` / `--txt2` / `--ink` | `#0F172A` / `#334155` / `#0F172A` | Metin / ikincil gövde metni / güçlü metin (büyük sayılar). `--ink` yalnızca metin rengidir |
| `--mut` / `--ico` | `#475569` / `#64748B` | İkincil metin / pasif simge (alt çubuk) |
| `--pri` | `#0E7490` | Ana eylem düğmesi, seçili çip, etkin sekme, bağlantı, odak halkası |
| `--on-pri` | `#FFFFFF` | Dolu `--pri` zemin üstündeki yazı ve simge (yalnızca yazı rengi) |
| `--pri-strong` / `--pri-soft` / `--pri-line` | `#155E75` / `#DDEFF3` / `#9FCCD7` | Basılı durum / soluk camgöbeği zemin (etkin sekme hapı, "Resmi sayfa") / çerçeve |
| `--g` / `--gbg` / `--gline` | `#047857` / `#DDEFE6` / `#A8D5C0` | Şarj ağı indirimi, "kontrol edildi", indirimli fiyat: yazı / zemin / çerçeve |
| `--g-fill` / `--on-g` | `#047857` / `#FFFFFF` | Dolu yeşil zemin (seçili ağ çipi, sayaç rozeti) ve üstündeki yazı |
| `--amber-bg` / `--amber-fg` / `--amber-line` | `#F4EACD` / `#7C4A03` / `#E2CC8E` | Banka kartı kampanyası, "Doğrulanıyor", DC etiketi, Shell kutusu |
| `--blue-bg` / `--blue-fg` | `#DEE7F4` / `#1E40AF` | AC etiketi |
| `--r` / `--rbg` / `--rline` | `#B91C1C` / `#F6E4E4` / `#E6B9B9` | Hata, pasif istasyon, son günler |
| `--y` / `--brand-y` | `#FFC800` / `#E0A100` | Marka şimşeği ve "Kaç" yazısı (düğme rengi olarak kullanılmaz) |
| `--glass` / `--glass-h` / `--glass-line` / `--on-glass` | `rgba(245,247,250,.9)` / `.98` / `rgba(15,23,42,.12)` / `#0F172A` | Harita üstü cam denetimler: `--card` ile aynı tondan, ince kenar, koyu simge |
| `--map-bg` | `#E3E6E9` | Döşemeler yüklenirken harita zemini |
| `--map-ink` / `--map-halo` | `#0F172A` / `#fff` | Küme işaretçisi ve seçili işaretçi (her iki temada aynı; açık harita üstünde okunur) |
| `--sh-1..3`, `--sh-pop`, `--sh-ctl` | yumuşak gölgeler | Kart / harita iletisi / alt pencere / yüzen kutu / harita denetimi |

Anlamlar her yerde aynı: yeşil = şarj ağı indirimi, kehribar/sarı = banka kartı, kırmızı = hata / son günler, camgöbeği = eylem / seçili.
Metin kontrastı yüzeyinde en az 4,5:1 (`--mut` dahil); simge ve denetim çerçevelerinde en az 3:1. Durum zeminleri parlak pastel değil,
gri yüzeylerle uyumlu hafif kısık açık tonlardır. `color-scheme: light`; koyu temada `color-scheme: dark`.

## Yazı
- **Plus Jakarta Sans** (değişken ağırlık, `site/fonts/` içinde barınır; SIL OFL). Ağırlıklar: 500 metin, 600–700 vurgu, 800 başlık ve sayılar.
- Başlıklarda harf aralığı −0.02/−0.03em. Haritadaki işaretçi yazıları tek boy (11,5px / 800).

## Ölçü
- Aralıklar 4/8 ritminde. Köşe yarıçapları: `--r-sm` 10, `--r-md` 14, `--r-lg` 20, `--r-xl` 28.
- Gölgeler: `--sh-1` kart, `--sh-2` harita üstü denetim, `--sh-3` alt pencere.
- Dokunma hedefi en az 44×44 px.

## Etkileşim
- Basınca yerleşimi kaydırmayan hafif küçülme (`scale(.96)`), 120–150 ms geçiş.
- Klavye odağı her zaman görünür (2,5 px `--pri` halka).
- `prefers-reduced-motion` açıkken geçiş ve animasyon yok.

## Simgeler
Tüm simgeler `site/index.html` başındaki `#spr` simge kümesinden `<use href="#…">` ile gelir; yeni simge eklerken oraya, aynı kurallarla eklenir.
- **Tek çizim alanı:** 24×24 viewBox, simge alanı yaklaşık 2–22 arası; köşe ve uçlar yuvarlak.
- **Sayfa içi (`c-*`):** çizgisel, 2 px kalınlık, `stroke-linecap/linejoin: round`, dolgu yok. Rengi bulunduğu metnin rengidir (`currentColor`).
  Alt çubuk, yardım, kampanya kartı türü, çipler, etiketler, zil, kilit, geri bildirim, bilgi (`c-bilgi`, indirim koşulu), kapat (✕ yerine `c-x`) ve geri (← yerine `c-geri`) bunlardır.
- **Harita üstü denetimler (`s-*`):** aynı biçimlerin dolu (solid) hâli. Hepsi tek bileşen: `.mbtn`, 46×46, `--r-md` köşe,
  yarı saydam cam zemin (`--glass`: alt pencere ve alt çubukla aynı `--card` tonu, bulanıklaştırma, ince `--glass-line` kenar ve `--sh-ctl` gölge),
  22 px koyu (`--on-glass`) simge. Saf beyaz kutu ve düğme üstü yazı yok; ad `title` / `aria-label` içinde. Seçili / etkin: düz `--pri` zemin + `--on-pri` (beyaz) simge
  (`aria-pressed=true`, filtre düğmesinde `.on`). Leaflet atıf ve yakınlaştırma denetimleri de aynı camdır.
- **Tek palet:** denetimlerde simgeye özel renk kullanılmaz. Yeşil % ve sarı kart yalnızca haritadaki işaretçi rozetlerinde,
  kampanya kartı türü kutucuğunda (`.ico`) ve etiketlerde durum rengi olarak kalır.
- **Anlam her yerde aynı:** kart = banka kartı kampanyası, % = şarj ağının kendi indirimi, yıldız = bana uyan, huni = filtre,
  ok = konumum. AC = Type 2 fiş, DC = CCS fiş, çok hızlı DC = CCS + şimşek.
- Yapısal simge olarak emoji ya da yazı tipinde olmayan karakter (✕, ←, ✓) kullanılmaz; yazı tipi her yerde `var(--font)`.
