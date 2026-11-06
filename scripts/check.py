"""Instagram bağlantı testi: hiçbir şey paylaşmaz.

Token'ın hangi API adresiyle çalıştığını, hesabı ve kalan paylaşım kotasını yazdırır.
Token değeri asla loglanmaz.
"""
import json, os, sys, urllib.parse, urllib.request, urllib.error

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
UID = os.environ.get("IG_USER_ID", "")
CANDIDATES = ["https://graph.instagram.com", "https://graph.facebook.com/v23.0"]


def get(base, path, **p):
    p["access_token"] = TOKEN
    url = f"{base}/{path}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return True, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read()).get("error", {}).get("message", "")
        except Exception:
            return False, f"HTTP {e.code}"


def main():
    if not TOKEN or not UID:
        print("✗ IG_ACCESS_TOKEN veya IG_USER_ID secret'ı eksik.")
        return 1
    print(f"Token uzunluğu: {len(TOKEN)}, kullanıcı ID: {UID}")
    works = None
    for base in CANDIDATES:
        ok, r = get(base, UID, fields="username")
        print(f"[{base}] hesap: {'✓ ' + r.get('username', '?') if ok else '✗ ' + str(r)[:200]}")
        if ok:
            ok2, lim = get(base, f"{UID}/content_publishing_limit", fields="quota_usage,config")
            print(f"[{base}] paylaşım kotası: {lim if ok2 else '✗ ' + str(lim)[:200]}")
            works = works or base
    if works:
        print(f"\nSONUÇ: Çalışan adres = {works}")
        print(f"GRAPH_BASE değişkeni bu değer olmalı: {works}")
        return 0
    print("\nSONUÇ: Token hiçbir adresle çalışmadı.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
