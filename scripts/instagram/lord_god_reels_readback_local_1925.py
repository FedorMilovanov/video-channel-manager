"""Read-only Lord God Instagram 19:25 Moscow postflight; never initiates any Meta POST."""

from __future__ import annotations
import datetime as dt
import json
import pathlib
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
import hashlib

ROOT = pathlib.Path(r"E:\VideoChannelManager\Instagram\LordGod\20261110-daily-wave")
REPO = pathlib.Path(r"C:\Users\Fedor\Projects\video-channel-manager")
RELEASE = ROOT / "release-12-reels-OWNER-DIRECTED-v2.json"
ACCOUNT = "17841433845016161"
PAGE = "1457892317403899"


def get_token():
    f = REPO / ".env"
    if not f.exists():
        return None
    vals = [
        line.partition("=")[2].strip().strip('"').strip("'")
        for line in f.read_text(encoding="utf-8-sig").splitlines()
        if line.startswith("VCM_INSTAGRAM_ACCESS_TOKEN_LORD_GOD_STRENGTH=")
    ]
    return vals[0] if len(vals) == 1 and len(vals[0]) >= 35 else None


def get(url, token):
    if urllib.parse.urlsplit(url).hostname != "graph.facebook.com":
        raise RuntimeError("Unexpected Meta host")
    with urllib.request.urlopen(
        urllib.request.Request(
            url, headers={"Authorization": "Bearer " + token, "User-Agent": "LordGodReadOnlyPostflight/1.0"}
        ),
        timeout=20,
    ) as response:
        return json.load(response)


def list_meta_media(token):
    """Read a complete bounded Meta feed with GET only; never follow paging.next."""
    collected = []
    after = None
    seen = set()
    for page in range(5):
        params = {"fields": "id,caption,permalink,media_type,media_product_type,timestamp", "limit": "100"}
        if after is not None:
            params["after"] = after
        url = "https://graph.facebook.com/v26.0/" + ACCOUNT + "/media?" + urllib.parse.urlencode(params)
        payload = get(url, token)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RuntimeError("Meta feed data not a list")
        data = payload["data"]
        if not all(isinstance(item, dict) for item in data):
            raise RuntimeError("Meta feed contains malformed media row")
        collected.extend(data)
        if "paging" not in payload:
            return collected
        paging = payload["paging"]
        if not isinstance(paging, dict):
            raise RuntimeError("Meta feed paging malformed")
        if "next" not in paging:
            return collected
        if not isinstance(paging["next"], str) or not paging["next"]:
            raise RuntimeError("Meta feed continuation invalid")
        cursors = paging.get("cursors")
        cursor = cursors.get("after") if isinstance(cursors, dict) else None
        if not data or not isinstance(cursor, str) or not cursor or cursor in seen:
            raise RuntimeError("Meta feed continuation cursor missing or looping")
        if page == 4 or len(collected) >= 500:
            raise RuntimeError("Meta feed exceeds complete-verification bound")
        seen.add(cursor)
        after = cursor
    raise RuntimeError("Meta feed did not terminate")


def verify_provider_receipt(token, expected_media_id, row):
    """Strict receipt verification; None means unverified, never published."""
    owner = get("https://graph.facebook.com/v26.0/me?fields=id", token)
    if not isinstance(owner, dict) or str(owner.get("id")) != PAGE:
        raise RuntimeError("Unexpected Page token owner")
    page = get("https://graph.facebook.com/v26.0/" + PAGE + "?fields=id,instagram_business_account{id,username}", token)
    account = page.get("instagram_business_account") if isinstance(page, dict) else None
    if (
        not isinstance(account, dict)
        or str(page.get("id")) != PAGE
        or str(account.get("id")) != ACCOUNT
        or account.get("username") != "thelordgodismystrength"
    ):
        raise RuntimeError("Unexpected Instagram business account")

    expected_caption = row["caption"]
    calculated = "sha256:" + hashlib.sha256(expected_caption.encode("utf-8")).hexdigest()
    if row.get("caption_sha256") != calculated:
        raise RuntimeError("Local approved caption digest mismatch")
    media_rows = list_meta_media(token)
    by_id = [x for x in media_rows if str(x.get("id", "")) == str(expected_media_id)]
    same_caption = [x for x in media_rows if x.get("caption") == expected_caption]
    if len(by_id) > 1 or len(same_caption) > 1:
        raise RuntimeError("Duplicate provider media ID or caption")
    if len(by_id) != 1:
        return None
    media = by_id[0]
    if media.get("caption") != expected_caption:
        return None
    media_id = str(media.get("id", ""))
    permalink = media.get("permalink")
    if (
        not media_id.isdecimal()
        or media.get("media_product_type") != "REELS"
        or media.get("media_type") not in ("VIDEO", "REELS")
        or not isinstance(permalink, str)
    ):
        raise RuntimeError("Matched media ID, type or URL invalid")
    parsed_url = urllib.parse.urlsplit(permalink)
    if parsed_url.scheme != "https" or parsed_url.hostname not in ("www.instagram.com", "instagram.com"):
        raise RuntimeError("Matched Instagram permalink invalid")
    timestamp = media.get("timestamp")
    try:
        if not isinstance(timestamp, str):
            raise ValueError("Missing provider timestamp")
        published = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if published.tzinfo is None:
            raise ValueError("Timestamp must have timezone")
    except ValueError as e:
        raise RuntimeError("Provider timestamp invalid") from e
    expected_date = row["scheduled_at_moscow"][:10]
    actual_date = published.astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat()
    if actual_date != expected_date:
        raise RuntimeError("Provider Moscow date does not match scheduled date")
    return {"permalink": permalink, "provider_timestamp": timestamp}


