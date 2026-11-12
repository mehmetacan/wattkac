# WattKaç tasarım sistemi (v2)

Arayüz, [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) veri setindeki "EV/Charging Ecosystem" ve
"harita merkezli uygulama" önerilerine göre kuruldu. Belirteçler `site/index.html` içindeki `:root` bloğunda tanımlıdır; yeni bileşen
yazarken sabit renk yerine bu belirteçler kullanılır.

## Yön
- **Stil:** sade, düz (Minimalism / Flat). Harita ve marka renkli işaretçiler öne çıksın diye arayüz çerçevesi nötrdür.
- **Kaçınılacaklar (veri setindeki uyarı):** kötü harita deneyimi ve gizli maliyet. Fiyat ve indirim her zaman açık yazılır.

## Renk
| Belirteç | Değer | Kullanım |
|---|---|---|
| `--pri` | `#0E7490` | Ana eylem düğmesi, seçili çip, etkin sekme, bağlantı, odak halkası |
| `--pri-strong` / `--pri-soft` / `--pri-line` | `#155E75` / `#ECFEFF` / `#A5F3FC` | Basılı durum / açık zemin / çerçeve |
| `--g` + `#16A34A` | yeşil | Şarj ağı indirimi, "kontrol edildi", indirimli fiyat |
| `--y` `#FFC800` + kehribar tonları | sarı | Banka kartı kampanyası, marka şimşeği (düğme rengi olarak kullanılmaz) |
| `--r` | `#B91C1C` | Hata, pasif istasyon, son günler |
| `--txt` / `--mut` / `--line` / `--bg` / `--card2` | slate ölçeği | Metin / ikincil metin / çerçeve / zemin / yüzey |
| AC mavi · DC kehribar | durum renkleri | Listedeki akım türü etiketleri (haritadaki filtre düğmelerinde renk yok) |

Metin kontrastı en az 4,5:1; simge ve çerçevelerde en az 3:1.

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
  koyu yarı saydam cam zemin (`--glass`, bulanıklaştırma ile), 22 px beyaz simge. Beyaz kutu, beyaz çerçeve ve düğme üstü yazı yok;
  ad `title` / `aria-label` içinde. Seçili / etkin: düz `--pri` zemin + beyaz simge (`aria-pressed=true`, filtre düğmesinde `.on`).
- **Tek palet:** denetimlerde simgeye özel renk kullanılmaz. Yeşil % ve sarı kart yalnızca haritadaki işaretçi rozetlerinde,
  kampanya kartı türü kutucuğunda (`.ico`) ve etiketlerde durum rengi olarak kalır.
- **Anlam her yerde aynı:** kart = banka kartı kampanyası, % = şarj ağının kendi indirimi, yıldız = bana uyan, huni = filtre,
  ok = konumum. AC = Type 2 fiş, DC = CCS fiş, çok hızlı DC = CCS + şimşek.
- Yapısal simge olarak emoji ya da yazı tipinde olmayan karakter (✕, ←, ✓) kullanılmaz; yazı tipi her yerde `var(--font)`.
