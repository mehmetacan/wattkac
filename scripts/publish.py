"""Kuyruktaki zamanı gelmiş postları ve hikayeleri Instagram API ile paylaşır.

GitHub Actions içinde çalışır (bkz. .github/workflows/yayinla.yml).
Ortam değişkenleri:
  IG_USER_ID, IG_ACCESS_TOKEN   (GitHub Secrets)
  GRAPH_BASE                    varsayılan https://graph.facebook.com/v23.0 (bağlantı testiyle doğrulandı)
                                Instagram girişli token için: https://graph.instagram.com
  GITHUB_REPOSITORY, GITHUB_SHA (Actions otomatik verir; görsellerin herkese açık adresi için)
  DRY_RUN=1                     hiçbir şey paylaşmadan ne yapılacağını yazar
  YAYIN_AKTIF                   "true" değilse paylaşım yapılmaz (GitHub repo değişkeni)

Onay: Bir öğe ancak onaylar/<grup>.json dosyasında {"onay": "onaylandi"} varsa paylaşılır.
Bu dosyaları onay paneli (docs/index.html) yazar. Onay dosyası şunları da değiştirebilir:
  zaman   → postun paylaşım zamanı (hikaye 1 saat sonra)
  aciklama → Instagram açıklaması
  hikaye  → false ise hikaye paylaşılmaz
"""
import datetime as dt, glob, json, os, sys, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = (os.environ.get("GRAPH_BASE") or "https://graph.facebook.com/v23.0").rstrip("/")
DRY = os.environ.get("DRY_RUN") == "1"
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "3"))
GEC_KALMA_SINIRI = dt.timedelta(hours=24)   # bundan geç kalmış paylaşım atlanır
MAX_DENEME = 3


def log(*a):
    print(*a, flush=True)


