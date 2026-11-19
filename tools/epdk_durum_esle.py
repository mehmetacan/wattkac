#!/usr/bin/env python3
"""EPDK Şarj@TR sayısal kimliklerini istasyonlar.json'a ekler.

sarjtr.epdk.gov.tr/sarjet/api/stations adresindeki istasyonları
koordinat eşleşmesiyle (100 m) istasyonlar.json'daki kayıtlarla
eşleştirir ve eşleşen kayda "eid" (EPDK sayısal kimliği) yazar.
Site bu kimliği /api/durum/epdk?c=<eid> ile canlı müsaitlik
sorgulamak için kullanır.

sarjtr erişilemezse dosyaya dokunmaz.
"""

import json
import math
import pathlib
import sys
from http.client import HTTPSConnection
from urllib.request import Request, urlopen

SARJTR = "https://sarjtr.epdk.gov.tr/sarjet/api/stations"
UA = "Dart/3.4 (dart:io)"
IST_YOLU = pathlib.Path(__file__).resolve().parent.parent / "site" / "istasyonlar.json"
HUCRE = 0.001  # ~111 m
ESIK_M = 100   # metre


def cek():
    """sarjtr'den istasyonları çek. id, lat, lng döner."""
    req = Request(SARJTR, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=60) as resp:
        veri = json.loads(resp.read())
    sonuc = []
    for s in veri:
        sid = s.get("id")
        lat = s.get("lat", 0)
        lng = s.get("lng", 0)
        if sid and lat and lng:
            sonuc.append((sid, lat, lng))
    return sonuc


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
    # sarjtr'den çek
    try:
        sarjtr = cek()
    except Exception as e:
        print(f"UYARI: sarjtr erişilemedi ({e}), dosya değiştirilmedi.")
        return
    print(f"sarjtr: {len(sarjtr)} istasyon")

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
