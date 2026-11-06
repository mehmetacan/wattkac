"""render.py çıktısından paylaşım kuyruğu (queue/<etiket>.json) üretir.

Takvim: ilk gün 2 özet + 2 post, sonraki günler 3 post (09:30, 13:00, 19:30, İstanbul saati).
Her banka/istasyon postundan 1 saat sonra aynı kurumun hikayesi paylaşılır.
Bitiş tarihi geçmiş kampanyalar kuyruğa alınmaz.
Kullanım: python scripts/build_queue.py --etiket 2026-11 --baslangic 2026-11-07
"""
import argparse, datetime as dt, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = dt.timezone(dt.timedelta(hours=3))  # Europe/Istanbul (yaz saati uygulaması yok)
SAATLER = [(9, 30), (13, 0), (19, 30)]
ILK_GUN = [(9, 30), (10, 0), (13, 0), (19, 30)]
HASHTAG = "#elektrikliaraç #elektriklioto #şarj #şarjistasyonu #kampanya #kredikartı #wattkac"


def tag(s):
    return "#" + "".join(ch for ch in s.lower().replace(" ", "") if ch.isalnum())


def caption(item, d):
    if item["tur"] == "ozet":
        if item["id"] == "ozet_bankalar":
            body = "\n".join(f"• {b['name']}: {' / '.join(o['big'] for o in b['offers'])}" for b in d["bankalar"])
            head = f"⚡ {d['donem']} şarj kampanyaları: hangi banka ne veriyor?"
        else:
            body = "\n".join(f"• {s['name']}: {s['cover']['big']} ({s['cover']['sub']})" for s in d["istasyonlar"])
            head = f"⚡ {d['donem']}: şarj ağlarında hangi kampanyalar var?"
        return f"{head}\n\n{body}\n\nHer kurumun detayı ayrı postta. Kaydedin, şarj etmeden önce bakın.\n\nKoşullar değişebilir; katılmadan önce resmi kanallardan kontrol edin.\n\n{HASHTAG}"
    if item["tur"] == "banka":
        b = item["_src"]
        lines = []
        for o in b["offers"]:
            st = ", ".join(o["st"])
            lines.append(f"✅ {o['big']}: {o['det']}\n📍 {st}\n📝 Katılım: {o['join']}\n⏱ Son gün: {o['son']}")
        return (f"⚡ {b['name']} ile şarjda {b['cover']['big']}!\n\n" + "\n\n".join(lines) +
                f"\n\nKoşullar değişebilir; katılmadan önce bankanın resmi kanallarından kontrol edin."
                f"\n\n{HASHTAG} {tag(b['name'])}")
    s = item["_src"]
    lines = [f"✅ {o['big']}: {o['det']} (son gün {o['son']})" for o in s["own"]]
    lines += [f"💳 {k}: {v}" for k, v in s["banks"]]
    lines.append(f"🌍 Her istasyonda: {d['genel_kartlar']}")
    return (f"⚡ {s['name']} istasyonlarında bu ay ne kazandırıyor?\n\n" + "\n".join(lines) +
            f"\n\nKoşullar değişebilir; katılmadan önce resmi kanallardan kontrol edin.\n\n{HASHTAG} {tag(s['name'])}")


def resmi_mi(url):
    return not any(x in url for x in ["sarjharitasi", "sarjevi", "hangikredi", "sarjkampanya", "arabamsarj", "donanimhaber"])


def kaynaklar(item, d):
    out, seen = [], set()

    def add(ad, url):
        if url and url not in seen:
            seen.add(url)
            out.append({"ad": ad, "url": url, "tur": "resmi" if resmi_mi(url) else "derleme"})

    src = item.get("_src")
    if item["tur"] == "banka":
        for o in src["offers"]:
            add(f"{src['name']}: {o['big']} ({', '.join(o['st'])})", o["link"])
    elif item["tur"] == "istasyon":
        for o in src["own"]:
            add(f"{src['name']}: {o['big']}", o["link"])
        for b in d["bankalar"]:
            for o in b["offers"]:
                if src["name"] in o["st"]:
                    add(f"{b['name']}: {o['big']}", o["link"])
    else:
        for b in d["bankalar"] if item["id"] == "ozet_bankalar" else []:
            for o in b["offers"]:
                add(f"{b['name']}: {o['big']}", o["link"])
        for s in d["istasyonlar"] if item["id"] == "ozet_istasyonlar" else []:
            for o in s["own"]:
                add(f"{s['name']}: {o['big']}", o["link"])
    return out


