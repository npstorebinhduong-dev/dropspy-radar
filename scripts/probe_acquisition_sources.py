"""Bounded public-document probes, never calls actor execution or authenticated APIs."""
import argparse
import hashlib
import json
import socket
import ssl
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


def classify_error(exc):
    """Classify the observed layer; HTTPS response alone does not prove origin."""
    if isinstance(exc, HTTPError):
        code = exc.code
        return {
            "http_status": code,
            "proxy_connect_status": None,
            "response_source": "https_response_origin_unverified",
            "error_type": "authentication_failure" if code == 401 else "source_restriction_or_upstream_denial" if code in {403, 429, 451} else "http_error",
            "error_detail": f"HTTPS request returned HTTP {code}; origin attribution unverified",
        }
    reason = getattr(exc, "reason", exc)
    if "Tunnel connection failed: 403" in str(reason):
        return {"http_status": None, "proxy_connect_status": 403, "response_source": "environment_proxy_connect", "error_type": "proxy_connect_403", "error_detail": "Proxy rejected HTTPS CONNECT before destination TLS/HTTP"}
    if "Tunnel connection failed: 407" in str(reason):
        return {"http_status": None, "proxy_connect_status": 407, "response_source": "environment_proxy_connect", "error_type": "proxy_authentication_failure", "error_detail": "Proxy authentication required before destination TLS/HTTP"}
    kind = "dns_error" if isinstance(reason, socket.gaierror) else "tls_error" if isinstance(reason, ssl.SSLError) else "timeout" if isinstance(reason, TimeoutError) else "network_error"
    return {"http_status": None, "proxy_connect_status": None, "response_source": "transport_no_http_response", "error_type": kind, "error_detail": {"dns_error": "Resolver error; failing hostname may be proxy or destination", "tls_error": "TLS verification or handshake failed", "timeout": "Bounded connection/read timed out", "network_error": "Network failure; no destination HTTP status observed"}[kind]}


def probe(name, url, opener=urlopen):
    start = time.monotonic()
    row = {"id": name, "url": url, "observed_at": datetime.now(timezone.utc).isoformat(), "purpose": "public documentation/access probe, not an ad pilot"}
    try:
        with opener(Request(url, headers={"User-Agent": "DROPSpy-Research/0.3", "Accept": "text/html"}), timeout=15) as response:
            body = response.read(1024 * 1024 + 1)
            row.update(http_status=response.status, proxy_connect_status=None, response_source="https_response_origin_unverified", error_type=None, error_detail=None, bytes_read=len(body), sha256=hashlib.sha256(body).hexdigest(), truncated=len(body) > 1024 * 1024, final_url=response.url)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Persist bounded classification, never arbitrary credential-bearing exception text.
        row.update(classify_error(exc))
    row["duration_ms"] = round((time.monotonic() - start) * 1000)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="docs/acquisition/evidence/public-probes.json")
    args = parser.parse_args()
    rows = [probe(name, url) for name, url in URLS.items()]
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"probes": len(rows), "outcomes": {r["id"]: r.get("error_type") or r.get("http_status") for r in rows}}, indent=2))


if __name__ == "__main__":
    main()
