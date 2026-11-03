"""Functional smoke for the running Compose stack (host ports 3000 and 8000)."""

import json
from urllib.request import Request, urlopen


def call(path, method="GET"):
    with urlopen(
        Request("http://127.0.0.1:3000/api" + path, method=method), timeout=15
    ) as response:
        return json.load(response)


health = call("/health")
assert health["status"] == "ok" and health["mode"] == "demo"
result = call("/ads?country=US&platform=meta&page_size=2")
assert result["total"] == 7 and len(result["items"]) == 2
ad = result["items"][0]
assert ad["is_demo"] and len(ad["score"]["components"]) == 4
original = ad["saved"]
try:
    assert call(f"/ads/{ad['id']}/saved?saved=true", "PUT")["saved"]
    assert any(row["id"] == ad["id"] for row in call("/ads?saved=true")["items"])
    assert len(call(f"/ads/{ad['id']}/observations")) >= 1
finally:
    call(f"/ads/{ad['id']}/saved?saved={str(original).lower()}", "PUT")
assert call("/ads?platform=tiktok")["total"] == 4
assert len(call("/competitors")) == 7
with urlopen("http://127.0.0.1:3000", timeout=15) as response:
    page = response.read().decode()
    assert response.status == 200 and "DROPSpy" in page and "Discover what" in page
print(
    "PASS: Next.js page, same-origin API proxy, PostgreSQL search, filters, saved-ad roundtrip, observation history, scoring, TikTok, advertiser summary"
)
