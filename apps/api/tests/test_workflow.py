import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["MODE"] = "demo"

import pytest
from sqlalchemy import func, select

from app.collectors.base import AccessNotConfigured, AdRecord
from app.collectors.demo import DemoCollector
from app.collectors.meta import MetaCollector
from app.collectors.tiktok import TikTokCollector
from app.ingest import collect_with_retry, ingest
from app.models import Ad, Creative, Observation
from app.scoring import score


def test_fixture_schema_and_demo_label():
    rows = DemoCollector().collect()
    assert len(rows) == 12
    assert all(r.is_demo and r.source_url.host == "example.com" for r in rows)
    with pytest.raises(ValueError):
        AdRecord.model_validate(rows[0].model_dump() | {"last_seen": "2000-01-01T00:00:00"})


def test_ingestion_deduplicates_and_retains_history(session):
    rows = DemoCollector().collect()
    ingest(session, rows)
    ingest(session, rows)
    assert session.scalar(select(func.count()).select_from(Ad)) == 12
    assert session.scalar(select(func.count()).select_from(Observation)) == 12
    assert session.scalar(select(func.count()).select_from(Creative)) == sum(len(r.creatives) for r in rows)
    changed = rows[0].model_copy(update={"last_seen": rows[0].last_seen.replace(day=3), "status": "inactive"})
    ingest(session, [changed])
    ingest(session, [rows[0]])  # stale data cannot overwrite latest status
    ad = session.scalar(select(Ad).where(Ad.source_id == rows[0].source_id))
    assert ad.last_seen.day == 3 and ad.status == "inactive"
    assert session.scalar(select(func.count()).select_from(Observation)) == 13


def test_demo_real_data_isolation(session, client):
    real = DemoCollector().collect()[0].model_copy(update={"is_demo": False})
    ingest(session, [real])
    assert session.scalar(select(func.count()).select_from(Ad)) == 13
    assert client.get("/ads?country=US").json()["total"] == 10
    live_id = session.scalar(select(Ad.id).where(Ad.is_demo.is_(False)))
    assert client.put(f"/ads/{live_id}/saved?saved=true").status_code == 404


def test_search_filter_sort_pagination(client):
    result = client.get("/ads?country=US&platform=meta&page_size=2&sort=oldest").json()
    assert result["total"] == 7
    assert len(result["items"]) == 2
    second = client.get("/ads?country=US&platform=meta&page_size=2&page=2&sort=oldest").json()
    assert {r["id"] for r in result["items"]}.isdisjoint({r["id"] for r in second["items"]})
    assert client.get("/ads?q=blender&advertiser=blend&domain=example&status=active").json()["total"] == 1
    assert client.get("/ads?detected_after=2026-10-18T00:00:00").json()["total"] == 2
    assert client.get("/ads?detected_before=2026-09-01T00:00:00").json()["total"] == 1
    assert client.get("/ads?page=0").status_code == 422
    assert client.get("/ads?sort=invalid").status_code == 422
    assert client.get("/ads?q=%25").json()["total"] == 0


def test_saved_ads_observations_and_overview(client):
    ad = client.get("/ads").json()["items"][0]
    assert client.put(f"/ads/{ad['id']}/saved?saved=true").json()["saved"]
    assert client.get("/ads?saved=true").json()["total"] == 1
    assert client.get("/overview").json()["saved_ads"] == 1
    assert len(client.get(f"/ads/{ad['id']}/observations").json()) == 1
    assert client.put("/ads/999/saved?saved=true").status_code == 404
    assert len(client.get("/competitors").json()) == 7
    assert client.get("/health").json()["status"] == "ok"


def test_score_evidence_and_caps(session):
    ingest(session, DemoCollector().collect())
    ad = session.scalar(select(Ad))
    result = score(ad, 900, 900)
    assert 0 <= result["value"] <= 100
    assert len(result["components"]) == 4
    assert all(m["source"] and m["evidence"] and m["confidence"] == "demo" for m in result["components"])
    assert result["components"][-1]["evidence"].startswith("HTTPS URL syntax only")


@pytest.mark.parametrize("collector", [MetaCollector(), TikTokCollector()])
def test_live_adapters_fail_closed(collector):
    with pytest.raises(AccessNotConfigured):
        collect_with_retry(collector, sleep=lambda _: pytest.fail("Access failures must not retry"))


def test_transient_retry_is_bounded():
    class Flaky:
        calls = 0

        def collect(self):
            self.calls += 1
            raise TimeoutError()

    collector = Flaky()
    delays = []
    with pytest.raises(TimeoutError):
        collect_with_retry(collector, sleep=delays.append)
    assert collector.calls == 3
    assert delays == [1, 2]


def test_ingest_normalizes_timezone(session):
    record = DemoCollector().collect()[0]
    shifted = AdRecord.model_validate(record.model_dump() | {"first_seen": "2026-10-24T19:00:00+07:00", "last_seen": "2026-11-02T19:00:00+07:00"})
    ingest(session, [shifted])
    ingest(session, [record])
    assert session.scalar(select(func.count()).select_from(Observation)) == 1
    assert session.scalar(select(Ad)).last_seen.hour == 12
