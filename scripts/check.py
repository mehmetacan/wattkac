"""Instagram bağlantı testi: hiçbir şey PAYLAŞMAZ.

1. Token'ın hangi API adresiyle çalıştığını ve hesabı gösterir.
2. Kalan paylaşım kotasını yazar.
3. Depodaki bir hikaye görseliyle yayınlanmamış bir medya taslağı oluşturur; Instagram'ın
   görseli GitHub'dan çekebildiğini doğrular. Taslak yayınlanmaz, 24 saatte kendiliğinden silinir.
Token değeri asla loglanmaz.
"""
import glob, json, os, sys, time, urllib.parse, urllib.request, urllib.error

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
UID = os.environ.get("IG_USER_ID", "")
CANDIDATES = ["https://graph.facebook.com/v23.0", "https://graph.instagram.com"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def call(method, base, path, **p):
    p["access_token"] = TOKEN
    data = urllib.parse.urlencode(p)
    url = f"{base}/{path}"
    req = urllib.request.Request(url + "?" + data) if method == "GET" else urllib.request.Request(url, data=data.encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
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
        ok, r = call("GET", base, UID, fields="username")
        print(f"[{base}] hesap: {'✓ ' + r.get('username', '?') if ok else '✗ ' + str(r)[:200]}")
        if ok and not works:
            works = base
            ok2, lim = call("GET", base, f"{UID}/content_publishing_limit", fields="quota_usage,config")
            print(f"[{base}] paylaşım kotası: {lim if ok2 else '✗ ' + str(lim)[:200]}")
    if not works:
        print("\nSONUÇ: Token hiçbir adresle çalışmadı.")
        return 1

    imgs = sorted(glob.glob(os.path.join(ROOT, "media", "*", "*", "hikaye.jpg")))
    if imgs:
        rel = os.path.relpath(imgs[0], ROOT)
        url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{os.environ.get('GITHUB_SHA', 'main')}/{urllib.parse.quote(rel)}"
        print(f"\nGörsel çekme testi (YAYINLANMAZ): {rel}")
        ok, r = call("POST", works, f"{UID}/media", image_url=url, media_type="STORIES")
        if not ok:
            print(f"✗ Taslak oluşturulamadı: {str(r)[:300]}")
            return 1
        cid, st = r["id"], None
        for _ in range(20):
            ok, s = call("GET", works, cid, fields="status_code")
            st = s.get("status_code") if ok else s
            if st in ("FINISHED", "ERROR", "EXPIRED"):
                break
            time.sleep(3)
        print(f"{'✓' if st == 'FINISHED' else '✗'} Taslak durumu: {st} (yayınlanmadı)")
        if st != "FINISHED":
            return 1
    print(f"\nSONUÇ: Her şey hazır. Çalışan adres = {works}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
