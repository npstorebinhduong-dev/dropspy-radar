"""Bounded public-document probes, never calls actor execution or authenticated APIs."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URLS = {
    "meta_public": "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&q=solar%20garden%20lights&search_type=keyword_unordered",
    "meta_official": "https://developers.facebook.com/docs/graph-api/reference/ads_archive/",
    "meta_terms": "https://www.facebook.com/legal/automated_data_collection_terms",
    "tiktok_top": "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?region=US",
    "tiktok_official": "https://developers.tiktok.com/doc/commercial-content-api-getting-started",
    "locaihost": "https://apify.com/locaihost/facebook-ad-library",
    "steadyfetch": "https://apify.com/steadyfetch/facebook-ad-library-scraper",
    "silentflow": "https://apify.com/silentflow/tiktok-creative-ads-scraper",
    "data_xplorer": "https://apify.com/data_xplorer/tiktok-ads-scraper",
    "curious_coder": "https://apify.com/curious_coder/facebook-ads-library-scraper",
    "apify_dataset_docs": "https://docs.apify.com/api/v2/dataset-items-get",
}


def main():
    rows = []
    for name, url in URLS.items():
        start = time.monotonic()
        row = {"id": name, "url": url, "observed_at": datetime.now(timezone.utc).isoformat(), "purpose": "public documentation/access probe, not an ad pilot"}
        try:
            with urlopen(Request(url, headers={"User-Agent": "DROPSpy-Research/0.3", "Accept": "text/html"}), timeout=15) as response:
                body = response.read(1024 * 1024 + 1)
                row.update(http_status=response.status, bytes_read=len(body), sha256=hashlib.sha256(body).hexdigest(), truncated=len(body) > 1024 * 1024, final_url=response.url)
        except HTTPError as exc:
            row.update(http_status=exc.code, error_type="http_error")
        except (URLError, TimeoutError, OSError) as exc:
            # Only classify known failure, never persist credential-bearing exception URLs.
            row.update(http_status=None, error_type="proxy_connect_403" if "Tunnel connection failed: 403" in str(exc) else "network_error")
        row["duration_ms"] = round((time.monotonic() - start) * 1000)
        rows.append(row)
    path = Path("docs/acquisition/evidence/public-probes.json")
    path.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"probes": len(rows), "outcomes": {r["id"]: r.get("error_type", r.get("http_status")) for r in rows}}, indent=2))


if __name__ == "__main__":
    main()