def main():
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
    today = now.date().isoformat()
    outdir = ROOT / "operator-logs"
    outdir.mkdir(exist_ok=True)
    out = outdir / ("readback-" + today + ".json")
    if out.exists():
        raise RuntimeError("Today's readback already recorded; refuse overwrite")
    data = json.loads(RELEASE.read_text(encoding="utf8"))
    if data["instagram_account_id"] != ACCOUNT or len(data["items"]) != 12:
        raise RuntimeError("Wrong owner account/queue")
    rows = [x for x in data["items"] if x["scheduled_at_moscow"][:10] == today]
    if len(rows) != 1:
        print(json.dumps({"status": "NO_SCHEDULED_SLOT_TODAY", "today": today, "meta_posts": 0}))
        return
    row = rows[0]
    db = REPO / "data" / "video_manager.db"
    con = sqlite3.connect("file:" + db.as_posix() + "?mode=ro", uri=True)
    try:
        found = con.execute(
            "SELECT account_id,status,provider_container_id,provider_media_id,attempt_count,last_error_code,published_at FROM instagram_publications WHERE publication_key=?",
            (row["publication_key"],),
        ).fetchone()
    finally:
        con.close()
    report = {
        "schema": "lord-god-instagram-postflight-readonly-v1",
        "observed_at_moscow": now.isoformat(),
        "source_id": row["source_youtube_id"],
        "publication_key": row["publication_key"],
        "target_instagram_account_id": ACCOUNT,
        "expected_caption_sha256": row["caption_sha256"],
        "provider_writes": 0,
        "verification": "NOT_ATTEMPTED",
        "evidence": {"local_ledger_record_found": bool(found)},
    }
    if found:
        account, status, container, media, attempts, error, published = found
        report["evidence"].update(
            {
                "account_matches": account == ACCOUNT,
                "ledger_status": status,
                "attempt_count": attempts,
                "provider_container_id": container,
                "provider_media_id": media,
                "error_code": error,
                "published_at_local_ledger": published,
            }
        )
        report["verification"] = "LEDGER_ONLY_NOT_PROVIDER_VERIFIED"
        if account != ACCOUNT:
            report["verification"] = "CRITICAL_WRONG_ACCOUNT_LEDGER"
        elif status == "published" and media:
            token = get_token()
            if not token:
                report["verification"] = "PUBLISHED_LEDGER_META_READ_UNAVAILABLE"
            else:
                try:
                    evidence = verify_provider_receipt(token, media, row)
                    if evidence is not None:
                        report["verification"] = "VERIFIED_PUBLISHED_BY_META"
                        report["evidence"].update(evidence)
                    else:
                        report["verification"] = "META_ID_OR_CAPTION_UNVERIFIED"
                except urllib.error.HTTPError as e:
                    report["verification"] = "META_READ_FAILED"
                    report["evidence"]["http"] = e.code
                except Exception as e:
                    report["verification"] = "META_READ_UNVERIFIED"
                    report["evidence"]["error_type"] = type(e).__name__
        elif status in ("container_unknown", "publish_unknown", "published_unresolved"):
            report["verification"] = "AMBIGUOUS_PROVIDER_EFFECT_NO_RETRY"
    else:
        report["verification"] = "NO_LEDGER_WRITE_NO_PUBLICATION_PROVEN"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf8")
    print(
        json.dumps(
            {
                "status": report["verification"],
                "source_id": row["source_youtube_id"],
                "report": str(out),
                "meta_writes": 0,
            },
            ensure_ascii=False,
        )
    )
    if report["verification"] != "VERIFIED_PUBLISHED_BY_META":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
