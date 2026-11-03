import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.data_import import ImportOptions, process_job, start_import
from app.models import Ad, Advertiser, CollectionRun, Creative, ImportJob, Observation, RawEvidence
from app.sources import require_live_source

FIXTURES = Path(__file__).with_name("fixtures")


def options(**updates):
    return ImportOptions.model_validate(dict(source_id="demo", data_label="DEMO", corpus="demo", dataset_id="fixture-history", completeness="complete") | updates)


def upload(client, name="complete.json", opts=None, payload=None, mime="application/json"):
    return client.post("/v1/imports/preview", files={"file": (name, payload or (FIXTURES / name).read_bytes(), mime)}, data={"options": (opts or options()).model_dump_json()})


def finish(session, id):
    start_import(session, id)
    process_job(id, sessionmaker(bind=session.bind))
    session.expire_all()
    return session.get(ImportJob, id)


def test_json_preview_does_not_ingest_then_atomic_batches(client, session):
    before = session.scalar(select(func.count()).select_from(Ad))
    response = upload(client)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["valid_rows"] == 2 and data["status"] == "preview"
    assert session.scalar(select(func.count()).select_from(Ad)) == before
    job = finish(session, data["id"])
    assert job.status == "completed" and job.processed == 2
    assert session.scalar(select(func.count()).select_from(Ad)) == before + 2
    raw = session.scalars(select(RawEvidence).where(RawEvidence.job_id == job.id)).all()
    assert len(raw) == 2 and raw[0].source_id == "demo" and raw[0].raw_data["external_id"].startswith("fixture-")
    ad = session.get(Ad, raw[0].ad_id)
    assert ad.delivery_start and ad.delivery_start < ad.first_seen
    assert session.scalar(select(func.count()).select_from(Advertiser)) == 2
    assert client.get(f"/ads/{ad.id}/evidence?data_mode=demo").json()["total"] == 1
    assert client.get(f"/ads/{ad.id}/evidence?data_mode=real").status_code == 404


def test_duplicate_import_and_start_are_idempotent(client, session):
    first = upload(client).json()
    finish(session, first["id"])
    again = upload(client).json()
    assert again["id"] == first["id"] and again["status"] == "completed"
    process_job(first["id"], sessionmaker(bind=session.bind))
    assert session.scalar(select(func.count()).select_from(RawEvidence)) == 2
    assert session.scalar(select(func.count()).select_from(CollectionRun)) == 1


def test_csv_mapping_preview_and_import(client, session):
    mapping = dict(external_id="Ad ID", platform="Channel", advertiser="Brand", title="Product", country="Market", status="State", observed_at="Seen", creative_text="Copy")
    result = upload(client, "mapped.csv", options(mapping=mapping), mime="text/csv")
    assert result.status_code == 200, result.text
    assert result.json()["valid_rows"] == 1
    job = finish(session, result.json()["id"])
    row = session.scalar(select(RawEvidence).where(RawEvidence.job_id == job.id))
    assert row.raw_data["Product"] == "Portable blender" and row.normalized_data["title"] == "Portable blender"


def test_complete_partial_capped_never_infer_stopped(client, session):
    for kind in ["complete", "partial", "capped"]:
        result = upload(client, kind + ".json", options(completeness=kind)).json()
        finish(session, result["id"])
    ads = session.scalars(select(Ad).where(Ad.external_id.is_not(None))).all()
    assert len(ads) == 2 and all(ad.status == "active" for ad in ads)
    assert {run.completeness for run in session.scalars(select(CollectionRun))} == {"complete", "partial", "capped"}
    assert session.scalar(select(func.count()).select_from(Observation).where(Observation.ad_id == ads[0].id)) >= 1


