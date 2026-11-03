"""Read only JSON embedded in the public search page. No internal API, browser,
session cookies, challenge solving or access-control fallback. Partial first-page support.
"""

import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlencode, urlparse

import httpx

from .base import AdRecord

MAX_BYTES = 2 * 1024 * 1024


class PublicSourceError(RuntimeError):
    pass


def library_url(query, country):
    return "https://www.facebook.com/ads/library/?" + urlencode(
        {"active_status": "active", "ad_type": "all", "country": country, "q": query, "search_type": "keyword_unordered", "media_type": "all"}
    )


class ScriptJSON(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reading = False
        self.buffer = []
        self.payloads = []

    def handle_starttag(self, tag, attrs):
        self.reading = tag == "script" and dict(attrs).get("type") == "application/json" if tag == "script" else self.reading

    def handle_data(self, data):
        if self.reading:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            if self.reading:
                try:
                    self.payloads.append(json.loads("".join(self.buffer)))
                except (ValueError, RecursionError):
                    pass
            self.buffer = []
            self.reading = False


def objects(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def http_url(value):
    try:
        return isinstance(value, str) and urlparse(value).scheme in {"http", "https"} and bool(urlparse(value).hostname)
    except ValueError:
        return False


def parse_public_page(html, country, now=None):
    if len(html.encode()) > MAX_BYTES:
        raise PublicSourceError("Public page exceeds size limit")
    # Never interact with a login, CAPTCHA, checkpoint or challenge page.
    lower = html.lower()
    if any(marker in lower for marker in ('id="captcha', 'name="captcha', "/checkpoint/", 'id="login_form', "<title>log in", "<title>just a moment")):
        raise PublicSourceError("Public page requires login or a challenge; collection stopped")
    parser = ScriptJSON()
    parser.feed(html)
    stack = list(parser.payloads)
    candidates = []
    recognized = False
    visited = 0
    while stack:
        node = stack.pop()
        visited += 1
        if visited > 50000:
            raise PublicSourceError("Embedded data exceeds parsing limit")
        if isinstance(node, dict):
            if isinstance(node.get("collated_results"), list):
                recognized = True
                candidates.extend(node["collated_results"])
            stack.extend(value for value in node.values() if isinstance(value, (dict, list)))
        elif isinstance(node, list):
            stack.extend(value for value in node if isinstance(value, (dict, list)))
    if not recognized:
        raise PublicSourceError("No supported public search data in page; JavaScript-only/changed page or access gate. No fallback request made")
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    records = []
    details = {}
    seen = set()
    skipped = 0
    for raw in candidates:
        if not isinstance(raw, dict) or not raw.get("ad_archive_id") or raw.get("is_active") is not True:
            skipped += 1
            continue
        external_id = str(raw["ad_archive_id"])
        if not re.fullmatch(r"[0-9]{1,100}", external_id):
            skipped += 1
            continue
        if external_id in seen:
            continue
        snapshot = raw.get("snapshot") or {}
        if not isinstance(snapshot, dict):
            skipped += 1
            continue
        cards = objects(snapshot.get("cards"))
        link = snapshot.get("link_url") or next((c.get("link_url") for c in cards if http_url(c.get("link_url"))), None)
        body = snapshot.get("body")
        body = body.get("text", "") if isinstance(body, dict) else body if isinstance(body, str) else ""
        texts = list(dict.fromkeys(t for t in [body, *[c.get("body") for c in cards]] if isinstance(t, str) and t.strip()))
        title = snapshot.get("title") or (body[:200] if body else None)
        advertiser = raw.get("page_name") or snapshot.get("page_name")
        # v0.1 requires a real landing URL: skip incomplete rows rather than inventing one.
        if not http_url(link) or not isinstance(title, str) or not isinstance(advertiser, str) or len(title) > 500 or len(advertiser) > 200:
            skipped += 1
            continue
        placements = [p.lower() for p in (raw.get("publisher_platform") or []) if isinstance(p, str)]
        platform = "instagram" if "instagram" in placements and "facebook" not in placements else "facebook"
        record = AdRecord(
            source_id=external_id,
            platform=platform,
            advertiser=advertiser,
            title=title,
            country=country,
            status="active",
            landing_url=link,
            source_url=f"https://www.facebook.com/ads/library/?id={external_id}",
            first_seen=now,
            last_seen=now,
            is_demo=False,
            creatives=texts or [title],
        )
        records.append(record)
        seen.add(external_id)
        media = []
        for item in [*cards, *objects(snapshot.get("videos")), *objects(snapshot.get("images"))]:
            for key in ("video_hd_url", "video_sd_url", "original_image_url", "resized_image_url"):
                if http_url(item.get(key)):
                    media.append(item[key])
        details[external_id] = {
            "placements": placements,
            "query_country": country,
            "country_semantics": "search scope, not independently verified delivery geography",
            "media_urls": list(dict.fromkeys(media)),
            "source_delivery_start": raw.get("start_date"),
            "source_delivery_end": raw.get("end_date"),
            "coverage": "partial public first page; not exhaustive",
            "kind": "public_page",
        }
    return {"records": records, "details": details, "skipped": skipped, "coverage": "partial public first page; not exhaustive"}


def fetch_public_page(query, country):
    url = library_url(query, country)
    try:
        with httpx.Client(timeout=20, follow_redirects=False, headers={"Accept": "text/html"}) as client:
            with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise PublicSourceError(f"Public page returned HTTP {response.status_code}; collection stopped without fallback")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise PublicSourceError("Public page exceeds size limit")
                return parse_public_page(body.decode("utf-8", errors="replace"), country)
    except httpx.HTTPError:
        raise PublicSourceError("Public page unavailable through current network policy or transport; no access-control fallback attempted") from None
