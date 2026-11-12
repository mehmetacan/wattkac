# WattKaç tasarım sistemi (v3 · koyu tema)

Arayüz, [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) veri setindeki "EV/Charging Ecosystem" ve
"harita merkezli uygulama" önerilerine göre kuruldu. Belirteçler `site/index.html` içindeki `:root` bloğunda tanımlıdır; yeni bileşen
yazarken sabit renk yerine bu belirteçler kullanılır. **Tüm yüzey, çerçeve ve metin renkleri belirteçten okunur**; CSS'te, HTML `style="…"`
içinde ya da JS şablonlarında `#fff`, açık gri gibi sabit renk yazılmaz. Sabit renk yalnızca harita içeriğinde kalır (marka renkli işaretçiler,
`--map-ink` / `--map-halo`, konum noktası), çünkü onlar temadan bağımsız olarak açık harita döşemelerinin üstünde durur.

## Yön
- **Stil:** sade, düz (Minimalism / Flat). Harita ve marka renkli işaretçiler öne çıksın diye arayüz çerçevesi nötrdür.
- **Tek tema:** bütün uygulama (üst çubuk, alt çubuk, alt pencere, kampanya / profil / geri bildirim sayfaları, çekmeceler, harita denetimleri)
  tek koyu lacivert temadadır; markanın Instagram görselleriyle (lacivert zemin, sarı şimşek) aynı aile. Harita döşemelerine filtre uygulanmaz.
- **Açık tema yedeği:** `:root[data-theme="light"]` bloğu v2'nin açık değerlerini eksiksiz tutar. Arayüzde düğmesi yoktur;
  `<html data-theme="light">` yazmak tüm uygulamayı açık temaya döndürür. Yeni belirteç eklenirse iki bloğa da yazılır.
- **Kaçınılacaklar (veri setindeki uyarı):** kötü harita deneyimi ve gizli maliyet. Fiyat ve indirim her zaman açık yazılır.

## Renk
Değerler koyu temanındır (varsayılan). Açık tema karşılıkları `:root[data-theme="light"]` içindedir.

| Belirteç | Koyu değer | Kullanım |
|---|---|---|
| `--bg` | `#0A1020` | Sayfa zemini |
| `--card` | `#111A2E` | Yüzey: kart, bölüm, alt pencere, çekmece, üst/alt çubuk, harita iletisi |
| `--card2` | `#1A2640` | İç / yükseltilmiş yüzey: hap etiketler, istasyon çipleri, metin alanları |
| `--ctl` | `#18233B` | Denetim zemini: düğme, çip, arama, açılır liste |
| `--pop` | `#1B2742` | Öne çıkan yüzen kutu (ana ekrana ekle şeridi) |
| `--bar` | `rgba(17,26,46,.94)` | Üst çubuk (bulanıklaştırmalı) |
| `--line` / `--line2` | `#263556` / `#5B72A0` | Ayırıcı ve kart çerçevesi / denetim çerçevesi (≥3:1) |
| `--grip` | `#4A5F8A` | Alt pencere tutamacı, adım noktaları |
| `--scrim` | `rgba(2,6,16,.66)` | Çekmece arka örtüsü |
| `--txt` / `--txt2` / `--ink` | `#F4F6FB` / `#D5DCEB` / `#FFFFFF` | Metin / ikincil gövde metni / güçlü metin (büyük sayılar). `--ink` yalnızca metin rengidir, zemin olarak kullanılmaz |
| `--mut` / `--ico` | `#9FB0D0` / `#8EA0C4` | İkincil metin / pasif simge (alt çubuk) |
| `--pri` | `#22D3EE` | Ana eylem düğmesi, seçili çip, etkin sekme, bağlantı, odak halkası |
| `--on-pri` | `#06202A` | Dolu `--pri` zemin üstündeki yazı ve simge (beyaz değil: camgöbeği üstünde kontrast için koyu) |
| `--pri-strong` / `--pri-soft` / `--pri-line` | `#67E8F9` / `#0B3340` / `#1E7A8C` | Basılı durum / koyu camgöbeği zemin (etkin sekme hapı, "Resmi sayfa") / çerçeve |
| `--g` / `--gbg` / `--gline` | `#34D399` / `#0B2E24` / `#1C6B4E` | Şarj ağı indirimi, "kontrol edildi", indirimli fiyat: yazı / zemin / çerçeve |
| `--g-fill` / `--on-g` | `#34D399` / `#052E1C` | Dolu yeşil zemin (seçili ağ çipi, sayaç rozeti) ve üstündeki yazı |
| `--amber-bg` / `--amber-fg` / `--amber-line` | `#3A2A06` / `#FCD34D` / `#6B4E0B` | Banka kartı kampanyası, "Doğrulanıyor", DC etiketi, Shell kutusu |
| `--blue-bg` / `--blue-fg` | `#14254A` / `#93C5FD` | AC etiketi |
| `--r` / `--rbg` / `--rline` | `#F87171` / `#3A1219` / `#7F1D1D` | Hata, pasif istasyon, son günler |
| `--y` / `--brand-y` | `#FFC800` | Marka şimşeği ve "Kaç" yazısı (düğme rengi olarak kullanılmaz) |
| `--glass` / `--glass-h` / `--glass-line` / `--on-glass` | `rgba(17,26,46,.88)` / `.97` / `rgba(159,176,208,.22)` / `#fff` | Harita üstü cam denetimler: `--card` ile aynı tondan, ince açık kenar |
| `--map-bg` | `#1B2438` | Döşemeler yüklenirken harita zemini |
| `--map-ink` / `--map-halo` | `#0F172A` / `#fff` | Küme işaretçisi ve seçili işaretçi (her iki temada aynı; açık harita üstünde okunur) |
| `--sh-1..3`, `--sh-pop` | koyu gölgeler | Kart / harita denetimi / alt pencere / yüzen kutu |

