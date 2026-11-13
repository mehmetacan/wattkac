#!/usr/bin/env python3
"""5 Şarj'ın kendi haritasının (5sarj.com/tr/sarj-istasyonlari) anlık kopyasını data/aglar/5sarj.json'a dönüştürür ve EPDK
"5 şarj" kayıtlarıyla eşleştirir.

Kullanım: python3 tools/5sarj_kopya.py <map-pins.json> [YYYY-AA-GG]

Girdi, sitenin haritasının kullandığı 5sarj.com/api/locations/map-pins yanıtıdır ({"content": [lokasyon, ...]}); kullanıcı kendi
tarayıcısından kaydedip verir. 5sarj.com Cloudflare bot korumalı: bu betik ve günlük iş akışı siteye istek ATMAZ, korumayı aşmaya
çalışılmaz (ag_istasyonlari.py'de 5 Şarj yoktur). Dosya bu yüzden otomatik güncellenmez; yeni bir kopya gelince betik yeniden çalıştırılır.

Liste istasyonların yerine geçmez (fiyat yok, soketlerin gücü yok): istasyon_birlestir.py DOGRULA ile EPDK kayıtları gösterilmeye devam
eder, listede karşılığı olan EPDK kaydı "rl" alır. Eşleştirme burada yapılır, EPDK numaraları "e"ye yazılır (bir lokasyonda birden çok
EPDK ünitesi olabildiği için liste):
  1) konum: her EPDK "5 şarj" kaydı, 300 m içindeki lokasyonlardan adı en çok benzeyene (eşitse en yakına) bağlanır. Yakındaki
     lokasyonların hiçbirinin adı benzemiyor ve listede adı birebir aynı başka bir lokasyon varsa bağlanmaz (EPDK konumu yanlış
     girilmiş olabilir, ör. ŞRJ/18836 Defacto-Küçükçekmece EPDK'da Büyükçekmece'deki bir PO istasyonunun üstünde);
  2) ad: hâlâ eşleşmemiş lokasyon ve kayıtlar adla (benzerlik ≥ 0,5) eşleştirilir: 5 km içinde ya da adresteki ilçe aynıysa 25 km
     içinde. Bunlar konumu farklı diye raporlanır (konum her durumda EPDK'dan gelir; hangisinin doğru olduğu elle değerlendirilir).
Kayıt alanları: i="5sarj<id>", a/o, n (ad), b, il, ilce, ad (adres), ac/dc (soket sayısı; HPC DC sayılır), c (toplam soket), e.
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import konum_denetim as kd  # noqa: E402

EPDK_API = pathlib.Path("data/epdk/epdk_api.json")
OUT = pathlib.Path("data/aglar/5sarj.json")
KAYNAK = "https://5sarj.com/tr/sarj-istasyonlari"
EPDK_5SARJ = r"\b5 sarj\b|\bborenco"  # EPDK marka "5 şarj", işletmeci "BORENCO ŞARJ TEKNOLOJİ YATIRIMLARI…"
YAKIN_KM = 0.3
AD_KM = 5.0
AD_ILCE_KM = 25.0
AD_ESIK = 0.5


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cekildi = sys.argv[2] if len(sys.argv) > 2 else "2026-11-13"
    ham = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    ham = ham.get("content", ham) if isinstance(ham, dict) else ham
    liste = []
    for x in ham:
        a, o = x.get("latitude"), x.get("longitude")
        if not kd.gecerli(a, o):
            print(f"5sarj: konumsuz atlandı: {x.get('name')}")
            continue
        ac = dc = 0
        for s in x.get("stations") or []:
            for k in s.get("connectors") or []:
                if ((k.get("powerType") or {}).get("code") or "").upper() == "AC":
                    ac += 1
                else:  # DC ve HPC
                    dc += 1
        r = {"i": f"5sarj{x['id']}", "a": round(a, 6), "o": round(o, 6), "n": " ".join((x.get("name") or "").split()), "b": "5 Şarj",
             "il": ((x.get("city") or {}).get("name") or "").strip(), "ilce": ((x.get("district") or {}).get("name") or "").strip(),
             "ad": " ".join((x.get("address") or "").split())}
        if ac:
            r["ac"] = ac
        if dc:
            r["dc"] = dc
        if ac + dc:
            r["c"] = ac + dc
        liste.append(r)
    if len({r["i"] for r in liste}) != len(liste):
        raise SystemExit("kimlik çakışması")

    epdk = [x for x in json.loads(EPDK_API.read_text(encoding="utf-8")).get("istasyonlar", [])
            if re.search(EPDK_5SARJ, kd.fold(x.get("marka", "") + " " + x.get("isletmeci", ""))) and kd.gecerli(x.get("a"), x.get("o"))]
    sim = lambda r, x: kd.benzer(r["n"], x.get("ad", ""), ("po",))
    es = {}  # EPDK no → lokasyon indeksi
    for x in epdk:
        aday = [(-sim(r, x), kd.km(r["a"], r["o"], x["a"], x["o"]), i) for i, r in enumerate(liste)
                if kd.km(r["a"], r["o"], x["a"], x["o"]) <= YAKIN_KM]
        if aday and min(aday)[0] == 0 and any(sim(r, x) >= 1 for r in liste):
            continue  # yakındaki istasyon başka; adı birebir tutan lokasyon uzakta (2. adımda)
        if aday:
            es[x["no"]] = min(aday)[2]
    eslesen = set(es.values())
    uzak = []
    ilce_ayni = lambda r, x: kd.harfler(r["ilce"]) == (kd.il_ilce_epdk(x.get("adres", ""))[1] or "-")
    ciftler = sorted((-sim(r, x), kd.km(r["a"], r["o"], x["a"], x["o"]), i, x["no"]) for i, r in enumerate(liste) if i not in eslesen
                     for x in epdk if x["no"] not in es and sim(r, x) >= AD_ESIK
                     and kd.km(r["a"], r["o"], x["a"], x["o"]) <= (AD_ILCE_KM if ilce_ayni(r, x) else AD_KM))
    for s, d, i, no in ciftler:
        if no not in es and (i not in eslesen or any(u[0] == i for u in uzak)):
            es[no] = i; eslesen.add(i); uzak.append((i, no, d))
    for no, i in sorted(es.items(), key=lambda t: (t[1], int(re.sub(r"\D", "", t[0]) or 0))):
        liste[i].setdefault("e", []).append(no)

    OUT.write_text(json.dumps({"ag": "5sarj", "kaynak": KAYNAK, "cekildi": cekildi, "sayi": len(liste),
                               "not": "kullanıcının tarayıcısından alınan anlık kopya; otomatik güncellenmez",
                               "istasyonlar": sorted(liste, key=lambda r: int(r["i"][5:]))}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    ep = {x["no"]: x for x in epdk}
    print(f"5sarj: resmi liste {len(liste)} lokasyon ({sum(r.get('ac', 0) for r in liste)} AC, {sum(r.get('dc', 0) for r in liste)} DC/HPC soket) → {OUT}")
    print(f"5sarj: EPDK 5 şarj kaydı {len(epdk)}; listede karşılığı olan {len(es)} kayıt, EPDK'yla eşleşen lokasyon {len(eslesen)}"
          f" (konumla {len(eslesen) - len({u[0] for u in uzak})}, adla {len({u[0] for u in uzak})})")
    for i, no, d in uzak:
        r, x = liste[i], ep[no]
        print(f"5sarj: konumu farklı ({d * 1000:.0f} m): {r['n']} [{r['ilce']}/{r['il']}] {r['a']},{r['o']} ↔ {no} {x['ad']} "
              f"[{x.get('adres', '')}] {x['a']},{x['o']}")
    yok = [r for i, r in enumerate(liste) if i not in eslesen]
    print(f"5sarj: listede olup EPDK 5 şarj kaydı bulunamayan ({len(yok)}; haritaya eklenmez): " + "; ".join(f"{r['n']} ({r['ilce']}/{r['il']})" for r in yok))
    disari = [x for x in epdk if x["no"] not in es]
    print(f"5sarj: EPDK'da 5 şarj olup listede olmayan ({len(disari)}; EPDK kaydıyla gösterilmeye devam eder): "
          + "; ".join(f"{x['no']} {x['ad']}" for x in disari))


if __name__ == "__main__":
    main()
