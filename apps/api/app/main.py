import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session as DBSession

from .analysis import analyze, status_evidence, utc_now
from .collectors.demo import DemoCollector
from .collectors.meta_public import PublicSourceError, fetch_public_page, library_url
from .import_ads import AuthorizedDataset, import_dataset
from .db import Base, Session, engine
from .ingest import collect_with_retry, ingest
from .models import Ad, AdProvenance, Creative, Observation, RawEvidence, Source
from .sources import EU_COUNTRIES, require_live_source, seed_sources
from .data_routes import router as data_router
from .data_import import start_worker
from .migrate import upgrade_database
from .scoring import score

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
MODE = os.getenv("MODE", "demo")
if MODE not in {"demo", "live"}:
    raise RuntimeError("MODE must be demo or live")


@asynccontextmanager
async def lifespan(app):
    if engine.dialect.name == "postgresql":
        upgrade_database()
    else:
        # SQLite is limited to isolated tests/fresh local demos. PostgreSQL uses migrations.
        Base.metadata.create_all(engine)
    with Session() as session:
        seed_sources(session)
        session.commit()
    if MODE == "demo":
        with Session() as session:
            ingest(session, collect_with_retry(DemoCollector()))
    worker = start_worker() if os.getenv("IMPORT_WORKER_ENABLED", "1") == "1" else None
    yield
    if worker:
        worker[0].set()
        worker[1].join(timeout=5)


app = FastAPI(title="DROPSpy Radar", version="0.2.0", lifespan=lifespan)


def db():
    with Session() as session:
        yield session


app.include_router(data_router)


def current_ads(data_mode=None):
    return select(Ad).where(Ad.is_demo == ((data_mode or MODE) == "demo"))


def serialize(session, ad):
    creatives = session.scalars(select(Creative).where(Creative.ad_id == ad.id)).all()
    recurrence = session.scalar(select(func.count()).select_from(Ad).where(Ad.advertiser == ad.advertiser, Ad.is_demo == ad.is_demo))
    source = session.get(Source, ad.registry_source_id) if ad.registry_source_id else None
    label = "DEMO" if ad.is_demo else "REAL" if source and source.approval_status in {"approved", "operator_attested"} and ad.corpus != "unknown" else "UNKNOWN"
    return {c.name: getattr(ad, c.name) for c in Ad.__table__.columns} | {
        "data_label": label,
        "source_name": source.name if source else "Legacy / unknown",
        "creatives": [c.content for c in creatives],
        "score": score(ad, len(creatives), recurrence),
        "status_evidence": status_evidence(ad),
    }


@app.get("/health")
def health(session: DBSession = Depends(db)):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "mode": MODE, "live_collectors": "disabled"}