Anlamlar her yerde aynı: yeşil = şarj ağı indirimi, kehribar/sarı = banka kartı, kırmızı = hata / son günler, camgöbeği = eylem / seçili.
Metin kontrastı yüzeyinde en az 4,5:1 (`--mut` dahil); simge ve denetim çerçevelerinde en az 3:1. Durum renkleri koyu temada açık pastel zemin
değil, koyu tonlu zemin + açık tonlu yazıdır. `color-scheme: dark` sayesinde açılır liste, onay kutusu ve kaydırma çubukları da koyudur.

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
  Alt çubuk, yardım, kampanya kartı türü, çipler, etiketler, zil, kilit, geri bildirim, kapat (✕ yerine `c-x`) ve geri (← yerine `c-geri`) bunlardır.
- **Harita üstü denetimler (`s-*`):** aynı biçimlerin dolu (solid) hâli. Hepsi tek bileşen: `.mbtn`, 46×46, `--r-md` köşe,
  koyu yarı saydam cam zemin (`--glass`, sayfa yüzeyi `--card` ile aynı ton, bulanıklaştırma ve ince `--glass-line` kenarıyla), 22 px beyaz simge.
  Beyaz kutu ve düğme üstü yazı yok; ad `title` / `aria-label` içinde. Seçili / etkin: düz `--pri` zemin + `--on-pri` (koyu) simge
  (`aria-pressed=true`, filtre düğmesinde `.on`). Leaflet atıf ve yakınlaştırma denetimleri de aynı camdır.
- **Tek palet:** denetimlerde simgeye özel renk kullanılmaz. Yeşil % ve sarı kart yalnızca haritadaki işaretçi rozetlerinde,
  kampanya kartı türü kutucuğunda (`.ico`) ve etiketlerde durum rengi olarak kalır.
- **Anlam her yerde aynı:** kart = banka kartı kampanyası, % = şarj ağının kendi indirimi, yıldız = bana uyan, huni = filtre,
  ok = konumum. AC = Type 2 fiş, DC = CCS fiş, çok hızlı DC = CCS + şimşek.
- Yapısal simge olarak emoji ya da yazı tipinde olmayan karakter (✕, ←, ✓) kullanılmaz; yazı tipi her yerde `var(--font)`.
