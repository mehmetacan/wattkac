"""Instagram istatistiklerini okur (SADECE OKUMA, hiçbir şey paylaşmaz) ve stats/rapor.json'a yazar.
Token asla loglanmaz. Her metrik ayrı istenir; izin olmayan metrik atlanır ve hata notu düşülür."""
import datetime as dt, json, os, urllib.parse, urllib.request, urllib.error

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
UID = os.environ.get("IG_USER_ID", "")
BASE = os.environ.get("IG_API_BASE", "https://graph.facebook.com/v23.0")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get(path, **p):
    p["access_token"] = TOKEN
    try:
        with urllib.request.urlopen(f"{BASE}/{path}?{urllib.parse.urlencode(p)}", timeout=60) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        try:
            return None, json.loads(e.read()).get("error", {}).get("message", f"HTTP {e.code}")[:200]
        except Exception:
            return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)[:200]


def insights(obj, metrics, **extra):
    out, errs = {}, {}
    for m in metrics:
        r, err = get(f"{obj}/insights", metric=m, **extra)
        if err:
            errs[m] = err
            continue
        for it in r.get("data", []):
            vals = it.get("values") or []
            tv = it.get("total_value", {}).get("value")
            out[it["name"]] = tv if tv is not None else (vals[-1].get("value") if vals else None)
    return out, errs


def main():
    rap = {"zaman": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "hatalar": {}}
    acc, err = get(UID, fields="username,followers_count,follows_count,media_count")
    rap["hesap"] = acc or {}
    if err:
        rap["hatalar"]["hesap"] = err
    a_ins, a_err = insights(UID, ["reach", "views", "profile_views", "accounts_engaged", "total_interactions", "follows_and_unfollows"],
                            period="day", metric_type="total_value",
                            since=int((dt.datetime.now() - dt.timedelta(days=7)).timestamp()), until=int(dt.datetime.now().timestamp()))
    rap["hesap_7gun"] = a_ins
    if a_err:
        rap["hatalar"]["hesap_7gun"] = a_err
    media, err = get(f"{UID}/media", fields="id,caption,media_type,media_product_type,timestamp,like_count,comments_count,permalink", limit=50)
    if err:
        rap["hatalar"]["medya"] = err
    rap["medya"] = []
    for m in (media or {}).get("data", []):
        reel = m.get("media_product_type") == "REELS"
        mets = ["reach", "views", "saved", "shares", "total_interactions", "profile_visits", "follows"]
        if reel:
            mets += ["ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
        ins, ierr = insights(m["id"], mets)
        rap["medya"].append({"tur": m.get("media_product_type"), "tip": m.get("media_type"), "zaman": m.get("timestamp"),
                             "begeni": m.get("like_count"), "yorum": m.get("comments_count"), "link": m.get("permalink"),
                             "baslik": (m.get("caption") or "")[:70].replace("\n", " "), "istatistik": ins,
                             "olmayan": sorted(ierr)})
        for k, v in ierr.items():
            rap["hatalar"].setdefault("medya_metrik", {})[k] = v
    os.makedirs(os.path.join(ROOT, "stats"), exist_ok=True)
    with open(os.path.join(ROOT, "stats", "rapor.json"), "w", encoding="utf-8") as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(f"Takipçi: {rap['hesap'].get('followers_count')}, medya: {len(rap['medya'])}, hata grupları: {list(rap['hatalar'])}")


if __name__ == "__main__":
    main()
