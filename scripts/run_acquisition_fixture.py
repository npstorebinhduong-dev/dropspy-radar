"""Reproducible synthetic benchmark + v0.2 import proof in an isolated memory DB."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from app.acquisition.adapters import FileDatasetAdapter, registry_gate
from app.acquisition.benchmark import benchmark, export_import, product_links, write_artifact
from app.acquisition.contracts import Access, Query
from app.data_import import ImportOptions, create_preview, process_job, start_import
from app.models import Ad, Base, RawEvidence
from app.sources import seed_sources

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / "docs/acquisition/sources.example.json").read_text())["fixture"]
    access = Access.model_validate(config["access"])
    query = Query.model_validate(config["dataset_query"])
    adapter = FileDatasetAdapter(access, ROOT / "apps/api" / config["filename"], dataset_query=query)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        seed_sources(session)
        session.commit()
        result = benchmark(adapter, query, ROOT / "docs/acquisition/evidence/fixture-benchmark.json", lambda a, q: registry_gate(session, a, q))
        exported = export_import(result)
        write_artifact(ROOT / "docs/acquisition/evidence/fixture-import.json", exported)
        payload = json.dumps(exported).encode()
        options = ImportOptions(source_id="demo", dataset_id="phase3a-fixture", data_label="DEMO", corpus="demo")
        job = create_preview(session, payload, "fixture.json", options)
        start_import(session, job["id"])
        process_job(job["id"], factory)
        replay = create_preview(session, payload, "fixture.json", options)
        proof = {"synthetic": True, "storage": "isolated in-memory SQLite, not application DB", "ads": session.scalar(select(func.count()).select_from(Ad)), "raw_evidence": session.scalar(select(func.count()).select_from(RawEvidence)), "real_ads": session.scalar(select(func.count()).select_from(Ad).where(Ad.is_demo.is_(False))), "replay_same_job": replay["id"] == job["id"], "product_url_groups": len(product_links(result["records"])), "benchmark": result["summary"]}
        assert proof["ads"] == 2 and proof["real_ads"] == 0 and proof["replay_same_job"]
        write_artifact(ROOT / "docs/acquisition/evidence/fixture-import-proof.json", proof)
        print(json.dumps(proof, indent=2))
    engine.dispose()


if __name__ == "__main__":
    main()