def api(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    url = f"{BASE}/{path.lstrip('/')}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        raise RuntimeError(f"HTTP {e.code}: {msg}") from None


def public_url(rel):
    repo = os.environ["GITHUB_REPOSITORY"]
    ref = os.environ.get("GITHUB_SHA", "main")
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{urllib.parse.quote(rel)}"


def wait_ready(cid, tries=20):
    for _ in range(tries):
        st = api("GET", cid, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Medya hazırlanamadı: {st}")
        time.sleep(3)
    raise RuntimeError("Medya zamanında hazırlanmadı")


def publish(item, uid):
    urls = [public_url(p) for p in item["gorseller"]]
    if DRY:
        log(f"  [DRY] {item['tip']}: {urls}")
        return "dry-run"
    if item["tip"] == "hikaye":
        c = api("POST", f"{uid}/media", image_url=urls[0], media_type="STORIES")["id"]
    elif len(urls) == 1:
        c = api("POST", f"{uid}/media", image_url=urls[0], caption=item["aciklama"])["id"]
    else:
        kids = []
        for u in urls:
            k = api("POST", f"{uid}/media", image_url=u, is_carousel_item="true")["id"]
            wait_ready(k)
            kids.append(k)
        c = api("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(kids), caption=item["aciklama"])["id"]
    wait_ready(c)
    return api("POST", f"{uid}/media_publish", creation_id=c)["id"]


def quota_left(uid):
    try:
        r = api("GET", f"{uid}/content_publishing_limit", fields="quota_usage,config")["data"][0]
        return r["config"]["quota_total"] - r["quota_usage"]
    except Exception as e:
        log(f"Limit okunamadı ({e}); devam ediliyor")
        return 999


def persist(path, q, msg):
    """Kuyruğu yazar; Actions içindeyse hemen commit+push yapar (yarıda kesilirse çift paylaşım olmasın)."""
    json.dump(q, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.environ.get("GIT_COMMIT_EACH") != "1":
        return
    import subprocess
    rel = os.path.relpath(path, ROOT)
    run = lambda *a: subprocess.run(list(a), cwd=ROOT, capture_output=True, text=True)
    run("git", "add", rel)
    if run("git", "diff", "--cached", "--quiet").returncode == 0:
        return
    run("git", "-c", "user.name=wattkac-bot", "-c", "user.email=wattkac-bot@users.noreply.github.com",
        "commit", "-m", f"{msg} [skip ci]")
    for _ in range(3):
        pr = run("git", "-c", "user.name=wattkac-bot", "-c", "user.email=wattkac-bot@users.noreply.github.com",
                 "pull", "--rebase", "-q", "origin", "main")
        if pr.returncode != 0:
            log(f"git pull hatası: {pr.stderr.strip()[:300]}")
            run("git", "rebase", "--abort")
        ps = run("git", "push", "-q", "origin", "HEAD:main")
        if ps.returncode == 0:
            return
        log(f"git push hatası: {ps.stderr.strip()[:300]}")
        time.sleep(3)
    log("Uyarı: kuyruk durumu push edilemedi")


def load_approvals():
    out = {}
    for f in glob.glob(os.path.join(ROOT, "onaylar", "*.json")):
        try:
            out[os.path.basename(f)[:-5]] = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            log(f"Onay dosyası okunamadı {f}: {e}")
    return out


def effective(item, approvals):
    """Onaya göre öğenin paylaşılıp paylaşılmayacağını ve zamanını döndürür: (paylasilacak_mi, zaman, aciklama)."""
    grup = item.get("grup") or item["id"].rsplit("_", 1)[0]
    a = approvals.get(grup)
    if not a or a.get("onay") != "onaylandi":
        return False, None, None
    t = dt.datetime.fromisoformat(a.get("zaman") or item["zaman"])
    if item["tip"] == "hikaye":
        if item.get("yalniz_hikaye"):        # tek başına hikaye: panelde seçilen saat aynen kullanılır
            return True, t, ""
        if a.get("hikaye") is False:
            return False, None, None
        if a.get("zaman"):
            t = t + dt.timedelta(hours=1)
        return True, t, ""
    return True, t, a.get("aciklama") or item["aciklama"]


def main():
    if os.environ.get("YAYIN_AKTIF", "").lower() != "true" and not DRY:
        log("YAYIN_AKTIF=true değil, paylaşım kapalı. Çıkılıyor.")
        return 0
    uid = os.environ.get("IG_USER_ID", "DRY")
    now = dt.datetime.now(dt.timezone.utc)
    done, errors = 0, 0
    left = 999 if DRY else quota_left(uid)
    log(f"Kalan günlük API kotası: {left}")
    approvals = load_approvals()
    log(f"Onaylı grup sayısı: {sum(1 for a in approvals.values() if a.get('onay') == 'onaylandi')}")
    for path in sorted(glob.glob(os.path.join(ROOT, "queue", "*.json"))):
        q = json.load(open(path, encoding="utf-8"))
        changed = False
        for item in q:
            if item["durum"] not in ("bekliyor", "hata"):
                continue
            if item["durum"] == "hata" and item.get("deneme", 0) >= MAX_DENEME:
                continue
            ok, t, aciklama = effective(item, approvals)
            if not ok:
                continue
            item = dict(item, aciklama=aciklama, _ref=item)
            if t > now:
                continue
            ref = item["_ref"]
            if now - t > GEC_KALMA_SINIRI:
                ref["durum"], ref["hata"] = "atlandi", "24 saatten fazla gecikti"
                changed = True
                continue
            if done >= MAX_PER_RUN or left <= 1:
                break
            log(f"Paylaşılıyor: {item['id']} (onaylı saat {t.astimezone(dt.timezone(dt.timedelta(hours=3))):%d.%m %H:%M})")
            try:
                mid = publish(item, uid)
                if not DRY:
                    ref.update(durum="paylasildi", ig_media_id=mid, hata=None,
                               paylasim_zamani=now.isoformat(timespec="seconds"))
                    persist(path, q, f"Paylaşıldı: {ref['id']}")
                log(f"  ✓ {mid}")
                done += 1
                left -= 1
            except Exception as e:
                ref["deneme"] = ref.get("deneme", 0) + 1
                ref.update(durum="hata", hata=str(e)[:500])
                changed = True
                errors += 1
                log(f"  ✗ HATA ({ref['id']}): {e}")
        if changed and not DRY:
            persist(path, q, "Kuyruk güncellendi")
    log(f"Bitti: {done} paylaşım, {errors} hata")
    return 1 if errors and not done else 0


def next_due_seconds():
    """Onaylı ve bekleyen en yakın öğenin kaç saniye sonra paylaşılacağı (yoksa None)."""
    approvals = load_approvals()
    now = dt.datetime.now(dt.timezone.utc)
    best = None
    for path in glob.glob(os.path.join(ROOT, "queue", "*.json")):
        for item in json.load(open(path, encoding="utf-8")):
            if item["durum"] != "bekliyor":
                continue
            ok, t, _ = effective(item, approvals)
            if ok and t > now:
                sec = (t - now).total_seconds()
                best = sec if best is None else min(best, sec)
    return best


if __name__ == "__main__":
    # BEKLE_DK > 0 ise: bu çalışma içinde zamanı yaklaşan onaylı öğeleri bekleyip tam saatinde paylaşır.
    limit = time.time() + int(os.environ.get("BEKLE_DK", "0")) * 60
    rc = main()
    while not DRY:
        sec = next_due_seconds()
        if sec is None or time.time() + sec > limit:
            break
        log(f"Sıradaki onaylı paylaşım {int(sec // 60)} dk {int(sec % 60)} sn sonra, bekleniyor…")
        time.sleep(sec + 5)
        rc = main() or rc
    sys.exit(rc)
