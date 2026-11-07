#!/usr/bin/env python3
"""Yalnızca "seçili istasyonlarda" geçerli ağ kampanyalarının istasyon listelerini, kampanya sahibinin resmi
sayfasından okur ve data/secili_istasyonlar.json dosyasına yazar. istasyon_birlestir.py bu listeyle eşleşen
istasyonlara "sk" (seçili kampanya) etiketini koyar; sitede kampanya yalnızca bu istasyonlarda gösterilir.

Kaynaklar:
  otopriz  https://otopriz.com.tr/kampanyalar/indirimli-istasyonlar/kampanya-detaylari  (Seçili istasyonlarda %30)
Okunamazsa önceki dosya korunur.
"""
import html, json, pathlib, re, sys, urllib.request, datetime

OUT = pathlib.Path("data/secili_istasyonlar.json")
UA = "WattKac/1.0 (+https://wattkac.com)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text_lines(page):
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|li|h\d|div|tr|td)>", "\n", page)
    t = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n") if x.strip()]


def otopriz():
    url = "https://otopriz.com.tr/kampanyalar/indirimli-istasyonlar/kampanya-detaylari"
    lines = text_lines(get(url))
    try:
        a = next(i for i, x in enumerate(lines) if x.startswith("Kampanyaya Dahil İstasyonlar"))
        b = next(i for i, x in enumerate(lines) if i > a and "Kampanya Koşulları" in x)
    except StopIteration:
        raise RuntimeError("istasyon listesi bölümü bulunamadı")
    il, out = None, []
    for x in lines[a + 1:b]:
        if "," in x:
            ad, ilce = [y.strip() for y in x.rsplit(",", 1)]
            out.append({"il": il, "ilce": ilce, "ad": ad})
        elif len(x) <= 25:
            il = x
    bitis = re.search(r"(\d{1,2}) (Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık) (\d{4}) saat", " ".join(lines))
    return {"ag": "Otopriz", "kaynak": url, "baslik": "Seçili istasyonlarda %30 indirim",
            "bitis": " ".join(bitis.groups()) if bitis else "", "istasyonlar": out}


SOURCES = {"otopriz": (otopriz, 20)}


def main():
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for key, (fn, minimum) in SOURCES.items():
        try:
            d = fn()
            if len(d["istasyonlar"]) < minimum:
                raise RuntimeError(f"yalnızca {len(d['istasyonlar'])} istasyon")
            d["cekildi"] = datetime.date.today().isoformat()
            data[key] = d
            print(f"{key}: {len(d['istasyonlar'])} seçili istasyon")
        except Exception as e:  # noqa: BLE001
            print(f"{key}: BAŞARISIZ ({e}); önceki liste korunuyor", file=sys.stderr)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
