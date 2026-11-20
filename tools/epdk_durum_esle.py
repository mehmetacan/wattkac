#!/usr/bin/env python3
"""EPDK Şarj@TR sayısal kimliklerini istasyonlar.json'a ekler.

Şarj@TR istasyonlarını koordinat eşleşmesiyle (100 m) istasyonlar.json'daki
kayıtlarla eşleştirir ve eşleşen kayda "eid" yazar. Site bu kimliği
/api/durum/epdk?c=<eid> ile canlı müsaitlik sorgulamak için kullanır.

Kaynak sırası: api.wattkac.com (EPDK_API_KEY varsa) → sarjtr → son başarılı
konum listesinin kopyası (data/epdk/sarjtr_konum.json). Birleştirme her gün
dosyayı baştan ürettiği için bu betik birleştirmeden sonra çalışmalı.
"""

import json
import math
import pathlib
import sys
import os
from urllib.request import Request, urlopen

SARJTR = "https://sarjtr.epdk.gov.tr/sarjet/api/stations"
UA = "Dart/3.4 (dart:io)"
KOK = pathlib.Path(__file__).resolve().parent.parent
IST_YOLU = KOK / "site" / "istasyonlar.json"
KOPYA = KOK / "data" / "epdk" / "sarjtr_konum.json"
API = "https://api.wattkac.com/api/stations"
HUCRE = 0.001  # ~111 m
ESIK_M = 100   # metre


def indir(url, basliklar):
    with urlopen(Request(url, headers={"Accept": "application/json", **basliklar}), timeout=90) as resp:
        veri = json.loads(resp.read())
    sonuc = [(s["id"], s["lat"], s["lng"]) for s in veri if s.get("id") and s.get("lat") and s.get("lng")]
    if len(sonuc) < 1000:
        raise ValueError(f"yalnızca {len(sonuc)} istasyon")
    return sonuc


def cek():
    """(id, lat, lng) listesi; çekilemezse son kopya."""
    kaynaklar = []
    if os.environ.get("EPDK_API_KEY"):
        kaynaklar.append(("api.wattkac.com", API, {"X-API-Key": os.environ["EPDK_API_KEY"], "User-Agent": "wattkac-eslestir/1.0"}))
    kaynaklar.append(("sarjtr", SARJTR, {"User-Agent": UA}))
    for ad, url, basliklar in kaynaklar:
        try:
            sonuc = indir(url, basliklar)
        except Exception as e:
            print(f"UYARI: {ad} okunamadı ({type(e).__name__})")
            continue
        print(f"{ad}: {len(sonuc)} istasyon")
        KOPYA.parent.mkdir(parents=True, exist_ok=True)
        KOPYA.write_text(json.dumps(sorted(sonuc), separators=(",", ":")) + "\n", encoding="utf-8")
        return sonuc
    if KOPYA.exists():
        sonuc = [tuple(x) for x in json.loads(KOPYA.read_text(encoding="utf-8"))]
        print(f"Son kopya kullanılıyor: {len(sonuc)} istasyon")
        return sonuc
    return None


def izgara_olustur(liste):
    grid = {}
    for sid, lat, lng in liste:
        ci, cj = int(lat / HUCRE), int(lng / HUCRE)
        grid.setdefault((ci, cj), []).append((sid, lat, lng))
    return grid


def en_yakin(lat, lng, grid):
    ci, cj = int(lat / HUCRE), int(lng / HUCRE)
    en_iyi, en_uzak = None, float("inf")
    cos_lat = math.cos(math.radians(lat))
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for sid, slat, slng in grid.get((ci + di, cj + dj), []):
                dlat = slat - lat
                dlng = (slng - lng) * cos_lat
                d = math.sqrt(dlat * dlat + dlng * dlng) * 111_000
                if d < en_uzak:
                    en_uzak = d
                    en_iyi = sid
    return en_iyi if en_uzak <= ESIK_M else None


def main():
    sarjtr = cek()
    if not sarjtr:
        print("UYARI: Şarj@TR konumları alınamadı, dosya değiştirilmedi.")
        return

    grid = izgara_olustur(sarjtr)

    # istasyonlar.json oku
    veri = json.loads(IST_YOLU.read_text(encoding="utf-8"))
    istasyonlar = veri["istasyonlar"]
    print(f"istasyonlar.json: {len(istasyonlar)} istasyon")

    # Eşleştir
    eslesen = 0
    for ist in istasyonlar:
        lat, lng = ist.get("a"), ist.get("o")
        if not lat or not lng:
            ist.pop("eid", None)
            continue
        eid = en_yakin(lat, lng, grid)
        if eid:
            ist["eid"] = eid
            eslesen += 1
        else:
            ist.pop("eid", None)

    print(f"Eşleşen: {eslesen} / {len(istasyonlar)} ({eslesen / len(istasyonlar) * 100:.1f}%)")

    # Kaydet
    IST_YOLU.write_text(
        json.dumps(veri, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Kaydedildi: {IST_YOLU}")


if __name__ == "__main__":
    main()
