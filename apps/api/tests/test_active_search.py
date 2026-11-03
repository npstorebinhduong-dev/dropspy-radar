"""Active discovery uses synthetic fixtures/mocks only; never contacts a platform."""

import json
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.analysis import analyze, status_evidence
from app.collectors.demo import DemoCollector
from app.collectors.meta_public import PublicSourceError, library_url, parse_public_page
from app.import_ads import AuthorizedDataset, import_dataset
from app.models import Ad, AdProvenance, Creative

# Reuse isolated SQLite fixtures, not the running application database.


def dataset(source="licensed-panel", **updates):
    record = DemoCollector().collect()[0].model_dump(mode="json") | {"is_demo": False}
    return AuthorizedDataset.model_validate(
        {
            "source_id": source,
            "kind": "authorized_file",
            "corpus": "paid_ad",
            "permission_attested": True,
            "rights_reference": "Unit-test synthetic dataset only",
            "records": [record],
        }
        | updates
    )


def test_search_creative_advertiser_domain_and_active(client, session):
    ad = session.scalar(select(Ad).where(Ad.source_id == "demo-1"))
    session.add(Creative(ad_id=ad.id, fingerprint="test-only", content={"text": "Solar garden lights — 20% off. Shop now!"}))
    session.commit()
    assert client.get("/ads?q=solar%20garden%20lights&status=active").json()["total"] == 1
    assert client.get("/ads?q=Blend%20%26%20Go").json()["total"] == 1
    assert client.get("/ads?q=pawsociety.example").json()["total"] == 2
    assert client.get("/ads?status=active").json()["total"] == 11
    assert client.get("/ads?q=%25&status=active").json()["total"] == 1  # literal % in one creative
    assert client.get("/ads?detected_after=2026-11-01T00:00:00&detected_before=2026-01-01T00:00:00").status_code == 422


def test_freshness_span_and_sort(client):
    result = client.get("/ads?sort=longest&min_observed_days=30").json()
    assert result["items"][0]["source_id"] == "demo-12"
    assert all((datetime.fromisoformat(a["last_seen"]) - datetime.fromisoformat(a["first_seen"])).days >= 30 for a in result["items"])
    counts = [len(a["creatives"]) for a in client.get("/ads?sort=creative_count").json()["items"]]
    assert counts == sorted(counts, reverse=True)
    assert client.get("/ads?observed_within_days=0").status_code == 422
    assert client.get("/ads?observed_within_days=7").json()["live_search"] is False


def test_analysis_matches_evidence_and_missing_outcomes(client, session):
    ad = session.scalar(select(Ad).where(Ad.source_id == "demo-1"))
    text = "Tired of clutter? Portable kit, 20% off with free shipping. Shop now!"
    session.add(Creative(ad_id=ad.id, fingerprint="analysis-only", content={"text": text}))
    session.commit()
    response = client.get(f"/ads/{ad.id}/analysis")
    assert response.status_code == 200
    body = response.json()
    assert {s["label"] for s in body["signals"]} >= {"problem_solution", "convenience", "discount", "free_shipping", "shop_now"}
    for signal in body["signals"]:
        creative = client.get("/ads?q=blender").json()["items"][0]["creatives"][signal["creative_index"]]["text"]
        assert creative[signal["start"] : signal["end"]] == signal["excerpt"]
    assert all(value is None for value in body["business_outcomes"].values())
    assert body["status_evidence"]["currently_running_verified"] is False
    assert client.get("/ads/99999/analysis").status_code == 404


def test_stale_active_is_not_silently_verified(session):
    import_dataset(session, dataset())
    ad = session.scalar(select(Ad))
    ad.last_seen = datetime(2020, 1, 1)
    evidence = status_evidence(ad, now=datetime(2026, 11, 3))
    assert evidence["freshness"] == "stale" and evidence["reported_status"] == "active"
    assert not evidence["currently_running_verified"]
    result = analyze(ad, [], 1, 1)
    assert any("out of date" in warning for warning in result["limitations"])


def test_import_gate_namespace_and_replay(session):
    for update in [{"permission_attested": False}, {"corpus": "organic_post"}, {"rights_reference": " " * 20}]:
        with pytest.raises(ValueError):
            dataset(**update)
    import_dataset(session, dataset("provider-a"))
    import_dataset(session, dataset("provider-a"))
    import_dataset(session, dataset("provider-b"))
    session.commit()
    assert session.scalar(select(func.count()).select_from(Ad)) == 2
    assert session.scalar(select(func.count()).select_from(AdProvenance)) == 2
    bad = dataset("provider-a", rights_reference="Conflicting rights reference")
    with pytest.raises(ValueError):
        import_dataset(session, bad)
    session.rollback()
    assert session.scalar(select(func.count()).select_from(Ad)) == 2


def public_fixture(**updates):
    row = {
        "ad_archive_id": "123456",
        "page_name": "Synthetic Fixture Advertiser",
        "is_active": True,
        "publisher_platform": ["FACEBOOK", "INSTAGRAM"],
        "start_date": 1700000000,
        "snapshot": {
            "title": "Fixture portable blender",
            "body": {"text": "Portable blender. Shop now!"},
            "link_url": "https://example.com/products/blender",
            "images": [{"original_image_url": "https://example.com/creative.jpg"}],
        },
    } | updates
    return '<html><script type="application/json">' + json.dumps({"data": {"edges": [{"node": {"collated_results": [row, row]}}]}}) + "</script></html>"


def test_public_parser_dedup_active_and_no_fabricated_landing():
    result = parse_public_page(public_fixture(), "US", now=datetime(2026, 11, 3))
    assert len(result["records"]) == 1
    assert result["records"][0].first_seen == datetime(2026, 11, 3)  # observation != source delivery start
    assert result["details"]["123456"]["media_urls"] == ["https://example.com/creative.jpg"]
    assert not result["records"][0].is_demo
    assert not parse_public_page(public_fixture(is_active=False), "US")["records"]
    assert not parse_public_page(public_fixture(snapshot={"title": "Missing landing"}), "US")["records"]
    no_media = {"title": "Fixture", "link_url": "https://example.com", "cards": None, "videos": None, "images": None}
    assert len(parse_public_page(public_fixture(snapshot=no_media), "US")["records"]) == 1
    assert "country=US" in library_url("solar garden lights", "US")


@pytest.mark.parametrize("html", ['<form id="login_form">', '<input name="captcha">', "<html>JavaScript shell</html>"])
def test_public_access_gates_and_unsupported_shell_fail_closed(html):
    with pytest.raises(PublicSourceError):
        parse_public_page(html, "US")


def test_public_discovery_gate_and_mocked_live_flow(client, session, monkeypatch):
    import app.main as main

    assert client.post("/discovery/meta", json={"q": "portable blender"}).status_code == 409
    monkeypatch.setattr(main, "MODE", "live")
    monkeypatch.setenv("ENABLE_META_PUBLIC_COLLECTION", "1")
    monkeypatch.setattr(main, "_last_discovery", 0)
    monkeypatch.setattr(main, "fetch_public_page", lambda q, country: parse_public_page(public_fixture(), country))
    result = client.post("/discovery/meta", json={"q": "portable blender", "country": "US"})
    assert result.status_code == 200, result.text
    assert result.json()["records_processed"] == 1
    ads = client.get("/ads?status=active").json()["items"]
    assert len(ads) == 1 and not ads[0]["is_demo"]
    details = client.get(f"/ads/{ads[0]['id']}/analysis").json()
    assert details["source"]["kind"] == "public_page"
    assert client.post("/discovery/meta", json={"q": "portable blender"}).status_code == 429