def bitis(item):
    src = item.get("_src")
    if not src:
        return "2099-12-31"
    tarihler = [o["bit"] or "2099-12-31" for o in src.get("offers", [])] + [o["bit"] or "2099-12-31" for o in src.get("own", [])]
    return max(tarihler) if tarihler else "2099-12-31"


def used_times(skip_path):
    t = set()
    for f in glob.glob(os.path.join(ROOT, "queue", "*.json")):
        if os.path.abspath(f) == os.path.abspath(skip_path):
            continue
        t |= {q["zaman"] for q in json.load(open(f, encoding="utf-8")) if q.get("durum") != "iptal"}
    return t


def build(etiket, baslangic, sadece=None):
    d = json.load(open(os.path.join(ROOT, "data", "kampanyalar.json"), encoding="utf-8"))
    manifest = json.load(open(os.path.join(ROOT, "media", etiket, "manifest.json"), encoding="utf-8"))
    src = {f"banka_{b['id']}": b for b in d["bankalar"]} | {f"istasyon_{s['id']}": s for s in d["istasyonlar"]}
    for m in manifest:
        m["_src"] = src.get(m["id"])

    ozet = [m for m in manifest if m["tur"] == "ozet"]
    banka = [m for m in manifest if m["tur"] == "banka"]
    ist = [m for m in manifest if m["tur"] == "istasyon"]
    # Banka ve istasyonları sırayla karıştır (profil çeşitli görünsün)
    karisik = []
    for i in range(max(len(banka), len(ist))):
        if i < len(banka): karisik.append(banka[i])
        if i < len(ist): karisik.append(ist[i])
    sira = ozet + karisik

    if sadece:
        sira = [m for m in sira if m["id"] in sadece]
    path = os.path.join(ROOT, "queue", f"{etiket}.json")
    if os.path.exists(path) and any(q["durum"] != "bekliyor" for q in json.load(open(path, encoding="utf-8"))):
        raise SystemExit(f"{path} içinde paylaşılmış öğeler var; üzerine yazılmaz. Güncelleme için yeni bir --etiket kullanın.")
    dolu = used_times(path)
    ilk = not dolu
    slots, gun = [], dt.date.fromisoformat(baslangic)
    while len(slots) < len(sira):
        for h, mi in (ILK_GUN if ilk else SAATLER):
            t = dt.datetime(gun.year, gun.month, gun.day, h, mi, tzinfo=TZ)
            if t.isoformat() not in dolu and (t + dt.timedelta(hours=1)).isoformat() not in dolu:
                slots.append(t)
        ilk = False
        gun += dt.timedelta(days=1)

    queue = []
    for item, t in zip(sira, slots):
        son = bitis(item)
        if t.date().isoformat() > son:
            print(f"atlandı (kampanya bitmiş): {item['id']}")
            continue
        base = f"media/{etiket}/{item['id']}"
        grup = f"{etiket}__{item['id']}"
        queue.append({"id": f"{item['id']}_post", "grup": grup, "tip": "karusel", "zaman": t.isoformat(),
                      "baslik": item["baslik"], "tur": item["tur"], "kaynaklar": kaynaklar(item, d),
                      "gorseller": [f"{base}/{f}" for f in item["dosyalar"] if f != "hikaye.jpg"],
                      "aciklama": caption(item, d), "durum": "bekliyor", "deneme": 0, "ig_media_id": None, "hata": None})
        if "hikaye.jpg" in item["dosyalar"]:
            queue.append({"id": f"{item['id']}_hikaye", "grup": grup, "baslik": item["baslik"], "tur": item["tur"], "tip": "hikaye", "zaman": (t + dt.timedelta(hours=1)).isoformat(),
                          "gorseller": [f"{base}/hikaye.jpg"], "aciklama": "", "durum": "bekliyor", "deneme": 0,
                          "ig_media_id": None, "hata": None})
    queue.sort(key=lambda q: q["zaman"])
    json.dump(queue, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return queue


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--etiket", required=True)
    ap.add_argument("--baslangic", required=True, help="YYYY-MM-DD (İstanbul)")
    ap.add_argument("--sadece", default="", help="virgülle post id'leri (boş = hepsi)")
    a = ap.parse_args()
    q = build(a.etiket, a.baslangic, set(x for x in a.sadece.split(",") if x))
    print(f"{len(q)} paylaşım kuyruğa alındı: {q[0]['zaman']} → {q[-1]['zaman']}")
