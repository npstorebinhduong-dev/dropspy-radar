"""Real PostgreSQL integration in disposable schemas; never rollback the app DB."""

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import sessionmaker

from app.data_import import ImportOptions, create_preview, process_job, start_import
from app.models import Ad, Advertiser, CollectionQuery, CollectionRun, Creative, ImportJob, Observation, RawEvidence

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Set TEST_DATABASE_URL for isolated PostgreSQL migration/concurrency tests")


def config(conn):
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.attributes["connection"] = conn
    return cfg


@pytest.fixture()
def pg():
    admin = create_engine(URL)
    schema = "coretest_" + uuid.uuid4().hex
    with admin.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_engine(URL, connect_args={"options": f"-csearch_path={schema}"}, pool_size=10, max_overflow=5)
    try:
        with engine.begin() as conn:
            command.upgrade(config(conn), "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


def test_postgres_upgrade_rollback_reupgrade(pg):
    with pg.begin() as conn:
        assert "raw_evidence" in inspect(conn).get_table_names()
        command.downgrade(config(conn), "0001_legacy")
        assert "sources" not in inspect(conn).get_table_names() and "ads" in inspect(conn).get_table_names()
        command.upgrade(config(conn), "head")
        assert conn.scalar(text("SELECT count(*) FROM sources")) == 7
        command.downgrade(config(conn), "base")
        assert "ads" not in inspect(conn).get_table_names()
        command.upgrade(config(conn), "head")
        assert "raw_evidence" in inspect(conn).get_table_names()


def test_adopts_unversioned_v01_without_losing_saved_ads(pg):
    with pg.begin() as conn:
        command.downgrade(config(conn), "0001_legacy")
        conn.execute(
            text(
                "INSERT INTO ads (source_id,platform,advertiser,title,country,status,landing_url,landing_domain,source_url,first_seen,last_seen,is_demo,saved) VALUES ('legacy','facebook','Legacy','Keep me','US','active','','','',now(),now(),true,true)"
            )
        )
        conn.execute(text("DELETE FROM alembic_version"))
        command.upgrade(config(conn), "head")
        row = conn.execute(text("SELECT title,saved,registry_source_id FROM ads WHERE source_id='legacy'")).one()
        assert row == ("Keep me", True, "demo")


def test_concurrent_upsert_and_idempotent_evidence(pg):
    factory = sessionmaker(pg)
    opts = ImportOptions(source_id="demo", dataset_id="concurrent", data_label="DEMO", corpus="demo", completeness="partial")
    ids = []
    for index in range(8):
        row = {
            "external_id": "same-ad",
            "platform": "facebook",
            "advertiser": "Fixture concurrent",
            "advertiser_id": "same-page",
            "title": f"Observation {index}",
            "country": "US",
            "status": "active",
            "observed_at": f"2026-10-{index + 1:02d}T00:00:00Z",
            "creative_text": "Identical creative across observations",
        }
        with factory() as session:
            job = create_preview(session, json.dumps({"fixture_only": True, "records": [row]}).encode(), "concurrent.json", opts)
            start_import(session, job["id"])
            ids.append(job["id"])
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda id: process_job(id, factory), ids))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Ad)) == 1
        assert session.scalar(select(func.count()).select_from(Advertiser)) == 1
        assert session.scalar(select(func.count()).select_from(Creative)) == 1
        assert session.scalar(select(func.count()).select_from(Observation)) == 8
        assert session.scalar(select(func.count()).select_from(RawEvidence)) == 8
        assert session.scalar(select(func.count()).select_from(CollectionRun)) == 8
        assert session.scalar(select(func.count()).select_from(CollectionQuery)) == 1
        assert all(j.status == "completed" for j in session.scalars(select(ImportJob)))
        ad = session.scalar(select(Ad))
        assert ad.title == "Observation 7" and ad.first_seen.day == 1 and ad.last_seen.day == 8
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda id: process_job(id, factory), ids))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RawEvidence)) == 8


def test_concurrent_same_file_preview_is_one_job(pg):
    factory = sessionmaker(pg)
    payload = json.dumps(
        {"fixture_only": True, "records": [{"external_id": "one", "platform": "tiktok", "advertiser": "Fixture", "country": "US", "observed_at": "2026-10-01T00:00:00Z"}]}
    ).encode()
    opts = ImportOptions(source_id="demo", dataset_id="preview-race", data_label="DEMO", corpus="demo")

    def upload(_):
        with factory() as session:
            return create_preview(session, payload, "same.json", opts)["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(upload, range(8)))
    assert len(set(ids)) == 1
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ImportJob)) == 1