def test_rights_fixture_country_source_and_schema_gates(client, session):
    real = ImportOptions(
        source_id="authorized-file", data_label="REAL", corpus="paid_ad", permission_attested=True, rights_reference="Unit test scope only; synthetic test execution"
    )
    assert upload(client, opts=real).status_code == 422  # marked fixture cannot become REAL
    assert upload(client, opts=options(source_id="missing-source")).status_code == 422
    assert upload(client, opts=options(source_id="tiktok-ad-library")).status_code == 422
    raw = json.loads((FIXTURES / "complete.json").read_text())
    raw["records"][0]["country"] = "BR"
    result = upload(client, payload=json.dumps(raw).encode()).json()
    assert result["error_count"] == 1 and result["valid_rows"] == 1
    result = upload(client, name="rows.txt", payload=b"not a file").status_code
    assert result == 422
    assert upload(client, payload=b"{}").status_code == 422
    assert upload(client, payload=b"[").status_code == 422
    assert upload(client, payload=b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    assert upload(client, mime="application/zip").status_code == 415
    with pytest.raises(ValueError):
        ImportOptions(source_id="authorized-file", data_label="REAL", corpus="paid_ad")
    with pytest.raises(ValueError):
        require_live_source(session, "meta-ad-library", "US", ["keyword"])


def test_row_errors_allow_explicit_valid_only_import(client, session):
    raw = json.loads((FIXTURES / "complete.json").read_text())
    raw["records"][1]["observed_at"] = "bad-date"
    data = upload(client, payload=json.dumps(raw).encode()).json()
    assert data["error_count"] == 1 and data["errors"][0]["row"] == 2
    report = client.get(f"/v1/imports/{data['id']}/errors")
    assert report.status_code == 200 and report.json()["errors"][0]["row"] == 2
    assert "attachment" in report.headers["content-disposition"]
    job = finish(session, data["id"])
    assert job.status == "completed_with_errors" and job.processed == 2
    run = session.get(CollectionRun, job.run_id)
    assert run.completeness == "partial"


def test_real_demo_isolation_and_search_filters(client, session):
    raw = json.loads((FIXTURES / "complete.json").read_text())
    # Synthetic test records in the isolated DB exercise REAL behavior; never seed these into application data.
    raw.pop("fixture_only")
    real = ImportOptions(
        source_id="authorized-file", data_label="REAL", corpus="paid_ad", permission_attested=True, rights_reference="Unit test synthetic records in isolated test DB"
    )
    data = upload(client, opts=real, payload=json.dumps(raw).encode()).json()
    finish(session, data["id"])
    assert client.get("/ads?data_mode=real&market=US&platform=meta&q=solar").json()["total"] == 1
    assert client.get("/ads?data_mode=real&market=EU&platform=tiktok").json()["total"] == 1
    assert client.get("/ads?data_mode=demo&q=Fixture").json()["total"] == 0
    result = client.get("/ads?data_mode=real&source=authorized-file").json()
    assert result["total"] == 2 and all(a["data_label"] == "REAL" for a in result["items"])
    ad = result["items"][0]
    assert client.put(f"/ads/{ad['id']}/saved?saved=true&data_mode=real").status_code == 200
    assert client.get("/ads?data_mode=real&saved=true").json()["total"] == 1
    assert client.get(f"/ads/{ad['id']}/analysis?data_mode=real").status_code == 200
    assert client.get(f"/ads/{ad['id']}/evidence?data_mode=real").json()["items"][0]["rights_reference"] == real.rights_reference
    assert client.get(f"/ads/{ad['id']}/evidence?data_mode=demo").status_code == 404


def test_missing_values_stay_unknown_and_no_urls_fetched(client, session, monkeypatch):
    import httpx

    monkeypatch.setattr(httpx.Client, "get", lambda *args, **kwargs: pytest.fail("Importer fetched an external URL"))
    raw = {"fixture_only": True, "records": [dict(external_id="unknown-row", platform="facebook", advertiser="Fixture Unknown", country="US", observed_at="2026-10-02T00:00:00Z")]}
    result = upload(client, payload=json.dumps(raw).encode()).json()
    job = finish(session, result["id"])
    ad = session.scalar(select(Ad).where(Ad.external_id == "unknown-row"))
    assert ad.status == "unknown" and ad.landing_url == "" and ad.delivery_start is None
    assert session.scalar(select(func.count()).select_from(Creative).where(Creative.ad_id == ad.id)) == 0
    assert job.status == "completed"


def test_preview_expiry_retention_and_safe_restart(client, session):
    import threading
    from datetime import timedelta
    from app.data_import import now_utc, purge_expired

    data = upload(client).json()
    job = session.get(ImportJob, data["id"])
    job.expires_at = now_utc() - timedelta(seconds=1)
    session.commit()
    purge_expired(session)
    session.refresh(job)
    assert job.status == "expired" and job.raw_rows == []
    recreated = upload(client).json()
    assert recreated["id"] == data["id"] and recreated["status"] == "preview" and recreated["valid_rows"] == 2
    start_import(session, data["id"])
    stop = threading.Event()
    stop.set()
    process_job(data["id"], sessionmaker(bind=session.bind), stop=stop)
    session.expire_all()
    job = session.get(ImportJob, data["id"])
    assert job.status == "queued" and job.cursor == 0 and job.run_id
    initial_run = job.run_id
    process_job(job.id, sessionmaker(bind=session.bind))
    session.expire_all()
    job = session.get(ImportJob, data["id"])
    assert job.status == "completed" and job.run_id == initial_run
    for row in session.scalars(select(RawEvidence)):
        row.retention_until = now_utc() - timedelta(seconds=1)
    job.created_at = now_utc() - timedelta(days=31)
    session.commit()
    purge_expired(session)
    assert session.scalar(select(func.count()).select_from(RawEvidence)) == 0
    session.refresh(job)
    assert job.raw_rows == [] and job.normalized_rows == [] and job.cursor == 2
    assert client.get(f"/v1/imports/{job.id}").json()["valid_rows"] == 2


def test_meta_platform_and_case_normalization(client, session):
    payload = json.dumps(
        {
            "fixture_only": True,
            "records": [dict(external_id="fixture-meta", platform="META", advertiser="Fixture Brand", country="us", status="ACTIVE", observed_at="2026-10-01T00:00:00Z")],
        }
    ).encode()
    result = upload(client, payload=payload).json()
    assert result["valid_rows"] == 1
    finish(session, result["id"])
    found = client.get("/ads?platform=meta&q=Fixture%20Brand&status=active").json()
    assert found["total"] == 1 and found["items"][0]["platform"] == "meta"


def test_legacy_creative_fingerprint_is_preserved(session):
    import hashlib
    from app.collectors.demo import DemoCollector
    from app.ingest import ingest

    records = DemoCollector().collect()
    ingest(session, records)
    ad = session.scalar(select(Ad).where(Ad.source_id == records[0].source_id))
    fingerprint = hashlib.sha256(records[0].creatives[0].encode()).hexdigest()
    assert session.scalar(select(Creative.id).where(Creative.ad_id == ad.id, Creative.fingerprint == fingerprint))
    before = session.scalar(select(func.count()).select_from(Creative))
    ingest(session, records)
    assert session.scalar(select(func.count()).select_from(Creative)) == before