@app.get("/ads")
def ads(
    q: str = Query("", max_length=200),
    country: str = "",
    market: Literal["", "US", "EU"] = "",
    data_mode: Literal["demo", "real"] | None = None,
    source: str = "",
    platform: Literal["", "meta", "facebook", "instagram", "reels", "tiktok"] = "",
    advertiser: str = "",
    domain: str = "",
    status: Literal["", "active", "inactive", "unknown"] = "",
    detected_after: datetime | None = None,
    detected_before: datetime | None = None,
    saved: bool = False,
    observed_within_days: int | None = Query(None, ge=1, le=365),
    min_observed_days: int = Query(0, ge=0, le=3650),
    sort: Literal["newest", "oldest", "advertiser", "last_seen", "longest", "creative_count"] = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(9, ge=1, le=100),
    session: DBSession = Depends(db),
):
    stmt = current_ads(data_mode)
    if source:
        stmt = stmt.where(Ad.registry_source_id == source)
    if market:
        stmt = stmt.where(Ad.country.in_(EU_COUNTRIES) if market == "EU" else Ad.country == "US")
    if q.strip():
        term = q.strip()
        creative_match = select(Creative.id).where(Creative.ad_id == Ad.id, Creative.content["text"].as_string().icontains(term, autoescape=True)).exists()
        stmt = stmt.where(
            or_(Ad.title.icontains(term, autoescape=True), Ad.advertiser.icontains(term, autoescape=True), Ad.landing_domain.icontains(term, autoescape=True), creative_match)
        )
    for column, value in [(Ad.advertiser, advertiser), (Ad.landing_domain, domain)]:
        if value:
            stmt = stmt.where(column.icontains(value, autoescape=True))
    if country:
        stmt = stmt.where(Ad.country == country.upper())
    if platform:
        stmt = stmt.where(Ad.platform.in_(["meta", "facebook", "instagram", "reels"]) if platform == "meta" else Ad.platform == platform)
    if status:
        stmt = stmt.where(Ad.status == status)

    def naive_utc(value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

    if detected_after and detected_before and naive_utc(detected_before) < naive_utc(detected_after):
        raise HTTPException(422, "detected_before must not precede detected_after")
    if observed_within_days:
        stmt = stmt.where(Ad.last_seen >= utc_now() - timedelta(days=observed_within_days))
    if detected_after:
        stmt = stmt.where(Ad.first_seen >= naive_utc(detected_after))
    if detected_before:
        stmt = stmt.where(Ad.first_seen <= naive_utc(detected_before))
    if saved:
        stmt = stmt.where(Ad.saved.is_(True))
    # Epoch math differs across SQLite test/local mode and PostgreSQL runtime.
    if session.bind.dialect.name == "sqlite":
        span = func.julianday(Ad.last_seen) - func.julianday(Ad.first_seen)
    else:
        span = func.extract("epoch", Ad.last_seen - Ad.first_seen) / 86400
    if min_observed_days:
        stmt = stmt.where(span >= min_observed_days)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    creative_count = select(func.count(Creative.id)).where(Creative.ad_id == Ad.id).correlate(Ad).scalar_subquery()
    ordering = {
        "newest": Ad.first_seen.desc(),
        "oldest": Ad.first_seen.asc(),
        "advertiser": Ad.advertiser.asc(),
        "last_seen": Ad.last_seen.desc(),
        "longest": span.desc(),
        "creative_count": creative_count.desc(),
    }[sort]
    result = session.scalars(stmt.order_by(ordering, Ad.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [serialize(session, ad) for ad in result],
        "total": total,
        "page": page,
        "page_size": page_size,
        "mode": data_mode or MODE,
        "scope": "stored observations",
        "live_search": False,
    }


def get_ad(session, ad_id, data_mode=None):
    ad = session.scalar(current_ads(data_mode).where(Ad.id == ad_id))
    if ad is None:
        raise HTTPException(404, "Ad not found")
    return ad


@app.put("/ads/{ad_id}/saved")
def save_ad(ad_id: int, saved: bool, data_mode: Literal["demo", "real"] | None = None, session: DBSession = Depends(db)):
    ad = get_ad(session, ad_id, data_mode)
    ad.saved = saved
    session.commit()
    return {"id": ad.id, "saved": ad.saved}


@app.get("/ads/{ad_id}/observations")
def observations(ad_id: int, data_mode: Literal["demo", "real"] | None = None, session: DBSession = Depends(db)):
    get_ad(session, ad_id, data_mode)
    return [
        {"observed_at": row.observed_at, "status": row.status, "source_url": row.source_url}
        for row in session.scalars(select(Observation).where(Observation.ad_id == ad_id).order_by(Observation.observed_at))
    ]


@app.get("/overview")
def overview(data_mode: Literal["demo", "real"] | None = None, session: DBSession = Depends(db)):
    rows = session.scalars(current_ads(data_mode)).all()
    return {
        "total_ads": len(rows),
        "advertisers": len({a.advertiser for a in rows}),
        "active_ads": sum(a.status == "active" for a in rows),
        "saved_ads": sum(a.saved for a in rows),
        "mode": data_mode or MODE,
    }


@app.get("/competitors")
def competitors(data_mode: Literal["demo", "real"] | None = None, session: DBSession = Depends(db)):
    rows = session.execute(
        select(Ad.advertiser, func.count(Ad.id), func.min(Ad.first_seen), func.max(Ad.last_seen))
        .where(Ad.is_demo == ((data_mode or MODE) == "demo"))
        .group_by(Ad.advertiser)
        .order_by(func.count(Ad.id).desc())
    ).all()
    return [
        {"advertiser": r[0], "ad_count": r[1], "first_seen": r[2], "last_seen": r[3], "source": "demo fixture" if (data_mode or MODE) == "demo" else "stored observations"}
        for r in rows
    ]


@app.get("/ads/{ad_id}/analysis")
def analysis(ad_id: int, data_mode: Literal["demo", "real"] | None = None, session: DBSession = Depends(db)):
    ad = get_ad(session, ad_id, data_mode)
    creatives = [row.content for row in session.scalars(select(Creative).where(Creative.ad_id == ad_id).order_by(Creative.id))]
    count = session.scalar(select(func.count()).select_from(Observation).where(Observation.ad_id == ad_id))
    related = session.scalar(select(func.count()).select_from(Ad).where(Ad.advertiser == ad.advertiser, Ad.is_demo == ad.is_demo))
    origin = session.get(AdProvenance, ad_id)
    provenance = (
        {
            "source_id": origin.source_id,
            "kind": origin.details.get("kind", "authorized_file"),
            "details": origin.details,
            "rights_reference": origin.rights_reference,
            "attestation": "operator-declared, not independently verified",
            "imported_at": origin.imported_at,
            "source_url": ad.source_url,
        }
        if origin
        else None
    )
    if provenance is None and ad.registry_source_id:
        source = session.get(Source, ad.registry_source_id)
        if source:
            provenance = {
                "source_id": source.id,
                "kind": source.kind,
                "source_url": ad.source_url,
                "approval_status": source.approval_status,
                "attestation": "operator-declared dataset permission; not verification of ad performance",
            }
    return analyze(ad, creatives, count, related, provenance)


class PublicSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str = Field(min_length=2, max_length=100)
    country: str = Field(default="US", pattern="^[A-Z]{2}$")


_discovery_lock = threading.Lock()
_last_discovery = 0.0


@app.post("/discovery/meta")
def discover_meta(query: PublicSearchQuery, session: DBSession = Depends(db)):
    global _last_discovery
    search_url = library_url(query.q, query.country)
    if MODE != "live" or os.getenv("ENABLE_META_PUBLIC_COLLECTION") != "1":
        raise HTTPException(409, detail={"message": "Public search requires MODE=live and ENABLE_META_PUBLIC_COLLECTION=1. Demo stays separate.", "source_url": search_url})
    try:
        require_live_source(session, "meta-ad-library", query.country, ["keyword", "country", "status"])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    if not _discovery_lock.acquire(blocking=False):
        raise HTTPException(429, "A public-page search is already running")
    try:
        if time.monotonic() - _last_discovery < 30:
            raise HTTPException(429, "Wait 30 seconds between public-page searches")
        _last_discovery = time.monotonic()
        try:
            result = fetch_public_page(query.q, query.country)
        except PublicSourceError as exc:
            raise HTTPException(503, detail={"message": str(exc), "source_url": search_url}) from None
        dataset = (
            AuthorizedDataset(
                source_id="meta-public-page",
                kind="authorized_file",
                corpus="paid_ad",
                rights_reference="Operator-enabled public-page access; retain according to applicable source terms",
                permission_attested=True,
                records=result["records"],
            )
            if result["records"]
            else None
        )
        try:
            if dataset:
                import_dataset(session, dataset)
                for record in result["records"]:
                    ad = session.scalar(select(Ad).where(Ad.source_id == f"meta-public-page:{record.source_id}", Ad.platform == record.platform, Ad.is_demo.is_(False)))
                    session.get(AdProvenance, ad.id).details = result["details"][record.source_id]
                    ad.registry_source_id, ad.corpus = "meta-ad-library", "paid_ad"
                session.commit()
        except Exception:
            session.rollback()
            raise
        return {
            "records_processed": len(result["records"]),
            "skipped": result["skipped"],
            "coverage": result["coverage"],
            "source_url": search_url,
            "note": "Source-reported active at fetch time. No independent current-delivery verification or exhaustive pagination.",
        }
    finally:
        _discovery_lock.release()


@app.get("/ads/{ad_id}/evidence")
def ad_evidence(ad_id: int, data_mode: Literal["demo", "real"] | None = None, page: int = Query(1, ge=1), session: DBSession = Depends(db)):
    get_ad(session, ad_id, data_mode)
    query = select(RawEvidence).where(RawEvidence.ad_id == ad_id, or_(RawEvidence.retention_until.is_(None), RawEvidence.retention_until > utc_now()))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.order_by(RawEvidence.observed_at.desc(), RawEvidence.id.desc()).offset((page - 1) * 10).limit(10))
    return {"items": [{c.name: getattr(row, c.name) for c in RawEvidence.__table__.columns} for row in rows], "total": total, "page": page}
