"""GET-only, fixed-host transport. No redirect traversal, paid POST or auth fallback."""
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from .contracts import AcquisitionError

MAX_BYTES = 2 * 1024 * 1024


class Transport:
    def __init__(self, host, client=None, sleep=time.sleep):
        self.host = host
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)
        self.sleep = sleep

    def get(self, url, params=None, headers=None, text=False):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != self.host or parsed.username or parsed.password or parsed.port not in {None, 443}:
            raise AcquisitionError("endpoint_not_allowed")
        for attempt in range(3):
            retry = False
            try:
                with self.client.stream("GET", url, params=params, headers=headers, follow_redirects=False, timeout=15) as response:
                    status = response.status_code
                    if status in {401, 403}:
                        raise AcquisitionError("access_denied")
                    if 300 <= status < 400:
                        raise AcquisitionError("redirect_denied")
                    if status == 429 or 500 <= status < 600:
                        if attempt == 2:
                            raise AcquisitionError("rate_limited" if status == 429 else "upstream_unavailable")
                        after = response.headers.get("Retry-After", "")
                        try:
                            delay = max(0, (parsedate_to_datetime(after) - datetime.now(timezone.utc)).total_seconds()) if after and not after.isdigit() else float(after) if after.isdigit() else 2 ** attempt
                        except (ValueError, TypeError, OverflowError):
                            delay = 2 ** attempt
                        if delay > 5:
                            raise AcquisitionError("retry_after_exceeds_pilot_limit")
                        retry = True
                    elif status != 200:
                        raise AcquisitionError("upstream_http_error")
                    else:
                        body = bytearray()
                        for chunk in response.iter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_BYTES:
                                raise AcquisitionError("response_too_large")
                        if text:
                            return body.decode("utf-8", errors="replace")
                        try:
                            import json
                            return json.loads(body)
                        except (ValueError, RecursionError):
                            raise AcquisitionError("invalid_json") from None
            except httpx.ProxyError:
                raise AcquisitionError("proxy_or_network_denied") from None
            except httpx.TransportError:
                if attempt == 2:
                    raise AcquisitionError("transport_unavailable") from None
                retry, delay = True, 2 ** attempt
            if retry:
                self.sleep(delay + random.uniform(0, 0.2))
        raise AcquisitionError("retry_exhausted")

    def close(self):
        self.client.close()
